import MySQLdb
import json
import threading
from threading import Timer, Lock
from flask import Flask, request
from globUtils import getFormatDate
from globUtils import connectToDb, logger, retry

app = Flask(__name__)

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
    return app.response_class(
            response=json.dumps({"result": "ok"}),
            status=200,
            mimetype='application/json'
    )

@app.route('/search', methods=['GET'])
def querySearch():
    keywords = request.args.get('keywords')
    likes = lambda key : " name like '%" + key +"%'" 
    query = "select keywords,e_keywords, description, price, seller, url, update_date from search pd, price p where pd.id=p.search_id"
    if not keywords is None:
        likesQuery = list(map(likes, keywords.split(",")))
        query = query + " and ".join(likesQuery.split(","))
        pass
    pass

@app.route('/search/<path:searchId>', methods=['PUT'])
def updateSearch(searchId):
    update_all_search=("UPDATE search "
              "set {COLS}, update_date=%(update_date)s "
              "where id=%(id)s")    
    search = request.json
    cols=[]
    data_search={}
    ekeywords=""
    if "keywords" not in search:
        errorJson={}
        errorJson["errorCode"] = "E003"
        errorJson["errorMsg"] = "keywords is required"
        return responseError(errorJson, 400)
    keywords = search["keywords"]
    cols.append("keywords=%(keywords)s")
    data_search["keywords"] = search["keywords"]
    if "ekeywords" in search:
        ekeywords = search["ekeywords"]
        cols.append("e_keywords=%(e_keywords)s")
        data_search["e_keywords"] = search["ekeywords"]
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
        st = threading.Thread(target=scanPrice, args=(keywords,ekeywords, searchId))
        st.start()        
    except Exception as e:
        errorJson= {}
        errorJson["errorCode"] = "E004"
        errorJson["errorMsg"] = str(e)
        return responseError(errorJson, 400)         
    finally:
        cursor.close()
        conn.close()
    return app.response_class(
            response=json.dumps({"result": "ok"}),
            status=200,
            mimetype='application/json'
    )    

@app.route('/search', methods=['POST'])
def addSearch():
    search = request.json
    errorJson = {}
    if "keywords" not in search:
        errorJson["errorCode"] = "E001"
        errorJson["errorMsg"] = "keywords is requried"
        return responseError(errorJson, 400)
    description = None
    if "description" in search:
        description = search["description"]
    ekeywords = None
    if "ekeywords" in search:
        ekeywords = search["ekeywords"] 
    data_search = {
        'keywords': search["keywords"],
        'e_keywords': ekeywords,
        'description': description,
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
        else:
            data_search["id"] = searchId
            cursor.execute(update_search, data_search)
        conn.commit()
        st = threading.Thread(target=scanPrice, args=(search["keywords"],ekeywords, searchId))
        st.start()
        return app.response_class(
            response=json.dumps({"result": "ok"}),
            status=200,
            mimetype='application/json'
        )
    except Exception as e:
        errorJson["errorCode"] = "E002"
        errorJson["errorMsg"] = str(e)
        return responseError(errorJson, 400) 
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
        
def responseError(errorMsg, statusCode):
    response = app.response_class(
        response=json.dumps(errorMsg),
        status=statusCode,
        mimetype='application/json'
    )
    return response