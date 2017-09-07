import MySQLdb
import configparser
import logging
import datetime
import time
import re
from threading import Timer, Lock

config=configparser.RawConfigParser()
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


def handleUserInput(content):
    if content == None:
        return None
    arr = []
    values = re.split(",| +", content)
    for val in values:
        if val == "":
            continue
        arr.append(val)
    return ",".join(arr)

class Periodic(object):

    def __init__(self, interval, function, *args, **kwargs):
        self._lock = Lock()
        self._timer = None
        self.function = function
        self.interval = interval
        self.args = args
        self.kwargs = kwargs
        self._stopped = True
        if kwargs.pop('autostart', True):
            self.start()

    def start(self, from_run=False):
        self._lock.acquire()
        if from_run or self._stopped:
            self._stopped = False
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self._lock.release()

    def _run(self):
        self.start(from_run=True)
        self.function(*self.args, **self.kwargs)

    def stop(self):
        self._lock.acquire()
        self._stopped = True
        self._timer.cancel()
        self._lock.release()