'''
Created on 2017/08/03
@author: wagan
'''
import urllib.request
import urllib
import json


def searchProduct(search):
    url="https://mstore.ppdai.com/product/searchPro"
    payload = {"pageIndex": 1, "pageSize": 200, "name": "iphone 6"}
    params = json.dumps(payload).encode('utf8')
    request = urllib.request.Request(url, data=params,
                             headers={'content-type': 'application/json'})
    response = urllib.request.urlopen(request)
    res_body = response.read()
    print(res_body)

if __name__ == '__main__':
    searchProduct(None)
    pass
