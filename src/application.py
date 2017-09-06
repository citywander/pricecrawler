from rest import app
import re
from scanner import initCache
from scanner import SearchPpProduct
from scanner import retryScanAllPrice

from rest import app
from globUtils import logger
from globUtils import Periodic
from globUtils import config


if __name__ == '__main__':
    initCache()

    logger.info("Parse PP")
    thread1 = SearchPpProduct()
    thread1.start()
    
    rt = Periodic(int(config.get("server", "watch.interval")), retryScanAllPrice)
      
    app.run(host='0.0.0.0', port=config.get("server", "listen.port"))