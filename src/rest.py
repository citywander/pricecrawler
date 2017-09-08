import json
import yaml
from flask import Flask, request, jsonify
from globUtils import getFormatDate
from scanner import scanPrice, docs
from globUtils import connectToDb, logger, handleUserInput, config

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = "application/json;charset=UTF-8"
app.config['LANGUAGES']="zh-CN"


add_search=("INSERT INTO search "
              "(keywords, e_keywords, o_keywords, description, is_auto, create_date, update_date) "
              "VALUES (%(keywords)s, %(e_keywords)s, %(o_keywords)s, %(description)s, %(is_auto)s, %(create_date)s, %(update_date)s)")

update_search=("UPDATE search "
              "set e_keywords=%(e_keywords)s, o_keywords=%(o_keywords)s, description=%(description)s, is_auto=%(is_auto)s,update_date=%(update_date)s "
              "where id=%(id)s")

add_price=("INSERT INTO price "
            "(product_id, search_id, url, src, description, seller, create_date,update_date) "
            "VALUES(%(product_id)s, %(search_id)s, %(url)s, %(src)s, %(description)s, %(seller)s, %(create_date)s, %(update_date)s)")

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

@app.route('/search', methods=['GET'])
def querySearch():
    logger.info("Get Search")
    keywords = request.args.get('keywords')
    likes = lambda key : " keywords like '%" + key +"%'" 
    query = "select s.id,keywords,e_keywords, s.description, p.id, p.description, price, seller, url, p.update_date, s.is_auto from search s left join price p on s.id=p.search_id"
    if not keywords is None:
        keywords = handleUserInput(keywords)
        likesQuery = list(map(likes, keywords.split(",")))
        query = query  + " where " + " and ".join(likesQuery)
        pass
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        results = {}
        for (sid, keywords, e_keywords, desc, pid, pdesc, price, seller, url, updateDate, is_auto) in cursor:
            if sid not in results:
                prices = []
                results[sid] = {"id":sid, "keywords" : keywords, "e_keywords": e_keywords, "description":desc, "prices":prices, "is_auto":is_auto}
            else:
                prices = results[sid]["prices"]
            if pid != None:
                prices.append({"id":pid, "description":pdesc, "price" : price, "seller" : seller, "url" : url, "updateDate" : updateDate})
    finally:
        cursor.close()
        conn.close()
    return jsonify(list(results.values()))


@app.route('/search/<path:searchId>', methods=['GET'])
def querySearchById(searchId):
    logger.info("Get Search by id " + str(searchId))
    keywords = request.args.get('keywords')
    query = "select s.id,keywords,e_keywords,o_keywords, s.description, p.id, p.description, price, seller, url, p.update_date, s.is_auto from search s left join price p on s.id=p.search_id where s.id=" + str(searchId)
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        results = {}
        prices = []
        empty = True
        for (sid, keywords, e_keywords,o_keywords, desc, pid, pdesc, price, seller, url, updateDate, is_auto) in cursor:
            empty = False
            results = {"id":sid, "keywords" : keywords, "e_keywords": e_keywords, "o_keywords": o_keywords, "description":desc, "prices":prices, "is_auto":is_auto}
            if pid != None:
                prices.append({"id":pid, "description":pdesc, "price" : price, "seller" : seller, "url" : url, "updateDate" : updateDate})
        if empty:
            return responseError("E0001", (searchId,))
    finally:
        cursor.close()
        conn.close()
    return jsonify(results)

@app.route('/search/<path:searchId>', methods=['PUT'])
def updateSearch(searchId):
    dbsearch = getSearchById(searchId)
    if dbsearch == None:
        return responseError("E0001", (searchId,))
    update_all_search=("UPDATE search "
              "set {COLS}, update_date=%(update_date)s "
              "where id=%(id)s")    
    search = request.json
    cols=[]
    data_search={}
    e_keywords=""
    o_keywords=""
    if "keywords" not in search:
        return responseError("E0002")
    keywords = handleUserInput(search["keywords"])
    cols.append("keywords=%(keywords)s")
    data_search["keywords"] = keywords
    if "e_keywords" in search:
        e_keywords = handleUserInput(search["e_keywords"])
    cols.append("e_keywords=%(e_keywords)s")
    data_search["e_keywords"] = e_keywords
    if "o_keywords" in search:
        o_keywords = handleUserInput(search["o_keywords"])
    cols.append("o_keywords=%(o_keywords)s")
    data_search["o_keywords"] = o_keywords
    
    if "description" in search:
        cols.append("description=%(description)s")
        data_search["description"] = search["description"]
    is_auto = dbsearch["is_auto"]
    if "is_auto" in search:
        cols.append("is_auto=%(is_auto)s")
        data_search["is_auto"] = search["is_auto"]
        is_auto = int(search["is_auto"])
                
    data_search["update_date"] = getFormatDate()
    data_search["id"] = searchId
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        update_all_search = update_all_search.replace("{COLS}", ",".join(cols))
        cursor.execute(update_all_search, data_search)
        conn.commit()
        
        if is_auto:
            scanPrice(keywords,e_keywords, o_keywords, searchId)
    except Exception as e:
        logger.error(str(e))
        return responseError("G0001", str(e))
    finally:
        cursor.close()
        conn.close()
    return querySearchById(searchId)

@app.route('/search', methods=['POST'])
def addSearch():
    search = request.json
    if "keywords" not in search:
        return responseError("E0002", ("keywords",))
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
    data_search = {
        'keywords': search["keywords"],
        'e_keywords': e_keywords,
        'o_keywords': o_keywords,
        'description': description,
        'is_auto': is_auto,
        "create_date": getFormatDate(),
        "update_date": getFormatDate()
    }
    searchId = compareKeywords(search["keywords"])
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
        scanPrice(search["keywords"],e_keywords, o_keywords, searchId)
        return querySearchById(searchId)
    except Exception as e:
        logger.error(str(e))
        return responseError("G0001", (), str(e)) 
    finally:
        cursor.close()
        conn.close()

@app.route('/price', methods=['POST'])
def addPrice():
    price = request.json
    if "search_id" not in price:
        return responseError("E0002", ("search_id",))
    search_id=price["search_id"]
    if "url" not in price:
        return responseError("E0002", ("url",))
    search = getSearchById(search_id)   
    if search == None:
        return responseError("E0001", (search_id,))
    if search["is_auto"] == 1:
        return responseError("E0005", "This search is handled by system" ,  404)
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
        else:
            price_data["id"] = priceId
            cursor.execute(update_price, price_data)
        conn.commit()
        priceId = cursor.lastrowid
        price_data["id"] = priceId
        return jsonify(price_data)        
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


@app.route('/price/<path:priceId>', methods=['DELETE'])
def deletePriceById(priceId):
    query=("Delete from price where id=" + priceId)
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

def compareKeywords(keywords):
    query = ("SELECT id, keywords FROM search where ")
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


@app.route('/api', methods=['GET'])
def api():
    with open("api.yaml", 'r') as stream:
        try:
            return jsonify(yaml.load(stream))
        except yaml.YAMLError as exc:
            print(exc)
    pass 
        
def responseError(errorCode, args, message=None):
    errorMsg = config.get("error", errorCode)
    msgs = errorMsg.split("-")
    if message != None:
        msgs[1] = message
    errorJson = {}
    errorJson["errorCode"] = errorCode
    errorJson["errorMsg"] = msgs[1]%args
    response = app.response_class(
        response=json.dumps(errorJson),
        status=int(msgs[0]),
        mimetype='application/json'
    )
    return response