'''
@author: wagan
'''
import urllib.request
import json
import re

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

def searchProduct():
    url="https://mstore.ppdai.com/product/searchPro"
    pageIndex = 1;
    pageSize = 100
    while True:
        payload ={"pageIndex":pageIndex, "pageSize":pageSize,"name":""}
        params = json.dumps(payload).encode('utf8')
        request = urllib.request.Request(url, data=params,
                                 headers={'content-type': 'application/json;charset=UTF-8', "Accept": "application/json"})
        response = urllib.request.urlopen(request)
        responseContent = response.read()
        proContent = json.loads(responseContent)
        totalPage = proContent["responseContent"]["totalPage"]
        prodList = proContent["responseContent"]["product004List"]
        for prod in prodList:
            prod["name"] = re.sub(u"(\u2018|\u2019|\xa0|\u2122)", "", prod["name"])
            del prod["pictureUrl"],prod["iconTypeName"]
        print(prodList)
        if pageIndex >= totalPage:
            break
        pageIndex = pageIndex + 1
    pass

def jd():
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

if __name__ == '__main__':
    searchProduct()
    pass