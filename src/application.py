

if __name__ == '__main__':
    config=configparser.ConfigParser()
    config.read("cp.ini")
    initCache()

    logger.info("Parse PP")
    thread1 = SearchPpProduct()
    thread1.start()
    
    rt = Periodic(int(config.get("server", "watch.interval")), retryScanAllPrice)
      
    app.run(host='0.0.0.0', port=config.get("server", "listen.port"))