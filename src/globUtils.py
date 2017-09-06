import MySQLdb
import configparser
import logging
import datetime

config=configparser.ConfigParser()
config.read("cp.ini")

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger = logging.getLogger('ComparePrice')
logger.setLevel(logging.DEBUG)
logger.addHandler(ch)

def connectToDb():
    while True:
        try: 
            host=config.get("db","host")
            port=int(config.get("db","port"))
            user=config.get("db","user")
            pwd=config.get("db","pwd")
            return MySQLdb.connect(host=host, port=port, user=user, passwd=pwd, db="prodprice", charset='utf8')
        except Exception as e:
            logger.error(e)
            time.sleep(2)


def retry(func, *args, **kwargs):
    while True:
        try:
            func(*args, **kwargs)
            break
        except Exception as e:
            time.sleep(5)
            logger.error(e)
    pass


def getFormatDate():
    now = datetime.datetime.now()
    return now.strftime('%Y-%m-%d %H:%M:%S')