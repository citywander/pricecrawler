import urllib.request
import json
import re
import copy
import time
import MySQLdb
import urllib.parse


docs = {}

add_pp = ("INSERT INTO pp "
              "(name, skuNames, linkUrl, price, monthPayments, months)"
              "VALUES (%(name)s, %(skuNames)s, %(linkUrl)s,  %(price)s, %(monthPayments)s, %(months)s)")

update_pp = ("UPDATE pp "
             "SET price=%(price)s, monthPayments= %(monthPayments)s, skuNames=%(skuNames)s, skuIds=%(skuIds)s "
             "WHERE id=%(id)s"
             )

def connect():
    return MySQLdb.connect(host="192.168.1.50", port=13306, user="root", passwd="Initial0",db="prodprice", charset='utf8')

def queryAll():
    cursor = db.cursor()
    query = ("SELECT id, linkUrl FROM pp")
    cursor.execute(query)
    for (idd, linkUrl) in cursor:
        docs[linkUrl]=idd
    cursor.close()

def searchPpProduct():
    url="https://mstore.ppdai.com/product/searchPro"
    pageIndex = 1;
    pageSize = 100
    while True:
        payload ={"pageIndex":pageIndex, "pageSize":pageSize,"name":""}
        proContent = getReponseFromPp(url, payload)
        totalPage = proContent["responseContent"]["totalPage"]
        prodList = proContent["responseContent"]["product004List"]
        for prod in prodList:
            prod["name"] = re.sub(u"(\u2018|\u2019|\xa0|\u2122)", "", prod["name"])
            del prod["pictureUrl"],prod["iconTypeName"],prod["hotWords"]
            prodId = prod["linkUrl"][9:]
            insertOrUpdateDB(prod)
            ppProdSku(prodId, prod)
        if pageIndex >= totalPage:
            break
        pageIndex = pageIndex + 1
    pass


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
                       "skuIds" :",".join(skuIds)}
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
            response = urllib.request.urlopen(request, timeout=10)
            responseContent = response.read()
            return json.loads(responseContent) 
        except:
            time.sleep(2)
    

def insertOrUpdateDB(doc, init = True):
    cursor = db.cursor()
    exist = doc["linkUrl"] in docs
    if exist and not init:
        result = docs[doc["linkUrl"]]
        data_pp = {
            'skuNames': doc["skuNames"],
            'skuIds': doc["skuIds"],
            'price': doc["price"],
            'monthPayments': doc["monthPayments"],
            'months': doc["months"],
            'id': result
        }
        print(data_pp)
        cursor.execute(update_pp, data_pp)
        db.commit()  
    elif not exist and init:
        data_pp = {
            'name': doc["name"],
            'skuNames': "",
            'linkUrl': doc["linkUrl"],
            'price': doc["price"],
            'monthPayments': doc["monthPayments"],
            'months': doc["months"]
        }
        print(data_pp)
        cursor.execute(add_pp, data_pp)
    db.commit()      
        
def jd(key):
    url="https://so.m.jd.com/ware/search.action?keyword=" + urllib.parse.quote(key)
    print(url)
    request = urllib.request.Request(url, headers={'content-type': 'application/json;charset=UTF-8', "Accept": "application/json"})
    response = urllib.request.urlopen(request)
    lines = response.readlines()
    for line in lines:
        strLine = line.decode("utf-8")
        if "searchData:" in strLine:
            prodList = strLine[strLine.index("searchData:") + len("searchData:"):strLine.index("abtestForUpToSaving") - 2]
            prods = json.loads(prodList)
            wareList = prods["wareList"]["wareList"]
            for ware in wareList:
                print(ware)
            break
    pass        

if __name__ == '__main__':
    db = connect()
    queryAll()
    searchPpProduct()