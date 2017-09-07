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



def initCache():
    query = ("SELECT id, linkUrl FROM pp")
    try:
        conn=connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        for (idd, linkUrl) in cursor:
            docs[linkUrl]=idd
    finally:
        cursor.close()
        conn.close()
    

def searchPpProduct(key=""):
    logger.info("Start scan all pp products")
    url="https://mstore.ppdai.com/product/searchPro"
    pageIndex = 1;
    pageSize = 100
    onlyFirst = True
    while True:
        payload ={"pageIndex":pageIndex, "pageSize":pageSize,"name":key}
        proContent = getReponseFromPp(url, payload)
        totalPage = proContent["responseContent"]["totalPage"]
        prodList = proContent["responseContent"]["product004List"]
        if onlyFirst:
            logger.info("Find " + str(proContent["responseContent"]["totalCount"]) + " products from pp" )
            onlyFirst = False
        
        for prod in prodList:
            if prod["linkUrl"] in docs:
                continue
            prod["name"] = re.sub(u"(\u2018|\u2019|\xa0|\u2122)", "", prod["name"])
            del prod["pictureUrl"],prod["iconTypeName"],prod["hotWords"]
            prodId = prod["linkUrl"][9:]
            prod["seller"] = getSeller(prodId)
            prod["skuNames"] = ""
            prod["skuIds"] = ""
            ppProdSku(prodId, prod)
        if pageIndex >= totalPage:
            break
        pageIndex = pageIndex + 1
    pass
    logger.info("End scan all pp products")


def getSeller(prodId):
    payload={"productSkuId": prodId}
    url="https://mstore.ppdai.com/product/getSkuProDeatils"    
    proContent = getReponseFromPp(url, payload)
    return proContent["responseContent"]["sellerName"]

def ppProdSku(prodId, prod):
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

    
def getReponseFromPp(url, payload):
    while True:
        try:
            params = json.dumps(payload).encode('utf8')
            request = urllib.request.Request(url, data=params,
                                        headers={'content-type': 'application/json;charset=UTF-8', "Accept": "application/json"})
            setProxy(request)
            response = urllib.request.urlopen(request, timeout=10)
            responseContent = response.read()
            return json.loads(responseContent) 
        except Exception as e:
            logger.error(e)
            time.sleep(2)
    

def insertOrUpdateDB(doc):
    exist = doc["linkUrl"] in docs
    while True:
        try:
            conn = connectToDb()
            cursor = conn.cursor()
            if exist:
                result = docs[doc["linkUrl"]]
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
                data_pp = {
                    'product_id': doc["linkUrl"][9:],
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
            conn.commit()
            break
        except Exception as e:
            logger.error(e)
            time.sleep(2)
        finally:
            cursor.close()
            conn.close()  
    


def updatePrice(cursor, doc):
    
    pass
       
def jdProducts(keywords, e_keywords, o_keywords, searchId, productIds, inProductIds):
    url="https://so.m.jd.com/ware/search.action?keyword=" + urllib.parse.quote(keywords)
    request = urllib.request.Request(url, headers={'content-type': 'application/json;charset=UTF-8', "Accept": "application/json"})
    setProxy(request)

    response = urllib.request.urlopen(request)
    lines = response.readlines()
    for line in lines:
        strLine = line.decode("utf-8")
        if "searchData:" in strLine:
            prodList = strLine[strLine.index("searchData:") + len("searchData:"):strLine.index("abtestForUpToSaving") - 2]
            prods = json.loads(prodList)
            break
    wareList = prods["wareList"]["wareList"]
    for ware in wareList:
        searched = True
        values = str(ware.values()).lower()
        for kw in keywords.split(","):
            if kw not in values:
                searched = False
                break
        if not searched:
            continue        
        for kw in e_keywords.split(","):
            if kw in values and kw != "":
                searched = False
                break
        if not searched:
            continue
        searched = False
        for kw in e_keywords.split(","):
            if kw in values and kw != "":
                searched = True
                break
        if not searched:
            continue        
        jdself = config.get("server", "jd.only.self")
        if jdself.lower() == "true" and not ware["self"]:
            continue
            
        data_price = {
            'search_id': searchId,
            'product_id': ware["wareId"],
            'price': ware["jdPrice"],
            'description': ware["wname"],
            'seller': "jd",
            'src': "jd",
            'url': "https://item.m.jd.com/product/" + ware["wareId"] + ".html",
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
    

class SearchPpProduct (threading.Thread):
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
    

def scanPrice(keywords, e_keywords, o_keywords, searchId):
    if e_keywords == None:
        e_keywords = ""
    query = ("SELECT name, product_id, seller, linkUrl,price FROM pp where ")
    likes = lambda key : " name like '%" + key +"%'" 
    nlikes = lambda key : " name not like '%" + key +"%'"
    likesQuery = list(map(likes, keywords.split(",")))
    inProductIds=[]
    if e_keywords == "":
        sql = query + " and ".join(likesQuery)
    else:
        nlikesQuery = list(map(nlikes, e_keywords.split(",")))
        sql = query + " and ".join(likesQuery) + " and " + " and ".join(nlikesQuery)
    
    if o_keywords != "":
        nlikesQuery = list(map(nlikes, o_keywords.split(",")))
        sql = query + " and " +"(" +" or ".join(nlikesQuery) +")"        
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        productIds = getProductIdsFromPrice(cursor, searchId)
        cursor.execute(sql)
        for (name, productId, seller,linkeUrl, price) in cursor:
            data_price = {
                'search_id': searchId,
                'product_id': productId,
                'price': price,
                'seller': seller,
                'description': name,
                'src': "pp",
                'url': "https://mstore.ppdai.com/" + linkeUrl,
                "create_date": getFormatDate(),
                "update_date": getFormatDate()
            }
            inProductIds.append(str(productId))
            if str(productId) in productIds:
                cursor.execute(update_price, data_price)
            else:    
                cursor.execute(add_price, data_price)        
        conn.commit()
        jdProducts(keywords.lower(), e_keywords.lower(), o_keywords.lower(), searchId, productIds, inProductIds)
        deletePrices(searchId, set(productIds) - set(inProductIds))
    finally:
        cursor.close()
        conn.close()


def deletePrices(searchId, productIds):
    try:
        logger.info("Start delete price for products(" + str(productIds) + ")")
        conn = connectToDb()
        cursor = conn.cursor()
        for productId in productIds:
            query=("Delete from price where search_id=" + str(searchId) + " and product_id=" + str(productId))
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
    sql = ("select p.id, p.search_id, p.product_id, src, s.keywords, s.e_keywords, pp.skuIds from price p left join pp "
            "on p.product_id=pp.product_id  and src='pp' left join search s on s.id=p.search_id")
    conn = connectToDb()
    cursor = conn.cursor()
    cursor.execute(sql)
    searchs={}
    for (priceId, searchId, productId, src, keywords, e_keywords, skuIds) in cursor:
        if src == 'pp':
            fetchPriceByAttributes(priceId, productId, skuIds.split(","))
        else:
            if e_keywords == None:
                e_keywords = ""
            searchs[searchId] = {"keywords" : keywords, "e_keywords" :e_keywords, "productId": productId}
    inProductIds=[]
    for (searchId, search) in searchs.items():
        productIds = getProductIdsFromPrice(cursor, searchId, "jd")                
        jdProducts(search["keywords"], search["e_keywords"], searchId, productIds, inProductIds)
        deletePrices(searchId, set(productIds) - set(inProductIds))
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