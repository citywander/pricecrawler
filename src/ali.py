'''
@author: wagan
'''
import urllib.request
import json


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
                    print(key)

def parseWords():
    pass

if __name__ == '__main__':
    readAliJson()
    pass