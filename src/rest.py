import json
import yaml
from flask import Flask, request, jsonify
from globUtils import getFormatDate
from scanner import scanPrice, docs, getReponseFromPp, insertOrUpdateDB, matchKeywords
from globUtils import connectToDb, logger, handleUserInput, config

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = "application/json;charset=UTF-8"
app.config['LANGUAGES']="zh-CN"


add_search=("INSERT INTO search "
              "(keywords, e_keywords, o_keywords, description, product_id, is_auto, international, create_date, update_date) "
              "VALUES (%(keywords)s, %(e_keywords)s, %(o_keywords)s, %(description)s, %(product_id)s, %(is_auto)s, %(international)s, %(create_date)s, %(update_date)s)")

update_search=("UPDATE search "
              "set keywords=%(keywords)s, e_keywords=%(e_keywords)s, o_keywords=%(o_keywords)s, description=%(description)s, is_auto=%(is_auto)s, international=%(international)s, update_date=%(update_date)s "
              "where id=%(id)s")

add_price=("INSERT INTO price "
            "(product_id, search_id, url, src, description, seller, is_input, create_date,update_date) "
            "VALUES(%(product_id)s, %(search_id)s, %(url)s, %(src)s, %(description)s, %(seller)s, %(is_input)s, %(create_date)s, %(update_date)s)")

update_price=("UPDATE price "
              "set url=%(url)s, seller=%(seller)s, update_date=%(update_date)s "
              "WHERE id=%(id)s")


@app.route('/search/<path:searchId>', methods=['DELETE'])
def deleteSearch(searchId):
    query1=("Delete from search where id=" + searchId)
    query2=("Delete from price where search_id=" + searchId)
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
    return ('', 204)



@app.route('/search/avg', methods=['GET'])
def querySearchAvg():
    expand = request.args.get('expand')
    expand = request.args.get('expand')
    isExpand = False
    if expand != None and expand.strip().lower() == "true":
        isExpand = True    
    query='''
        select s.id,keywords,e_keywords,o_keywords, s.description, p.id, p.description, price, seller, url, p.product_id, p.update_date, s.is_auto, p.is_input,s.min_price,s.max_price,s.avg_price
        from search s left join price p on s.id=p.search_id
        where p.product_id in(
        select product_id from price p where seller='%s' and price <= (select avg(price) from price pr where pr.search_id=p.search_id and price!=9999 and price!=99999 and seller!='%s'))    
    '''
    weiya=config.get("words", "weiya")
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        query = query%(weiya, weiya)
        cursor.execute(query)
        results = handleSearchResults(cursor)
    finally:
        cursor.close()
        conn.close()
    return jsonify(list(results.values()))       

@app.route('/search/min', methods=['GET'])
def querySearchMin():
    expand = request.args.get('expand')
    isExpand = False
    if expand != None and expand.strip().lower() == "true":
        isExpand = True
    query='''
        select s.id,keywords,e_keywords,o_keywords, s.description, p.id, p.description, price, seller, url, p.product_id, p.update_date, s.is_auto, p.is_input,s.min_price,s.max_price,s.avg_price
        from search s left join price p on s.id=p.search_id
        where p.product_id in(
        select product_id from price p where seller='%s' and price <= (select min(price) from price pr where pr.search_id=p.search_id and price!=9999 and price!=99999 and seller!='%s'))    
    '''
    weiya=config.get("words", "weiya")
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        query = query%(weiya, weiya)
        cursor.execute(query)
        results = handleSearchResults(cursor)
    finally:
        cursor.close()
        conn.close()
    return jsonify(list(results.values()))    

@app.route('/search', methods=['GET'])
def querySearch():
    logger.info("Get Search")
    keywords = request.args.get('keywords')
    likes = lambda key : " keywords like '%" + key +"%'"
    weiya=config.get("words", "weiya")
    query = "select s.id,keywords,e_keywords,o_keywords, s.description, p.id, p.description, price, seller, url, p.product_id, p.update_date, s.is_auto, p.is_input,s.min_price,s.max_price,s.avg_price from search s left join price p on s.id=p.search_id and p.seller='" +weiya + "'"
    hasWhere = False
    if not keywords is None:
        keywords = handleUserInput(keywords)
        likesQuery = list(map(likes, keywords.split(",")))
        query = query  + "where " + " and ".join(likesQuery)
        hasWhere = True
        pass
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        results = handleSearchResults(cursor)
    finally:
        cursor.close()
        conn.close()
    return jsonify(list(results.values()))

@app.route('/search/product/<path:product_id>', methods=['GET'])
def querySearchByProductId(product_id):
    logger.info("Get Search")
    keywords = request.args.get('keywords')
    likes = lambda key : " keywords like '%" + key +"%'" 
    query = "select s.id,keywords,e_keywords,o_keywords, s.description, p.id, p.description, price, seller, url, p.product_id, p.update_date, s.is_auto, p.is_input,s.min_price,s.max_price,s.avg_price  from search s left join price p on s.id=p.search_id "
    if product_id:
        query = query + " where s.product_id=" + str(product_id)  
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        results = handleSearchResults(cursor, expand=True)
        if len(results) == 0:
            return responseError("E0003",(product_id, ))
    finally:
        cursor.close()
        conn.close()
    return jsonify(list(results.values())[0])    

@app.route('/search/<path:searchId>', methods=['GET'])
def querySearchById(searchId):
    logger.info("Get Search by id " + str(searchId))
    weiya=config.get("words", "weiya")
    query = "select s.id,keywords,e_keywords,o_keywords, s.description, p.id, p.description, price, seller, url, p.product_id, p.update_date, s.is_auto, p.is_input,s.min_price,s.max_price,s.avg_price from search s left join price p on s.id=p.search_id where s.id=" + str(searchId)
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        results = handleSearchResults(cursor, expand=True)
    finally:
        cursor.close()
        conn.close()
    return jsonify(results[int(searchId)])


def handleSearchResults(cursor, expand=False):
    results = {}
    weiya=config.get("words", "weiya")
    for (sid, keywords, e_keywords,o_keywords, desc, pid, pdesc, price, seller, url, product_id, updateDate, is_auto, is_input, min_price,max_price,avg_price) in cursor:
        if sid not in results:
            prices = []
            results[sid] = {"id":sid, "keywords" : keywords, "e_keywords": e_keywords, "description":desc, "prices":prices, "is_auto":is_auto, "min" : min_price, "max":max_price, "avg" : avg_price}
        else:
            prices = results[sid]["prices"]
        if pid == None:
            continue
        if weiya == seller:
            refPrice={"id":pid, "description":pdesc, "price" : price, "seller" : seller, "url" : url, "product_id":product_id, "updateDate" : updateDate}
            results[sid]["target"]=refPrice
        else:           
            prices.append({"id":pid, "description":pdesc, "price" : price, "seller" : seller, "url" : url, "product_id":product_id, "updateDate" : updateDate, "is_input":is_input})
    
    for value in results.values():
        if not expand:
            del value["prices"]
    return results 

@app.route('/search', methods=['POST'])
def addSearch():
    search = request.json
    if "keywords" not in search:
        return responseError("E0002", ("keywords",))
    if "product_id" in search:
        product_id = search["product_id"]
        url = "/product/" + product_id        
    else:
        if "url" not in search:
            return responseError("E0004")
        else:
            url = search["url"]
            product_id = url[url.rindex("/") + 1:]
            url = "/product/" + product_id       
        
    if not newPp(product_id):
        return responseError("E0003",(product_id,))
    description = None
    if "description" in search:
        description = search["description"]
    e_keywords = None
    o_keywords = None
    if "e_keywords" in search:
        e_keywords = handleUserInput(search["e_keywords"])
    if "o_keywords" in search:
        o_keywords = handleUserInput(search["o_keywords"])
    is_auto = 1
    if "is_auto" in search:
        if search["is_auto"] != 0 or search["is_auto"] != "0":
            is_auto = 0                  
    search["keywords"] = handleUserInput(search["keywords"])
    huiyaDescription=docs[product_id]["name"]
    if not matchKeywords(huiyaDescription, search["keywords"], e_keywords, o_keywords):
        return responseError("E0005", (search["keywords"],))
    
    international = 1
    if "international" in search and search["international"] == 0:
        international = 0
        
    data_search = {
        "product_id":product_id,
        'keywords': search["keywords"],
        'e_keywords': e_keywords,
        'o_keywords': o_keywords,
        'description': description,
        'is_auto': is_auto,
        'international': international,
        "create_date": getFormatDate(),
        "update_date": getFormatDate()
    }
    searchId = getSearchByProductId(product_id)
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        if searchId == -1:
            cursor.execute(add_search, data_search)
            searchId = cursor.lastrowid
            data_search["id"] = searchId
        else:
            data_search["id"] = searchId
            cursor.execute(update_search, data_search)
        conn.commit()
        scanPrice(product_id, search["keywords"],e_keywords, o_keywords, searchId, international)
        return querySearchById(searchId)
    except Exception as e:
        logger.error(str(e))
        return responseError("G0001", (), str(e)) 
    finally:
        cursor.close()
        conn.close()
        
def newPp(product_id):
    if product_id in docs:
        return True
    url="https://mstore.ppdai.com/product/getSkuProDeatils"    
    payload = {"productSkuId": product_id}
    res = getReponseFromPp(url, payload)  
    sku=res["responseContent"]
    if sku is None:
        return False
    url = "https://mstore.ppdai.com/product/getAttribute"
    payload = {"productSkuId": product_id}
    proContent = getReponseFromPp(url, payload)
    attrs={}
    for attributes in proContent["responseContent"]:
        for attribute in attributes["attributeList"]:
            attrs[attribute["attributeValueId"]] = attribute["attributeValue"]
    skuNames=[]
    skuIds=[]
    for (valueId, value) in attrs.items():
        if value in sku["skuName"]:
            skuNames.append(value)
            skuIds.append(str(valueId))
    skuProd = {"name":sku["proName"], "linkUrl": "/product/" + product_id, "price":sku["price"], 
           "monthPayments": str(sku["monthPayments"]), 
           "months":str(sku["months"]),
           "skuNames" :",".join(skuNames),
           "skuIds" :",".join(skuIds),
           "seller": sku["seller"]}
    insertOrUpdateDB(skuProd)
    return True    

@app.route('/search/<path:search_id>/price', methods=['POST'])
def addPrice(search_id):
    price = request.json
    if "url" not in price:
        return responseError("E0002", ("url",))
    search = getSearchById(search_id)   
    if search == None:
        return responseError("E0001", (search_id,))
    src = "pp"
    url = price["url"]
    seller=None
    description = None
    if "seller" in price:
        seller = price["seller"]        
    if "jd" in url:
        product_id = url[url.rindex("/") + 1:url.rindex(".")]
        src = "jd"
        seller = "jd"
    else:
        product_id = url[url.rindex("/") + 1:]
    if src=='pp' and not product_id in docs:
        return responseError("E0006", "This url can't be found in paipai" ,  404)
    if src == 'pp':
        seller = docs[product_id]["seller"]
        description = docs[product_id]["name"]
    price_data={
        "product_id" : product_id,
        "search_id" : search_id,
        "url": url,
        "seller" : seller,
        "description" : description,
        "is_input" : 1,
        "src":src,
        "create_date": getFormatDate(),
        "update_date": getFormatDate()        
    }
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        priceId = getPriceByProduct(cursor, product_id, search_id)
        if priceId == -1:
            cursor.execute(add_price, price_data)
            priceId = cursor.lastrowid
        else:
            price_data["id"] = priceId
            cursor.execute(update_price, price_data)
        conn.commit()
        return querySearchById(search_id)
    except Exception as e:
        logger.error(str(e))
        return responseError("G0001", (), str(e)) 
    finally:
        cursor.close()
        conn.close()    
    pass


def getPriceByProduct(cursor, product_id, search_id):    
    query = ("SELECT id FROM price where search_id=" + str(search_id) + " and product_id=" + str(product_id))
    cursor.execute(query)
    for (priceId, ) in cursor:
        return priceId
    return -1


@app.route('/search/<path:search_id>/price/<path:price_id>', methods=['DELETE'])
def deletePriceById(search_id, price_id):
    query=("Delete from price where id=" + price_id)
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    pass
    return ('', 204)

def getSearchById(searchId):
    logger.info("Get Search by id " + str(searchId))
    query = "select id, is_auto from search where id=" + str(searchId)
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        for (searchId, is_auto) in cursor:
            return {"id" : searchId, "is_auto":is_auto}
        return None
    finally:
        cursor.close()
        conn.close()

def getSearchByProductId(product_id):
    query = ("SELECT id FROM search where product_id=" + product_id)
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        for (idd, ) in cursor:
            return idd;
    finally:
        cursor.close()
        conn.close()
    return -1


@app.route('/api', methods=['GET'])
def api():
    with open("api.yaml", 'r') as stream:
        try:
            return jsonify(yaml.load(stream))
        except yaml.YAMLError as exc:
            print(exc)
    pass 
        
def responseError(errorCode, args=None, message=None):
    errorMsg = config.get("error", errorCode)
    msgs = errorMsg.split("-")
    if message != None:
        msgs[1] = message
    errorJson = {}
    errorJson["errorCode"] = errorCode
    if args:
        errorJson["errorMsg"] = msgs[1]%args
    else:
        errorJson["errorMsg"] = msgs[1]
    response = app.response_class(
        response=json.dumps(errorJson),
        status=int(msgs[0]),
        mimetype='application/json'
    )
    return response