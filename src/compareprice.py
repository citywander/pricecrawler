import urllib.request
import json
import re
import copy
import time,sched
import MySQLdb
import urllib.parse
import logging
import datetime
import threading
import configparser
from flask import Flask, request

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger = logging.getLogger('ComparePrice')
logger.setLevel(logging.DEBUG)
logger.addHandler(ch)

docs = {}

add_pp = ("INSERT INTO pp "
              "(name, skuNames, linkUrl, price, monthPayments, months,seller,create_date)"
              "VALUES (%(name)s, %(skuNames)s, %(linkUrl)s,  %(price)s, %(monthPayments)s, %(months)s, %(seller)s, %(create_date)s)")

update_pp = ("UPDATE pp "
             "SET price=%(price)s, monthPayments= %(monthPayments)s, skuNames=%(skuNames)s, skuIds=%(skuIds)s, update_date=%(update_date)s "
             "WHERE id=%(id)s"
             )

add_product=("INSERT INTO product "
              "(keywords, e_keywords, description, create_date, update_date) "
              "VALUES (%(keywords)s, %(e_keywords)s, %(description)s, %(create_date)s, %(update_date)s)")

update_product=("UPDATE product "
              "set e_keywords=%(e_keywords)s, description=%(description)s,update_date=%(update_date)s "
              "where id=%(id)s")

add_price=("INSERT INTO price "
              "(product_id, pp_id, price, seller, url, create_date, update_date)"
              "VALUES (%(product_id)s, %(pp_id)s, %(price)s,  %(seller)s, %(url)s, %(create_date)s, %(update_date)s)")

update_price=("UPDATE price "
              "set price=%(price)s, update_date=%(update_date)s "
              "WHERE product_id=%(product_id)s and pp_id=%(pp_id)s")

app = Flask(__name__)

def connectToDb():
    while True:
        try: 
            host=config.get("db","host")
            port=int(config.get("db","port"))
            user=config.get("db","user")
            pwd=config.get("db","pwd")
            return MySQLdb.connect(host=host, port=port, user=user, passwd=pwd, db="prodprice", charset='utf8')
        except Exception as e:
            print(e)
            time.sleep(2)


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
    url="https://mstore.ppdai.com/product/searchPro"
    pageIndex = 1;
    pageSize = 100
    while True:
        payload ={"pageIndex":pageIndex, "pageSize":pageSize,"name":key}
        proContent = getReponseFromPp(url, payload)
        totalPage = proContent["responseContent"]["totalPage"]
        prodList = proContent["responseContent"]["product004List"]
        for prod in prodList:
            prod["name"] = re.sub(u"(\u2018|\u2019|\xa0|\u2122)", "", prod["name"])
            del prod["pictureUrl"],prod["iconTypeName"],prod["hotWords"]
            prodId = prod["linkUrl"][9:]
            prod["seller"] = getSeller(prodId)
            insertOrUpdateDB(prod)
            ppProdSku(prodId, prod)
        if pageIndex >= totalPage:
            break
        pageIndex = pageIndex + 1
    pass


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
        insertOrUpdateDB(skuProd, False)
        
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
            #request.set_proxy("proxy.pvgl.sap.corp:8080", 'http')
            #request.set_proxy("proxy.pvgl.sap.corp:8080", 'https')
            response = urllib.request.urlopen(request, timeout=10)
            responseContent = response.read()
            return json.loads(responseContent) 
        except Exception as e:
            print(e)
            time.sleep(2)
    

def insertOrUpdateDB(doc, init = True):
    exist = doc["linkUrl"] in docs
    while True:
        try:
            conn = connectToDb()
            cursor = conn.cursor()
            if exist and not init:
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
            elif not exist and init:
                data_pp = {
                    'name': doc["name"],
                    'skuNames': "",
                    'linkUrl': doc["linkUrl"],
                    'price': doc["price"],
                    'monthPayments': doc["monthPayments"],
                    'months': doc["months"],
                    'seller': doc["seller"],
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
    
        
def jd(keywords):
    url="https://so.m.jd.com/ware/search.action?keyword=" + urllib.parse.quote(keywords)
    request = urllib.request.Request(url, headers={'content-type': 'application/json;charset=UTF-8', "Accept": "application/json"})
    #request.set_proxy("proxy.pvgl.sap.corp:8080", 'http')
    #request.set_proxy("proxy.pvgl.sap.corp:8080", 'https')

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
        print(str(ware).encode(encoding='utf_8', errors='strict'))

class SearchPpProduct (threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
      
    def run(self):
        searchPpProduct()


@app.route('/products', methods=['POST'])
def addProduct():
    product = request.json
    errorJson = {}
    if "keywords" not in product:
        errorJson["errorCode"] = "E001"
        errorJson["errorMsg"] = "keywords is requried"
        return responseError(errorJson, 400)
    description = None
    if "description" in product:
        description = product["description"]
    ekeywords = None
    if "ekeywords" in product:
        ekeywords = product["ekeywords"] 
    data_product = {
        'keywords': product["keywords"],
        'e_keywords': ekeywords,
        'description': description,
        "create_date": getFormatDate(),
        "update_date": getFormatDate()
    }
    productId = compareKeywords(product["keywords"])
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        if productId == -1:
            cursor.execute(add_product, data_product)
            productId = cursor.lastrowid
        else:
            data_product["id"] = productId
            cursor.execute(update_product, data_product)
        conn.commit()
        st = threading.Thread(target=scanPrice, args=(product["keywords"],ekeywords, productId))
        st.start()        
        return app.response_class(
            response=json.dumps({"result": "ok"}),
            status=200,
            mimetype='application/json'
        )
    except Exception as e:
        errorJson["errorCode"] = "E002"
        errorJson["errorMsg"] = str(e)
        return responseError(errorJson, 400) 
    finally:
        cursor.close()
        conn.close()
    

@app.route('/products/<path:productId>', methods=['DELETE'])
def deleteProduct(productId):
    query1=("Delete from product where id=" + productId)
    query2=("Delete from price where product_id=" + productId)
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query1)
        cursor.execute(query2)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    pass


@app.route('/products', methods=['GET'])
def queryProduct():
    keywords = request.args.get('keywords')
    likes = lambda key : " name like '%" + key +"%'" 
    query = "select keywords,e_keywords, description, price, seller, url, update_date from product pd, price p where pd.id=p.product_id"
    if not keywords is None:
        likesQuery = list(map(likes, keywords.split(",")))
        query = query + " and ".join(likesQuery.split(","))
        pass
    pass

@app.route('/Products/<path:productId>', methods=['PUT'])
def updateProduct(productId):
    product = request.json
    pass

def scanPrice(keywords, ekeywords, productId):
    if ekeywords is None:
        ekeywords = ""
    query = ("SELECT id, seller, linkUrl,price FROM pp where ")
    likes = lambda key : " name like '%" + key +"%'" 
    nlikes = lambda key : " name not like '%" + key +"%'"
    likesQuery = list(map(likes, keywords.split(",")))
    nlikesQuery = list(map(nlikes, ekeywords.split(",")))
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        print(query + " and ".join(likesQuery) + " and " + " and ".join(nlikesQuery))
        cursor.execute(query + " and ".join(likesQuery) + " and " + " and ".join(nlikesQuery))
        for (ppId, seller,linkeUrl, price) in cursor:
            data_price = {
                'product_id': productId,
                'pp_id': ppId,
                'price': price,
                'seller': seller,
                'url': linkeUrl,
                "create_date": getFormatDate(),
                "update_date": getFormatDate()
            }
            if existPrice(cursor, productId, ppId):
                cursor.execute(update_price, data_price)
            else:    
                cursor.execute(add_price, data_price)
        jd(cursor, keywords)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def existPrice(cursor, productId, ppId):
    query = ("SELECT id FROM price where product_id=" + str(productId) + " and pp_id=" + str(ppId))
    cursor.execute(query)
    row = cursor.fetchone()
    if row is None:
        return False
    return True

def responseError(errorMsg, statusCode):
    response = app.response_class(
        response=json.dumps(errorMsg),
        status=statusCode,
        mimetype='application/json'
    )
    return response

def compareKeywords(keywords):
    query = ("SELECT id, keywords FROM product where ")
    keys = keywords.split(",")
    likes = lambda key : " keywords like '%" + key +"%'" 
    allQuery = list(map(likes, keys))
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query + " and ".join(allQuery))
        for (idd, kkeywords) in cursor:
            if set(keys) == set(kkeywords.split(",")):
                return idd
    finally:
        cursor.close()
        conn.close()
    return -1

def getFormatDate():
    now = datetime.datetime.now()
    return now.strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    config=configparser.ConfigParser()
    config.read("cp.ini")
    logger.info("Initiate Cache")
    initCache()
    
    logger.info("Parse PP")
    thread1 = SearchPpProduct()
    thread1.start()
    
    app.run(host='0.0.0.0', port=config.get("server", "listen.port"))