import urllib.request
import json
import re
import copy
import time
import urllib.parse
import threading
from globUtils import connectToDb, logger, retry
from globUtils import getFormatDate, config


docs = {}

beyondPrice = float(2.5)

add_pp = ("INSERT INTO pp "
              "(product_id, name, skuNames, skuIds, linkUrl, price, monthPayments, months,seller,create_date, update_date) "
              "VALUES (%(product_id)s, %(name)s, %(skuNames)s, %(skuIds)s, %(linkUrl)s,  %(price)s, %(monthPayments)s, %(months)s, %(seller)s, %(create_date)s, %(update_date)s)")

update_pp = ("UPDATE pp "
             "SET price=%(price)s, monthPayments= %(monthPayments)s, skuNames=%(skuNames)s, skuIds=%(skuIds)s, update_date=%(update_date)s "
             "WHERE id=%(id)s"
             )

add_price=("INSERT INTO price "
              "(search_id, product_id, description, src, price, seller, url, create_date, update_date)"
              "VALUES (%(search_id)s, %(product_id)s, %(description)s, %(src)s, %(price)s,  %(seller)s, %(url)s, %(create_date)s, %(update_date)s)")

update_price=("UPDATE price "
              "set price=%(price)s, update_date=%(update_date)s "
              "WHERE search_id=%(search_id)s and product_id=%(product_id)s")

def refresProductCache():
    query = ("SELECT id, product_id, name, price, seller FROM pp")
    productCache=set()
    try:
        conn=connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        for (idd, product_id, name, price, seller) in cursor:
            docs[str(product_id)]={"id": idd, "name": name.lower(), "seller":seller, "price":price}
            productCache.add(str(product_id))
        for product_id in productCache - set(docs.keys()):
            del docs[product_id]
    finally:
        cursor.close()
        conn.close()

def searchPpProduct(refresh=False):
    logger.info("Start scan all pp products")
    url="https://mstore.ppdai.com/product/searchPro"
    pageIndex = 1;
    pageSize = 100
    onlyFirst = True
    curDocs=set()
    while True:
        payload ={"pageIndex":pageIndex, "pageSize":pageSize,"name":""}
        proContent = getReponseFromPp(url, payload)
        totalPage = proContent["responseContent"]["totalPage"]
        prodList = proContent["responseContent"]["product004List"]
        if onlyFirst:
            logger.info("Find " + str(proContent["responseContent"]["totalCount"]) + " products from pp" )
            onlyFirst = False
        
        for prod in prodList:
            prodId = prod["linkUrl"][9:]
            if prodId in docs and not refresh:
                continue
            prod["name"] = re.sub(u"(\u2018|\u2019|\xa0|\u2122)", "", prod["name"])
            del prod["pictureUrl"],prod["iconTypeName"],prod["hotWords"]
            prod["seller"] = getSeller(prodId)
            prod["skuNames"] = ""
            prod["skuIds"] = ""
            ppProdSku(prodId, prod, curDocs)
        if pageIndex >= totalPage:
            break
        pageIndex = pageIndex + 1
    pass
    if refresh:
        deleteOldProducts(docs, curDocs)
        refresProductCache()
    logger.info("End scan all pp products")
    
    
def deleteOldProducts(docs, ids):
    logger.info("begin to delete useless products")
    deleteIds=set()
    for idd in docs.keys():
        if idd not in ids:
            deleteIds.add(idd)
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        for idd in deleteIds:
            logger.info("delete useless product:" + str(idd))
            sql = "delete from pp where product_id=" + idd
            cursor.execute(sql)
            del docs[idd]
            conn.commit()
        logger.info("End delete useless products")
    finally:
        cursor.close()
        conn.close()
    pass


def getSeller(prodId):
    payload={"productSkuId": prodId}
    url="https://mstore.ppdai.com/product/getSkuProDeatils"    
    proContent = getReponseFromPp(url, payload)
    return proContent["responseContent"]["sellerName"]

def ppProdSku(prodId, prod, curDocs):
    url = "https://mstore.ppdai.com/product/getAttribute"
    payload = {"productSkuId": prodId}
    proContent = getReponseFromPp(url, payload)
    
    crossIds=[]
    attributeNames={}
    attributeValueIds = {}
    init = True
    for attributes in proContent["responseContent"]:
        preKeeyIds = crossIds
        crossIds=[]
        preIds = copy.deepcopy(preKeeyIds)
        for attribute in attributes["attributeList"]:
            attributeValueIds[attribute["attributeValueId"]] = attributes["attributeId"]
            attributeNames[attribute["attributeValueId"]] = {"name": attribute["attributeValue"], "attributeId": attributes["attributeId"]}
            if init:
                crossIds.append([attribute["attributeValueId"]])
                continue
            for ids in preIds:
                copyIds = copy.deepcopy(ids)
                attributeValueId = attribute["attributeValueId"]
                copyIds.append(attributeValueId)
                crossIds.append(copyIds) 
        init = False
    
    prodName = prod["name"]
    srcProdName = getDefaultName(crossIds, attributeNames, attributeValueIds, prodName)
    for attributeIds in crossIds:
        skuNames = []
        skuIds = []
        prodName = srcProdName
        for attributeValueId in attributeIds:
            attributeName = attributeNames[attributeValueId]["name"]
            skuNames.append(attributeName)
            skuIds.append(str(attributeValueId))
            prodName = prodName.replace("{" + str(attributeValueIds[attributeValueId]) + "}", attributeName)
        sku = getSku(attributeIds, prodId)
        skuProd = {"name":prodName, "linkUrl": "/product/" + str(sku["id"]), "price":sku["price"], 
                       "monthPayments": str(sku["monthPayments"]), 
                       "months":str(sku["months"]),
                       "skuNames" :",".join(skuNames),
                       "skuIds" :",".join(skuIds),
                       "seller": prod["seller"]}
        product_id = skuProd["linkUrl"][9:]
        curDocs.add(product_id)
        insertOrUpdateDB(skuProd)

        
def getDefaultName(crossIds, attributeNames, attributeValueIds, prodName):
    defaultName = prodName
    for attributeIds in crossIds:
        for attributeValueId in attributeIds:
            attributeName = attributeNames[attributeValueId]["name"]
            if attributeName in prodName:
                defaultName = defaultName.replace(attributeName, "{" + str(attributeValueIds[attributeValueId]) + "}")    
    return defaultName
    

def getSku(attributeIds, prodId):
    url = "https://mstore.ppdai.com/product/getSkuProSimpleByAttr"
    payload = {"attributeValueIds":attributeIds, "productSkuId": prodId}
    proContent = getReponseFromPp(url, payload)
    return proContent["responseContent"]

    
def getReponseFromPp(url, payload, dead=True):
    while dead:
        try:
            params = json.dumps(payload).encode('utf8')
            request = urllib.request.Request(url, data=params,
                                        headers={'content-type': 'application/json;charset=UTF-8', "Accept": "application/json"})
            setProxy(request)
            response = urllib.request.urlopen(request, timeout=10)
            responseContent = response.read()
            return json.loads(responseContent.decode('utf-8')) 
        except Exception as e:
            logger.error(str(e) + "--" + url)
            time.sleep(2)
    

def insertOrUpdateDB(doc):
    productId=doc["linkUrl"][9:]
    exist = productId in docs
    while True:
        try:
            conn = connectToDb()
            cursor = conn.cursor()
            if exist:
                result = docs[productId]["id"]
                data_pp = {
                    'skuNames': doc["skuNames"],
                    'skuIds': doc["skuIds"],
                    'price': doc["price"],
                    'monthPayments': doc["monthPayments"],
                    'months': doc["months"],
                    'update_date': getFormatDate(),
                    'id': result
                }
                cursor.execute(update_pp, data_pp)
            else:
                product_id = doc["linkUrl"][9:]
                data_pp = {
                    'product_id': product_id,
                    'name': doc["name"],
                    'skuNames': doc["skuNames"],
                    'skuIds': doc["skuIds"],
                    'linkUrl': doc["linkUrl"],                    
                    'price': doc["price"],
                    'monthPayments': doc["monthPayments"],
                    'months': doc["months"],
                    'seller': doc["seller"],
                    'update_date': getFormatDate(),
                    'create_date': getFormatDate()
                }                
                cursor.execute(add_pp, data_pp)
                docs[product_id] = {"id": cursor.lastrowid, "name": doc["name"], "seller":doc["seller"]}
            conn.commit()            
            break
        except Exception as e:
            logger.error(e)
            time.sleep(2)
        finally:
            cursor.close()
            conn.close()  


def jdKeywordsPriceByUrl(url):
    headers={'content-type': 'application/json;charset=UTF-8', 
             "Accept": "application/json", 
             "Cookie":'JAMCookie=true; USER_FLAG_CHECK=85b0b2409f79d6915479702195a7f7fe; sid=8f905c0ea3d730a68dc2d2bb7a142e4c; __jda=181809404.15048617124911937256625.1504861712.1504861712.1504861712.1; __jdb=181809404.6.15048617124911937256625|1.1504861712; __jdv=181809404|direct|-|none|-|1504861712492; __jdc=181809404; mba_muid=15048617124911937256625; mba_sid=15048617124924978589409612432.6;'}
    request = urllib.request.Request(url, headers=headers)
    setProxy(request)
    response = urllib.request.urlopen(request)
    lines = response.readlines()
    description = ""
    price = -1
    result = {"description":description, "price": price}
    for line in lines:
        strLine = line.decode("utf-8")
        if "keywords" in strLine:
            description = strLine[strLine.index("CONTENT") + 9: strLine.index(">") -1 ]
            result["description"] = description
        if "big-price" in strLine:
            price = strLine[strLine.index(">") + 1: strLine.index("/") -1 ]
            result["price"] = price
            break
    return result    

def jdProductsByUrl(search_id, product_id, url):
    kwprice = jdKeywordsPriceByUrl(url)
    data_price = {
        'price': kwprice["price"],
        'search_id': search_id,
        'product_id': product_id,
        'description': kwprice["description"],
        "update_date": getFormatDate()
    }
    update_price=("UPDATE price "
              "set price=%(price)s, description=%(description)s, update_date=%(update_date)s "
              "WHERE search_id=%(search_id)s and product_id=%(product_id)s")
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(update_price, data_price)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    pass            
       
def jdProducts(product_id, keywords, e_keywords, o_keywords, searchId, productIds, inProductIds, international):
    jdself = config.get("server", "jd.only.self")
    jdtwo = config.get("server", "jd.two")
    twoword=config.get("words", "two")
 
    url="https://so.m.jd.com/ware/search.action?keyword=" + urllib.parse.quote(keywords)
    request = urllib.request.Request(url, headers={'content-type': 'application/json;charset=UTF-8', "Accept": "application/json"})
    setProxy(request)
    if not e_keywords:
        e_keywords = ""
    if not o_keywords:
        o_keywords = ""
    response = urllib.request.urlopen(request)
    lines = response.readlines()
    for line in lines:
        strLine = line.decode("utf-8")
        if "searchData:" in strLine:
            prodList = strLine[strLine.index("searchData:") + len("searchData:"):strLine.index("abtestForUpToSaving") - 2]
            prods = json.loads(prodList)
            break
    wareList = prods["wareList"]["wareList"]
    huiyaPrice=docs[str(product_id)]["price"]
    for ware in wareList:
        if jdself.lower() == "true" and not ware["self"]:
            continue
        if jdtwo.lower() == "false" and twoword in ware["wname"]:
            continue        
        itemUrl = "https://item.m.jd.com/product/" + ware["wareId"] + ".html"
        if international==0 and ware["international"]:
            continue
        if float(huiyaPrice)/float( ware["jdPrice"]) > beyondPrice:
            continue
        if ware["international"]:
            itemUrl = "https://mitem.jd.hk/product/" + ware["wareId"] + ".html"
        description = ware["wname"]
        if not matchKeywords(str(ware.values()).lower(), keywords, e_keywords, o_keywords):
            continue
            #result = jdKeywordsPriceByUrl(itemUrl)
            #description = result["description"].lower()
            #if not matchKeywords(description, keywords, e_keywords, o_keywords):
            #    continue
        data_price = {
            'search_id': searchId,
            'product_id': ware["wareId"],
            'price': ware["jdPrice"],
            'description': description,
            'seller': "jd",
            'src': "jd",
            'url': itemUrl,
            "create_date": getFormatDate(),
            "update_date": getFormatDate()
        }
        try:
            conn = connectToDb()
            cursor = conn.cursor()
            if ware["wareId"] in productIds:
                cursor.execute(update_price, data_price)
            else:            
                cursor.execute(add_price, data_price)
            inProductIds.append(str(ware["wareId"]))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        pass
 
 
def matchKeywords(description, keywords, e_keywords, o_keywords):
    for kw in keywords.split(","):
        if kw not in description:
            return False
    if not e_keywords:
        e_keywords = ""
    for kw in e_keywords.split(","):
        if kw in description and kw != "":
            return False
    searched = False
    if not o_keywords:
        o_keywords = ""    
    if o_keywords == "" or o_keywords == None:
        searched = True
    for kw in o_keywords.split(","):
        if kw in description and kw != "":
            searched = True
            break
    if not searched:
        return False
    return True   

class SearchPpProductThread (threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
      
    def run(self):
        searchPpProduct()


def setProxy(request):
    if config.has_option("proxy", "http.proxy"):
        request.set_proxy(config.get("proxy", "http.proxy"), 'http')
    
    if config.has_option("proxy", "https.proxy"):
        request.set_proxy(config.get("proxy", "https.proxy"), 'https')

def deletePriceBySearchId(searchId):
    query=("Delete from price where search_id=" + str(searchId))
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    pass
    

def scanPrice(product_id, keywords, e_keywords, o_keywords, searchId, international):
    if e_keywords == None:
        e_keywords = ""
    if o_keywords == None:
        o_keywords = ""        
    query = ("SELECT name, product_id, seller, linkUrl,price FROM pp where product_id=" + product_id + " or  ")
    likes = lambda key : " name like '%" + key +"%'" 
    nlikes = lambda key : " name not like '%" + key +"%'"
    olikes = lambda key : " name like '%" + key +"%'"
    likesQuery = list(map(likes, keywords.split(",")))
    inProductIds=[]
    if e_keywords == "":
        sql = query + " and ".join(likesQuery)
    else:
        nlikesQuery = list(map(nlikes, e_keywords.split(",")))
        sql = query + " and ".join(likesQuery) + " and " + " and ".join(nlikesQuery)
    
    if o_keywords != "":
        nlikesQuery = list(map(olikes, o_keywords.split(",")))
        sql = sql + " and " +"(" +" or ".join(nlikesQuery) +")" 
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        productIds = getProductIdsFromPrice(cursor, searchId)
        cursor.execute(sql)
        huiyaPrice=docs[product_id]["price"]
        for (name, productId, seller,linkeUrl, price) in cursor:
            if float(huiyaPrice)/float(price) > beyondPrice:
                continue
            if seller==config.get("words", "weiya") and str(productId) != product_id:
                continue
            data_price = {
                'search_id': searchId,
                'product_id': productId,
                'price': price,
                'seller': seller,
                'description': name,
                'src': "pp",
                'url': "https://mstore.ppdai.com" + linkeUrl,
                "create_date": getFormatDate(),
                "update_date": getFormatDate()
            }
            inProductIds.append(str(productId))
            if str(productId) in productIds:
                cursor.execute(update_price, data_price)
            else:    
                cursor.execute(add_price, data_price)        
        conn.commit()
        jdProducts(product_id, keywords, e_keywords, o_keywords, searchId, productIds, inProductIds, international)
        updateMaxMinAvg()
        deletePrices(searchId, set(productIds) - set(inProductIds))
    finally:
        cursor.close()
        conn.close()
        
def updateMaxMinAvg():
    update1="update search s set min_price=(select min(price) price from price p where s.id=p.search_id group by search_id)"
    update2="update search s set max_price=(select max(price) price from price p where s.id=p.search_id group by search_id)"
    update3="update search s set avg_price=(select avg(price) price from price p where s.id=p.search_id group by search_id)"
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(update1)
        cursor.execute(update2)
        cursor.execute(update3)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    pass


def deletePrices(searchId, productIds):
    try:
        logger.info("Start delete price for products(" + str(productIds) + ")")
        conn = connectToDb()
        cursor = conn.cursor()
        for productId in productIds:
            query=("Delete from price where search_id=" + str(searchId) + " and product_id=" + str(productId) + " and is_input=0")
            cursor.execute(query)
        conn.commit()  
    finally:
        cursor.close()
        conn.close()          
    pass

def getProductIdsFromPrice(cursor, searchId, src=None):    
    if src == None:
        query = ("SELECT product_id FROM price where search_id=" + str(searchId))
    else:
        query = ("SELECT product_id FROM price where search_id=" + str(searchId) + " and src='" + src +"'")
    cursor.execute(query)
    productIds = []
    for (productId, ) in cursor:
        productIds.append(str(productId))
    return productIds


def scanAllPrice():
    logger.info("Start scan price")
    sql = ("select p.id, p.search_id, p.product_id, src, s.keywords, s.e_keywords, s.o_keywords,  pp.skuIds, s.is_auto, p.url, s.product_id, s.international from price p left join pp "
            "on p.product_id=pp.product_id  and src='pp' left join search s on s.id=p.search_id")
    conn = connectToDb()
    cursor = conn.cursor()
    cursor.execute(sql)
    searchs={}
    for (priceId, searchId, productId, src, keywords, e_keywords, o_keywords, skuIds, is_auto, url, sproduct_id, international) in cursor:
        if src == 'pp':
            fetchPriceByAttributes(priceId, productId, skuIds.split(","))
        else:
            if e_keywords == None:
                e_keywords = ""
            searchs[searchId] = {"keywords":keywords,"e_keywords":e_keywords,"o_keywords":o_keywords,
                                 "product_id": productId, "is_auto":is_auto, "search_id":searchId,"url":url, "sproduct_id":sproduct_id, "international":international}
    inProductIds=[]
    for (searchId, search) in searchs.items():
        productIds = getProductIdsFromPrice(cursor, searchId, "jd")
        if search["is_auto"]:            
            jdProducts(search["sproduct_id"], search["keywords"], search["e_keywords"], search["o_keywords"], searchId, productIds, inProductIds, search["international"])
        else:
            jdProductsByUrl(search["search_id"], search["product_id"], search["url"])
        deletePrices(searchId, set(productIds) - set(inProductIds))
        updateMaxMinAvg()
    pass
    logger.info("End scan price")

def fetchPriceByAttributes(priceId, productId, attributeIds):
    sku = getSku(attributeIds, productId)
    skuProd = {"price":sku["price"],
               "monthPayments": str(sku["monthPayments"]),
               "months": str(sku["months"]),
               "product_id": productId,
               "update_date": getFormatDate(),
               "id": priceId}
    
    updatePriceSql = ("update price " 
                      "set price = %(price)s, update_date=%(update_date)s "
                      "where id=%(id)s")
    updatePpSql = ("update pp "
                   "set price = %(price)s, monthPayments=%(monthPayments)s,months=%(months)s, update_date=%(update_date)s "
                   "where product_id=%(product_id)s")
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(updatePriceSql, skuProd)
        cursor.execute(updatePpSql, skuProd)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def retryScanAllPrice():
    retry(scanAllPrice)
    pass