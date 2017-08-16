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
                    print(parseWords(item["tip"]))

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
    readAliJson()
    pass