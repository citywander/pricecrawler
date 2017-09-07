import json
import threading
from flask import Flask, request, jsonify
from globUtils import getFormatDate
from scanner import scanPrice
from globUtils import connectToDb, logger, handleUserInput

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = "application/json;charset=UTF-8"
app.config['LANGUAGES']="zh-CN"


add_search=("INSERT INTO search "
              "(keywords, e_keywords, o_keywords, description, is_auto, create_date, update_date) "
              "VALUES (%(keywords)s, %(e_keywords)s, %(o_keywords)s, %(description)s, %(create_date)s, %(update_date)s)")

update_search=("UPDATE search "
              "set e_keywords=%(e_keywords)s, o_keywords=%(o_keywords)s, description=%(description)s, is_auto=%(is_auto)s,update_date=%(update_date)s "
              "where id=%(id)s")

add_price=("INSERT INTO price "
            "(product_id, search_id, src, seller, create_date,update_date) "
            "VALUES(%(product_id)s, %(search_id)s, %(src)s, %(seller)s, %(create_date)s, %(update_date)s)")


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
    query = "select s.id,keywords,e_keywords, s.description, p.id, p.description, price, seller, url, p.update_date from search s, price p where s.id=p.search_id"
    if not keywords is None:
        keywords = handleUserInput(keywords)
        likesQuery = list(map(likes, keywords.split(",")))
        query = query  + " and " + " and ".join(likesQuery)
        pass
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        results = {}
        for (sid, keywords, e_keywords, desc, pid, pdesc, price, seller, url, updateDate) in cursor:
            if sid not in results:
                prices = []
                results[sid] = {"id":sid, "keywords" : keywords, "e_keywords": e_keywords, "description":desc, "prices":prices}
            else:
                prices = results[sid]["prices"]
            prices.append({"id":pid, "description":pdesc, "price" : price, "seller" : seller, "url" : url, "updateDate" : updateDate})
    finally:
        cursor.close()
        conn.close()
    return jsonify(list(results.values()))


@app.route('/search/<path:searchId>', methods=['GET'])
def querySearchById(searchId):
    logger.info("Get Search by id " + searchId)
    keywords = request.args.get('keywords')
    query = "select s.id,keywords,e_keywords, s.description, p.id, p.description, price, seller, url, p.update_date from search s, price p where s.id=p.search_id and s.id=" + searchId
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        results = {}
        prices = []
        for (sid, keywords, e_keywords, desc, pid, pdesc, price, seller, url, updateDate) in cursor:
            results = {"id":sid, "keywords" : keywords, "e_keywords": e_keywords, "description":desc, "prices":prices}
            prices.append({"id":pid, "description":pdesc, "price" : price, "seller" : seller, "url" : url, "updateDate" : updateDate})
    finally:
        cursor.close()
        conn.close()
    return jsonify(results)

@app.route('/search/<path:searchId>', methods=['PUT'])
def updateSearch(searchId):
    update_all_search=("UPDATE search "
              "set {COLS}, update_date=%(update_date)s "
              "where id=%(id)s")    
    search = request.json
    cols=[]
    data_search={}
    e_keywords=""
    o_keywords=""
    if "keywords" not in search:
        return responseError("E003", "keywords is required" ,  404)
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
    data_search["update_date"] = getFormatDate()
    data_search["id"] = searchId
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        update_all_search = update_all_search.replace("{COLS}", ",".join(cols))
        cursor.execute(update_all_search, data_search)
        conn.commit()
        st = threading.Thread(target=scanPrice, args=(keywords,e_keywords, o_keywords, searchId))
        st.start()        
    except Exception as e:
        return responseError("E004", str(e),  400)
    finally:
        cursor.close()
        conn.close()
    return jsonify(data_search)

@app.route('/search', methods=['POST'])
def addSearch():
    search = request.json
    if "keywords" not in search:
        return responseError("E003", "keywords is required" ,  404)
    description = None
    if "description" in search:
        description = search["description"]
    e_keywords = None
    if "e_keywords" in search:
        e_keywords = handleUserInput(search["e_keywords"])
    if "o_keywords" in search:
        o_keywords = handleUserInput(search["o_keywords"])
    is_auto = 0
    if "is_auto" in search:
        is_auto = search["is_auto"] != 0 or search["is_auto"] != "0"                  
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
        st = threading.Thread(target=scanPrice, args=(search["keywords"],e_keywords, o_keywords, searchId))
        st.start()
        return jsonify(data_search)
    except Exception as e:
        return responseError("E002", str(e),  400) 
    finally:
        cursor.close()
        conn.close()

@app.route('/price', methods=['POST'])
def addPrice():
    price = request.json
    if "search_id" not in price:
        return responseError("E0001", "search_id is required" ,  404)
    if "url" not in price:
        return responseError("E0002", "url is required" ,  404)
    if "seller" not in price:
        return responseError("E0003", "seller is required" ,  404)    
    search = getSearchById(price["search_id"])   
    if search == None:
        return responseError("E0004", "search can't be found" ,  404)
    if search["is_auto"] == 1:
        return responseError("E0005", "This search is handled by system" ,  404)
    src = "pp"
    url = price["url"]
    if "jd" in url:
        src = "jd"
    product_id = url[url.rindex("/") + 1:url.rindex(".")]
    price_data={
        "product_id" : product_id,
        "search_id" : price["search_id"],
        "url": url,
        "src":src,
        "create_date": getFormatDate(),
        "update_date": getFormatDate()        
    }
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        if searchId == -1:
            cursor.execute(add_price, price_data)
            searchId = cursor.lastrowid
            price_data["id"] = searchId
        else:
            price_data["id"] = searchId
            cursor.execute(update_search, price_data)
        conn.commit()
    except Exception as e:
        return responseError("E002", str(e),  400) 
    finally:
        cursor.close()
        conn.close()    
    pass


def getSearchById(searchId):
    logger.info("Get Search by id " + searchId)
    query = "select id, is_auto from search id=" + searchId
    try:
        conn = connectToDb()
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        return row
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
        
def responseError(errorCode, errorMsg, statusCode):
    errorJson = {}
    errorJson["errorCode"] = errorCode
    errorJson["errorMsg"] = errorMsg
    response = app.response_class(
        response=json.dumps(errorMsg),
        status=statusCode,
        mimetype='application/json'
    )
    return response