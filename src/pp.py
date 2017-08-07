'''
Created on 2017/08/03
@author: wagan
'''
import urllib.request
import json

def fetchCategoryList():
    url="http://mstore.ppdai.com/avtm/getIndexCategoryNav"
    response = urllib.request.urlopen(url, {})
    prodList = json.loads(response.read())["responseContent"]
    for prod in prodList:
        print(prod)
    pass

def queryJd(key):
    pass

def queryPp(key):
    pass



def searchProduct(search):
    url="https://mstore.ppdai.com/product/searchPro"
    payload = {"pageIndex": 1, "pageSize": 200, "name": "iphone 6"}
    params = json.dumps(payload).encode('utf8')
    request = urllib.request.Request(url, data=params,
                             headers={'content-type': 'application/json'})
    response = urllib.request.urlopen(request)
    print(response.read())
    

if __name__ == '__main__':
    fetchCategoryList()
    pass
