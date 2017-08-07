'''
@author: wagan
'''
import urllib.request
import 

def fetchMobile():
    url="https://www.taobao.com/market/3c/shouji.php"
    response = urllib.request.urlopen(url, {})
    print(response)
    pass

if __name__ == '__main__':
    fetchMobile()
    pass