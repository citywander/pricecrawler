import urllib.request
import json
import re
import copy
import time
import urllib.parse
import threading
import datetime
import sys
from globUtils import connectToDb, logger, retry
from globUtils import getFormatDate, config

docs = {}
docss = {}

beyondPrice = float(2.5)

add_pp = ("INSERT INTO pp "
              "(product_id, name, skuNames, skuIds, linkUrl, price, monthPayments, months,seller,saleState,create_date, update_date,category_id) "
              "VALUES (%(product_id)s, %(name)s, %(skuNames)s, %(skuIds)s, %(linkUrl)s,  %(price)s, %(monthPayments)s, %(months)s, %(seller)s, %(saleState)s, %(create_date)s, %(update_date)s, %(category_id)s)")

update_pp = ("UPDATE pp "
             "SET price=%(price)s,saleState=%(saleState)s, monthPayments= %(monthPayments)s, skuNames=%(skuNames)s, skuIds=%(skuIds)s, update_date=%(update_date)s "
             "WHERE id=%(id)s"
             )

add_price = ("INSERT INTO price "
              "(search_id, product_id, description, src, price, last_price, seller, url, saleState,self, two_hand, create_date, update_date, scan_date)"
              "VALUES (%(search_id)s, %(product_id)s, %(description)s, %(src)s, %(price)s, %(price)s, %(seller)s, %(url)s, %(saleState)s, %(self)s, %(two_hand)s, %(create_date)s, %(update_date)s, %(update_date)s)")

update_price = ("UPDATE price "
              "set price=%(price)s, last_price=price, update_date=%(update_date)s,saleState=%(saleState)s "
              "WHERE search_id=%(search_id)s and product_id=%(product_id)s and price!=%(price)s")

update_price_scan_date = ("UPDATE price "
              "set scan_date=%(update_date)s "
              "WHERE search_id=%(search_id)s and product_id=%(product_id)s")

add_category=("INSERT INTO category "
              "(category_id, name, parent_category_id)"
              "VALUES (%(category_id)s, %(name)s, %(parent_category_id)s)")

def refresProductCache():
    query = ("SELECT id, product_id, name, price, saleState FROM pp")
    productCache = set()
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        for (idd, product_id, name, price, saleState) in cursor:
            docs[str(product_id)] = {"id": idd, "name": name.lower(), "price":price, "saleState":saleState}
            productCache.add(str(product_id))
        for product_id in productCache - set(docs.keys()):
            del docs[product_id]
    finally:
        cursor.close()
        conn.close()

def refresProductCaches():
    query = ("SELECT id, product_id, name, price, saleState FROM wy_reptilian_commodity")
    productCache = set()
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        for (idd, product_id, name, price, saleState) in cursor:
            docss[str(product_id)] = {"id": idd, "name": name.lower(), "price":price, "saleState":saleState}
            productCache.add(str(product_id))
        for product_id in productCache - set(docss.keys()):
            del docss[product_id]
    finally:
        cursor.close()
        conn.close()

def searchPpProduct(refresh=False):
    logger.info("Start scan all pp products")
    curDocs = set()
    categories = getCategories()
    
    for category in categories:
        categoryId=category["category_id"]
        parentId=category["parent_category_id"]
        if parentId is None:
            continue
        logger.info("Start scan pp %s products"%(categoryId,))
        parseProdByCategory(refresh, categoryId, curDocs)
    pass
    
    if refresh:
        deleteOldProducts(docs, curDocs)
        refresProductCache()
    logger.info("End scan all pp products")
    
def getCategories():    
    query = ("SELECT category_id from category")
    ctgSet = set()
    
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        for (ctgId, ) in cursor:
            ctgSet.add(ctgId)
    finally:
        cursor.close()
        conn.close()    
    
    ctgUrl = "https://mstore.ppdai.com/avtm/getIndexCategoryNav"
    payload = {"channel":1}
    
    allCtgs = []
    resContent = getReponseFromPp(ctgUrl, payload)
    categoryList = resContent["responseContent"]
    categories = parseCategory(ctgSet, resContent)
    allCtgs.extend(categories)
    for ctg in categories:
        idd=ctg["category_id"]
        ctgUrl = "https://mstore.ppdai.com/category/getChildCategories?parentId=" + idd
        resContent = getReponseFromPp(ctgUrl)
        categoryList = resContent["responseContent"]
        categories = parseCategory(ctgSet, resContent, idd)
        allCtgs.extend(categories)
    
    return allCtgs


def parseCategory(ctgSet, resContent, parent_category_id = None):
    categories = []
    categoryList = resContent["responseContent"]
    for ct in categoryList:
        category = {}
        category["name"] = ct["name"]
        if parent_category_id == None:
            category["category_id"] = ct["linkUrl"][34:]
        else:
            category["category_id"] = ct["id"]
        category["parent_category_id"] = parent_category_id
        categories.append(category)
        if not int(category["category_id"]) in ctgSet:
            insertCategory(category["category_id"], ct["name"], parent_category_id)    
    return categories


def insertCategory(ctgId, name, parentId):
    conn = connectToDb()
    cursor = conn.cursor()
    data_pp = {
        'category_id': ctgId,
        'name': re.sub(u"(\u2018|\u2019|\xa0|\u2122)", "", name),
        "parent_category_id": parentId
    }
    cursor.execute(add_category, data_pp)
    conn.commit()
    
def parseProdByCategory(refresh, categoryId, curDocs):
    url = "https://mstore.ppdai.com/product/searchSku"
    
    pageIndex = 1;
    pageSize = 100   
    
    while True:
        payload = {"pageIndex":pageIndex, "pageSize":pageSize,"categoryId":categoryId}
        proContent = getReponseFromPp(url, payload)
        prodList = proContent["responseContent"]
        if prodList == []:
            break

        for prod in prodList:
            prodId = prod["linkUrl"][9:]
            if prodId in docs and not refresh:
                continue
            prod["name"] = re.sub(u"(\u2018|\u2019|\xa0|\u2122)", "", prod["name"])
            del prod["pictureUrl"], prod["iconTypeName"], prod["hotWords"]
            prod["seller"] = getSeller(prodId)
            prod["skuNames"] = ""
            prod["skuIds"] = ""
            ppProdSku(categoryId, prodId, prod, curDocs)

        pageIndex = pageIndex + 1
    pass    
    
    
def deleteOldProducts(docs, ids):
    logger.info("begin to delete useless products")
    deleteIds = set()
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
    payload = {"productSkuId": prodId}
    url = "https://mstore.ppdai.com/product/getSkuProDeatils"    
    proContent = getReponseFromPp(url, payload)
    return proContent["responseContent"]["sellerName"]


def ppProdSku(categoryId, prodId, prod, curDocs):
    url = "https://mstore.ppdai.com/product/getAttribute"
    payload = {"productSkuId": prodId}
    proContent = getReponseFromPp(url, payload)
    
    crossIds = []
    attributeNames = {}
    attributeValueIds = {}
    init = True
    for attributes in proContent["responseContent"]:
        preKeeyIds = crossIds
        crossIds = []
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
                       "seller": prod["seller"],
                       "category_id": categoryId,
                       "saleState": sku["saleState"]}
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

    
def getReponseFromPp(url, payload = None, dead=True):
    if payload != None:
        params = json.dumps(payload).encode('utf8')
        method = "POST"
    else:
        params = None
        method = "GET"
    while dead:
        try:            
            request = urllib.request.Request(url, data=params,
                                                 headers={'content-type': 'application/json;charset=UTF-8', "Accept": "application/json"}, method=method)                
            setProxy(request)
            response = urllib.request.urlopen(request, timeout=10)
            responseContent = response.read()
            info = response.info()
            serverDatetime = datetime.datetime.strptime(info["Date"], '%a, %d %b %Y %H:%M:%S GMT')
            expireDatetime = datetime.datetime.strptime("17 Oct 2017 10:00:00 GMT", '%d %b %Y %H:%M:%S GMT')
            #if serverDatetime > expireDatetime:
            #    print("Expire time is 10 Oct 2017 10:00:00 GMT, Application Exit")
            #    sys.exit(1)
            return json.loads(responseContent.decode('utf-8')) 
        except Exception as e:
            logger.error(str(e) + "--" + url)
            time.sleep(2)
    

def insertOrUpdateDB(doc):
    productId = doc["linkUrl"][9:]
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
                    "saleState": doc["saleState"],
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
                    'saleState': doc["saleState"],
                    'monthPayments': doc["monthPayments"],
                    'months': doc["months"],
                    'seller': doc["seller"],
                    "category_id": doc["category_id"],
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


def jdKeywordsPriceByUrl(usr):
    headers = {'content-type': 'application/json;charset=UTF-8',
             "Accept": "application/json",
             "Cookie":'JAMCookie=true; USER_FLAG_CHECK=85b0b2409f79d6915479702195a7f7fe; sid=8f905c0ea3d730a68dc2d2bb7a142e4c; __jda=181809404.15048617124911937256625.1504861712.1504861712.1504861712.1; __jdb=181809404.6.15048617124911937256625|1.1504861712; __jdv=181809404|direct|-|none|-|1504861712492; __jdc=181809404; mba_muid=15048617124911937256625; mba_sid=15048617124924978589409612432.6;'}
    request = urllib.request.Request(usr, headers=headers)
    setProxy(request)
    response = urllib.request.urlopen(request)
    lines = response.readlines()
    description = ""
    price = -1
    result = {}
    for line in lines:
        strLine = line.decode("utf-8").lower()
        if "keywords" in strLine and "description" not in result:
            description = strLine[strLine.index("content") + 9: strLine.rfind('"')]
            result["description"] = description
        if "&yen;<em>" in strLine:            
            price = strLine.strip().replace("&yen;<em>", "").replace("</em>","")
            result["price"] = price
            break
        if "big-price" in strLine:
            price = strLine[strLine.index(">") + 1: strLine.index("/") - 1 ]
            result["price"] = price
            break
    if "description" not in result:
        result["description"] = ""
    if "price" not in result:
        result["price"] = -1
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
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(update_price, data_price)
        cursor.execute(update_price_scan_date, data_price)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    pass


def jdProducts(product_id, keywords, e_keywords, o_keywords, searchId, productIds, inProductIds, international, twohand):
    if str(product_id) not in docss:
        logger.error("This product id-" + str(product_id) + " can't be found")
        return
    jdself = config.get("server", "jd.only.self")
    twoword = config.get("words", "two")
    jddetail = config.get("words", "two")
    url = "https://so.m.jd.com/ware/search.action?keyword=" + urllib.parse.quote(keywords)
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
    huiyaPrice = docss[str(product_id)]["price"]
    huisaleState = docss[str(product_id)]["saleState"]
    print("n1sad")
    global n1
    for ware in wareList:
        n1 = 1
        # print(ware["property_flag"])
        if not ware["self"]:
            n1=2
         # if jdtwo.lower() == "false" and twoword in ware["wname"]:
        #    continue
        print(n1)
        print(ware["wname"])
        itemUrl = "https://item.m.jd.com/product/" + ware["wareId"] + ".html"
        if international == 0 and ware["international"]:
            continue
        if float(huiyaPrice) / float(ware["jdPrice"]) > beyondPrice and huisaleState == 1:
            continue
        if ware["international"]:
            itemUrl = "https://mitem.jd.hk/product/" + ware["wareId"] + ".html"
        description = ware["wname"]
        two_hand_val = 0
        hasTwoword = twoword in description
        if twohand == 0 and hasTwoword:
            continue
        if hasTwoword:
            two_hand_val = 1
        if not matchKeywords(description.lower(), keywords, e_keywords, o_keywords):
            if jddetail.lower() == "false":
                continue
            # result = jdKeywordsPriceByUrl(itemUrl)
            # description = result["description"].lower()
            # print("description是："+description)
            # print("keywords：" + keywords)
            # print("keywords：" + keywords)
            # print("keywords：" + keywords)
            if not matchKeywords(ware["wname"], keywords, keywords, keywords):
                continue
        data_price = {
            'search_id': searchId,
            'product_id': ware["wareId"],
            'price': ware["jdPrice"],
            'description': ware["wname"],
            'seller': "jd",
            'saleState': 1,
            'self':n1,
            'two_hand': two_hand_val,
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
                cursor.execute(update_price_scan_date, data_price)
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
        retryScanAllPrice()


def setProxy(request):
    if config.has_option("proxy", "http.proxy"):
        request.set_proxy(config.get("proxy", "http.proxy"), 'http')
    
    if config.has_option("proxy", "https.proxy"):
        request.set_proxy(config.get("proxy", "https.proxy"), 'https')


def deletePriceBySearchId(searchId):
    query = ("Delete from price where search_id=" + str(searchId))
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    pass
    

def scanPrice(product_id, keywords, e_keywords, o_keywords, searchId, international, twohand):
    if e_keywords == None:
        e_keywords = ""
    if o_keywords == None:
        o_keywords = ""        
    query = ("SELECT name, product_id,price,saleState FROM wy_reptilian_commodity where product_id=" + product_id + " or  ")
    likes = lambda key : " name like '%" + key + "%'" 
    nlikes = lambda key : " name not like '%" + key + "%'"
    olikes = lambda key : " name like '%" + key + "%'"
    likesQuery = list(map(likes, keywords.split(",")))
    inProductIds = []
    if e_keywords == "":

        sql = query + " and ".join(likesQuery)
    else:
        nlikesQuery = list(map(nlikes, e_keywords.split(",")))
        sql = query + " and ".join(likesQuery) + " and " + " and ".join(nlikesQuery)
    
    if o_keywords != "":
        nlikesQuery = list(map(olikes, o_keywords.split(",")))
        sql = sql + " and " + "(" + " or ".join(nlikesQuery) + ")" 
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        productIds = getProductIdsFromPrice(cursor, searchId)
        cursor.execute(sql)

#       huiyaPrice = docs[product_id]["price"]

        for (name, productId, price, saleState) in cursor:


            # if huiyaPrice / float(price) > beyondPrice:
            #     continue
            # if seller == config.get("words", "weiya") and str(productId) != product_id:
            #     continue
            data_price = {
                'search_id': searchId,
                'product_id': productId,
                'price': price,
                'seller': "纬雅",
                'saleState':saleState,
                'self':1,
                'description': name,
                'src': "pp",
                'two_hand': 0,
                'url': productId,
                "create_date": getFormatDate(),
                "update_date": getFormatDate()
            }
            inProductIds.append(str(productId))
            if str(productId) in productIds:
                cursor.execute(update_price, data_price)
            else:
                cursor.execute(add_price, data_price)
        conn.commit()
        # print("拍拍贷商品吧注解解开可和拍拍贷商品比较")
        #scanPrices(keywords, e_keywords, o_keywords, searchId)

        refresProductCaches()
        jdProducts(product_id, keywords, e_keywords, o_keywords, searchId, productIds, inProductIds, international, twohand)
        deletePrices(searchId, set(productIds) - set(inProductIds))
        updateMaxMinAvg()
    finally:
        cursor.close()
        conn.close()


def scanPrices(keywords, e_keywords, o_keywords, searchId):
    if e_keywords == None:
        e_keywords = ""
    if o_keywords == None:
        o_keywords = ""
    query = (
                "SELECT name, product_id, seller, linkUrl,price,saleState FROM pp where ")
    likes = lambda key: " name like '%" + key + "%'"
    nlikes = lambda key: " name not like '%" + key + "%'"
    olikes = lambda key: " name like '%" + key + "%'"
    likesQuery = list(map(likes, keywords.split(",")))
    inProductIds = []
    if e_keywords == "":
        sql = query + " and ".join(likesQuery)
    else:
        nlikesQuery = list(map(nlikes, e_keywords.split(",")))
        sql = query + " and ".join(likesQuery) + " and " + " and ".join(nlikesQuery)

    if o_keywords != "":
        nlikesQuery = list(map(olikes, o_keywords.split(",")))
        sql = sql + " and " + "(" + " or ".join(nlikesQuery) + ")"
    try:
        print(sql)
        conn = connectToDb()
        cursor = conn.cursor()
        productIds = getProductIdsFromPrice(cursor, searchId)
        cursor.execute(sql)
        # huiyaPrice = docs[product_id]["price"]
        for (name, productId, seller, linkeUrl, price, saleState) in cursor:
            print(name)
            print(productId)
            print(seller)
            print(linkeUrl)
            print(price)
            print(saleState)
            data_price = {
                'search_id': searchId,
                'product_id': productId,
                'price': price,
                'seller': seller,
                'saleState': saleState,
                'self': 1,
                'description': name,
                'src': "pp",
                'two_hand': 0,
                'url': "https://mstore.ppdai.com" + linkeUrl,
                "create_date": getFormatDate(),
                "update_date": getFormatDate()
            }
            inProductIds.append(str(productId))
            if str(productId) in productIds:
                cursor.execute(update_price, data_price)
            else:
                print(data_price["description"])
                cursor.execute(add_price, data_price)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
        
def updateMaxMinAvg():
    update1 = '''update search s set min_price_id=(select id from price pp where s.id=pp.search_id and price =
                (select min(price) from price p where s.id=p.search_id and s.product_id!=p.product_id and p.two_hand=0 group by search_id) limit 1)'''
    update2 = '''update search s set max_price_id=(select id from price pp where s.id=pp.search_id and price =
                (select max(price) from price p where s.id=p.search_id and s.product_id!=p.product_id and p.two_hand=0 group by search_id) limit 1)
            '''
    update3 = "update search s set avg_price=(select avg(price) from price p where s.id=p.search_id and saleState=1 and p.two_hand=0 group by search_id)"
    update4 = "update price p , (select price, search_id from price pp where pp.seller='%s') t set p.gap_price=p.price - t.price where p.search_id=t.search_id"
    update5 = "update search s set count=(select count(*) from price p where p.search_id=s.id and seller!='%s' and saleState=1 )"
    weiya = config.get("words", "weiya")
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(update1)
        cursor.execute(update2)
        cursor.execute(update3)
        cursor.execute(update4 % (weiya,))
        cursor.execute(update5 % (weiya,))
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
            query = ("Delete from price where search_id=" + str(searchId) + " and product_id=" + str(productId) + " and is_input=0")
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
        query = ("SELECT product_id FROM price where search_id=" + str(searchId) + " and src='" + src + "'")
    cursor.execute(query)
    productIds = []
    for (productId,) in cursor:
        productIds.append(str(productId))
    return productIds


def scanAllPrice():
    logger.info("Start scan price")
    print("自动更新")
    sql = ("select p.id, p.search_id, p.product_id, src, s.keywords, s.e_keywords, s.o_keywords, s.is_auto, s.two_hand, p.url, s.product_id, s.international from price p"
            "left join search s on s.id=p.search_id")
    conn = connectToDb()
    cursor = conn.cursor()
    cursor.execute(sql)
    searchs = {}
    for (priceId, searchId, productId, src, keywords, e_keywords, o_keywords, is_auto, two_hand, url, sproduct_id, international) in cursor:
         if src == 'jd':
         #   if skuIds != None:
         #         fetchPriceByAttributes(priceId, productId, skuIds.split(","))
         # else:
            if e_keywords == None:
                e_keywords = ""
            searchs[searchId] = {"keywords":keywords, "e_keywords":e_keywords, "o_keywords":o_keywords,
                                 "product_id": productId, "is_auto":is_auto, "search_id":searchId, "url":url, "sproduct_id":sproduct_id,
                                 "international":international, "two_hand":two_hand}
    for (searchId, search) in searchs.items():
        inProductIds = []
        productIds = getProductIdsFromPrice(cursor, searchId, "jd")
        if search["is_auto"]:
            jdProducts(search["sproduct_id"], search["keywords"], search["e_keywords"], search["o_keywords"], searchId, productIds, inProductIds, search["international"], two_hand)
        # else:
        #     jdProductsByUrl(search["search_id"], search["product_id"], search["url"])
        deletePrices(searchId, set(productIds) - set(inProductIds))
    pass
    updateMaxMinAvg()
    logger.info("End scan price")


def fetchPriceByAttributes(priceId, productId, attributeIds):
    sku = getSku(attributeIds, productId)
    skuProd = {"price":sku["price"],
               "saleState":sku["saleState"],
               "monthPayments": str(sku["monthPayments"]),
               "months": str(sku["months"]),
               "product_id": productId,
               "update_date": getFormatDate(),
               "id": priceId}
    
    updatePriceSql = ("update price " 
                      "set price=%(price)s, last_price=price, saleState=%(saleState)s,update_date=%(update_date)s "
                      "where id=%(id)s and price!=%(price)s")
    updatePriceDateSql = ("update price " 
                      "set scan_date=%(update_date)s "
                      "where id=%(id)s")
    updatePpSql = ("update pp "
                   "set price = %(price)s, saleState=%(saleState)s, monthPayments=%(monthPayments)s,months=%(months)s, update_date=%(update_date)s "
                   "where product_id=%(product_id)s")
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(updatePriceSql, skuProd)
        cursor.execute(updatePriceDateSql, skuProd)
        cursor.execute(updatePpSql, skuProd)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def retryScanAllPrice():
    retry(scanAllPrice)
    pass
