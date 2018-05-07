from scanner import refresProductCache
from scanner import SearchPpProductThread
from scanner import searchPpProduct
from scanner import retryScanAllPrice

from rest import app
from globUtils import logger
from globUtils import Periodic
from globUtils import config


if __name__ == '__main__':
    refresProductCache()

    logger.info("Parse PP")
    thread1 = SearchPpProductThread()
    thread1.start()
    
    rt = Periodic(int(config.get("server", "watch.interval")), retryScanAllPrice)
    rt = Periodic(int(config.get("server", "watch.pp.interval")), searchPpProduct, True)

    port = config.get("server", "listen.port").strip()
    app.run(host='0.0.0.0', port=int(port))