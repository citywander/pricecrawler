'''
Created on 2017Äê8ÔÂ2ÈÕ

@author: wagan
'''
import scrapy
from scrapy.http import Request
from scrapy.spiders import CrawlSpider, Rule

class DmozSpider(scrapy.Spider):
    name = "dmoz"
    allowed_domains = ["dmoz.org"]
    start_urls = [
        "http://www.dmoz.org/Computers/Programming/Languages/Python/Books/",
        "http://www.dmoz.org/Computers/Programming/Languages/Python/Resources/",
        "https://mstore.ppdai.com/search#iphone 6"
    ]

    def parse(self, response):
        filename = response.url.split("/")[-2]
        with open(filename, 'wb') as f:
            f.write(response.body)

if __name__ == '__main__':
    pass
