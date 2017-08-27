# -*- coding: utf-8 -*-
'''
@author: wagan
'''
import urllib.request
import json
import re
import copy
import flask
import time
import MySQLdb
import urllib.parse
from elasticsearch import Elasticsearch


def fetchMobile():
    url="https://www.taobao.com/market/3c/shouji.php"
    response = urllib.request.urlopen(url, {})
    print(response)
    pass

def readAliJson():
    fp = open('shouji.json','r') 
    vul = json.loads(fp.read())
    brands=[]    
    for op in vul["propertyList"][0]["propertyList"]:
        brand={}
        brand["keys"] = op["name"].split("/")
        brands.append(brand)
    pass
    print(brands)
    for item in vul["itemList"]:
        for brand in brands:
            for key in brand["keys"]:                
                if key in item["tip"]:
                    print(parseWords(item["tip"]))

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
            insertEs(prod)
            ppProdSku(prodId, prod)
        print(prodList)
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
        exist = True
        prodName = srcProdName
        for attributeValueId in attributeIds:
            attributeName = attributeNames[attributeValueId]["name"]
            if attributeName not in prodName:
                exist = False
                prodName = prodName.replace("{" + str(attributeValueIds[attributeValueId]) + "}", attributeName)
        if not exist:
            skuProd = {"name":prodName}
            print(prodName, getPrice(attributeIds, prodId)) 
        
def getDefaultName(crossIds, attributeNames, attributeValueIds, prodName):
    defaultName = prodName
    for attributeIds in crossIds:
        for attributeValueId in attributeIds:
            attributeName = attributeNames[attributeValueId]["name"]
            if attributeName in prodName:
                defaultName = defaultName.replace(attributeName, "{" + str(attributeValueIds[attributeValueId]) + "}")    
    return defaultName
    

def getPrice(attributeIds, prodId):

    url = "https://mstore.ppdai.com/product/getSkuProSimpleByAttr"
    payload = {"attributeValueIds":attributeIds, "productSkuId": prodId}
    proContent = getReponseFromPp(url, payload)
    return proContent["responseContent"]["price"]

    
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


es = Elasticsearch(hosts=[{'host': "172.17.4.203", 'port': 9200}])
docs = {}


def insertEs(doc):
    if doc["linkUrl"] in docs:
        pass
    else:
        es.index(index="pp", doc_type='prod', body=doc)

def queryAll():
    fromIndex = 0
    size = 500
    
    while True:
        results = es.search(index="pp", doc_type='prod', body=  {
            "from" : fromIndex, "size" : size,
        })
        for result in results["hits"]["hits"]:
            docs[result["_source"]["linkUrl"]] = result
        pass
        total = results["hits"]["total"]
        fromIndex = fromIndex + size
        if fromIndex > total:
            break    

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

def parseWords(tip):
    words=[]
    begin = 0
    end = 0 
    pre = ord(tip[0])
    for c in tip:
        if c in ['/', ' ','|']:
            words.append(tip[begin:end])
            end = end + 1   
            begin = end
        elif pre < 127 and ord(c) < 127:
            end = end + 1
        elif pre >= 127 and ord(c) >= 127:
            end = end + 1
        elif begin != end:
            words.append(tip[begin:end])
            begin = end
            end = end + 1
        else:
            end = end + 1
        pre = ord(c)
    return words


def connect():
    db=MySQLdb.connect(host="192.168.1.50", port=13306, user="root", passwd="Initial0",db="prodprice")
    c=db.cursor()
    c.execute("select * from product")

if __name__ == '__main__':
    #jd("Apple iPhone 7 Plus 32G 银色 移动联通电信4G手机 银色 32G PLUS")
    #connect()
    queryAll()
    searchPpProduct()