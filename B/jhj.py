# coding:utf-8
import copy
import sys
import os
import time
import requests
from lxml import etree
from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import ElementNotInteractableException
import pymongo
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE_DIR))

from incre_web_crawler.constants import (USER_AGENT, RHEL7_URL,
                                         RHEL8_URL, REDHAT_DOMAIN,
                                         RHEL8_STORAGE_DIR, TODAY,
                                         RHEL7_STORAGE_DIR,
                                         LOGIN_URL, USERNAME,
                                         PASSWORD)
from incre_web_crawler.logger import Logger
from incre_web_crawler.utils import time_it, retry, dict2str
from incre_web_crawler.parse_config import get_config, update_config, get_current_time, update_start_crawl_time, \
    update_end_crawl_time, get_rhel_version

logger = Logger(log_name=r".\log\RedHatSpider.log", log_level=1, logger="RedHatSpider").get_log()


class IncrementalWebCrawler:
    """增量式RedHat爬虫"""

    def __init__(self, login_url, username, password):
        chrome_options = webdriver.ChromeOptions()
        # 静默模式
        chrome_options.add_argument('--headless')
        # 解决 ERROR:browser_switcher_service.cc(238) 报错,添加下面的试用选项
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--incognito')
        chrome_options.add_argument('--blink-settings=imagesEnabled=false')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('user-agent={useragent}'.format(useragent=USER_AGENT))
        self.driver = webdriver.Chrome(options=chrome_options)
        self.rhel7_base_url = RHEL7_URL
        self.rhel8_base_url = RHEL8_URL
        self.login_url = login_url
        self.username = username
        self.password = password
        self.failed_urls = list()
        # 是否是首次爬
        self.is_first = get_config()
        # 创建客户端
        self.client = pymongo.MongoClient(host='localhost', port=27017)
        self.ver_nos = list()
        self.urls = list()

    @retry(reNum=5)
    def login_red_website(self):
        """登录red网站"""
        try:
            self.driver.get(self.login_url)
        except Exception as e:
            raise e
        logger.info(f"login_title: {self.driver.title}")
        time.sleep(5)
        try:
            # 输入用户名
            self.driver.find_element_by_xpath("//div[@class='field']/input[@id='username']").send_keys(self.username)
            self.driver.find_element_by_xpath(
                '//div[@class="centered form-buttons"]/button[@class="centered button heavy-cta"]').click()
            time.sleep(2)

            # 输入密码
            self.driver.find_element_by_xpath("//div[@id='passwordWrapper']/input[@id='password']").send_keys(
                self.password)
            self.driver.find_element_by_xpath("//div[@id='kc-form-buttons']//input[@id='kc-login']").click()
            time.sleep(5)
        except ElementNotInteractableException as e:
            raise e

    # @retry(reNum=5)
    def get_all_rhel_urls(self, url):
        """获取所有下载链接"""
        try:
            self.driver.get(url)
        except Exception as e:
            logger.error(e)
        time.sleep(8)
        target_objs = self.driver.find_elements_by_xpath('//div[@class="option pull-left"][2]/select[@id="evr"]/option')
        version2urls = [{obj.get_attribute("text"): obj.get_attribute("value")} for obj in target_objs]
        if not version2urls:
            self.get_all_rhel_urls(url)

        return version2urls

    @retry(reNum=5)
    def get_target_page_cookie(self, url):
        """获取目标网页的cookie"""
        try:
            self.driver.get(url)
        except Exception as e:
            logger.error(e)
        rh_jwt = self.driver.get_cookie("rh_jwt")
        session = self.driver.get_cookie("_redhat_downloads_session")
        if all([rh_jwt, session]):
            logger.info(f"jwt: {rh_jwt}")
            logger.info(f"session: {session}")
            rh_jwt_value = rh_jwt["value"]
            session_value = session["value"]
            time.sleep(5)
            cookies = {
                "rh_user": "rd.sangfor|rd|P|",
                "rh_locale": "zh_CN",
                "rh_user_id": "51768269",
                "rh_sso_session": "1",
                "rh_jwt": rh_jwt_value,
                "_redhat_downloads_session": session_value
            }
            cookie_str = dict2str(cookies)
            return cookie_str
        else:
            logger.info(f"{url} 链接获取cookie失败,请重新获取")
            self.failed_urls.append(url)

    @retry(reNum=5)
    def save_target_data(self, cookie, target_url, filename):
        """保存数据"""
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": cookie,
        }
        session_obj = requests.Session()
        try:
            response = session_obj.get(target_url, headers=headers)
            wb_data = response.text
            html = etree.HTML(wb_data)
            need_data = html.xpath('//div[@class="changelog"]//text()')
            print("first element:{element}".format(element=need_data[0]))
            if need_data:
                with open(filename, "w", encoding="utf-8", errors="ignore") as fp:
                    for data in need_data:
                        fp.write(data)
        except Exception as e:
            print(e)

    def get_rhel8_latest_data(self):
        """爬取最新的rhel8"""

        # 先登录
        self.login_red_website()

        version2urls = self.get_all_rhel_urls(self.rhel8_base_url)
        url_suffix = [i for i in version2urls[0].values()][0]
        url = "".join([REDHAT_DOMAIN, url_suffix])
        ver_no = [i for i in version2urls[0].keys()][0]
        logger.info("===>>>开始爬取{ver_no}...".format(ver_no=ver_no))
        cookie = self.get_target_page_cookie(url)
        filename = "".join([RHEL8_STORAGE_DIR, str(TODAY), "-", ver_no, ".txt"])
        self.save_target_data(cookie, url, filename)
        logger.info("===>>>{ver_no}更新日志已保存".format(ver_no=ver_no))
        self.driver.quit()

    def get_rhel7_latest_data(self):
        """爬取最新的rhel7"""

        # 先登录
        self.login_red_website()
        version2urls = self.get_all_rhel_urls(self.rhel7_base_url)
        url_suffix = [i for i in version2urls[0].values()][0]
        url = "".join([REDHAT_DOMAIN, url_suffix])
        ver_no = [i for i in version2urls[0].keys()][0]
        logger.info("===>>>开始爬取{ver_no}...".format(ver_no=ver_no))
        cookie = self.get_target_page_cookie(url)
        filename = "".join([RHEL7_STORAGE_DIR, str(TODAY), "-", ver_no, ".txt"])
        self.save_target_data(cookie, url, filename)
        logger.info("===>>>{ver_no}更新日志已保存".format(ver_no=ver_no))
        self.driver.quit()

    def save_url_to_mongodb(self, items, rhel_ver):
        """将url保存至mongodb"""
        logger.info(f"pymongo version: {pymongo.version}")
        # 指定数据库,如果没有则会自动创建
        db = self.client.redhat
        if rhel_ver == "rhel8":
            # 集合:就是数据表的概念
            collection = db.centos8_table
        else:
            # 有,修改,没有,创建
            collection = db.centos7_table

        datas = list()
        for ver_no, url in items:
            # mongo会自动创建id, 不需要自己创建
            # url_id = uuid.uuid4().__str__()
            data = {
                # "id": url_id,
                "ver_no": ver_no,
                "url": url,
            }
            datas.append(data)
        try:
            collection.insert_many(datas)
        except TypeError as ex:
            logger.error(ex)

    def query_url_by_kw(self, url, ver_no):
        """根据关键字查询mongodb中的url"""
        # 指定数据库,如果没有则会自动创建
        db = self.client.redhat
        collection = db.centos8_table
        item = {
            "url": url,
            "ver_no": ver_no
        }
        db_data = collection.find_one(item)
        return db_data

    def query_all_db_objs(self, rhel_ver):
        """查询所有的mongodb对象"""
        try:
            db = self.client.redhat
            if rhel_ver == "rhel8":
                collection = db.centos8_table
            else:
                collection = db.centos7_table
            db_objs = collection.find()
        except Exception as ex:
            logger.error(ex)
        else:
            return db_objs

    def query_all_ver_nos(self, rhel_ver):
        """查询所有ver_no"""
        db_objs = self.query_all_db_objs(rhel_ver)
        ver_nos = list()
        for obj in db_objs:
            ver_no = [i for i in obj.values()][1]
            ver_nos.append(ver_no)
        return ver_nos

    def get_rhel_urls(self, rhel_ver):
        """获取rhel所有url"""
        # 先登录,登录后携带cookie进行抓取数据
        self.login_red_website()
        if rhel_ver == "rhel8":
            version2urls = self.get_all_rhel_urls(self.rhel8_base_url)
        else:
            version2urls = self.get_all_rhel_urls(self.rhel7_base_url)

        for item in version2urls:
            url_suffix = [i for i in item.values()][0]
            ver_no = [i for i in item.keys()][0]
            url = "".join([REDHAT_DOMAIN, url_suffix])
            self.ver_nos.append(ver_no)
            self.urls.append(url)

        # 实际上只存ver_no即可
        # item = {ver_no:url}  这种数据结构更好一点
        # 下面这种递归慎用
        # if all([ver_nos, urls]):
        #     return zip(ver_nos, urls)
        # else:
        #     self.get_rhel8_urls()
        logger.info(self.ver_nos)
        # 不需要了,直接下面调用self.urls即可
        # if self.ver_nos and self.urls:
        #     obj = zip(self.ver_nos, self.urls)
        #     return obj
        # else:
        #     import pdb;pdb.set_trace()
        #     return False

    def craw_data(self, items, save_path):
        """抓取并保存数据"""
        for ver_no, url in items:
            # 非首次爬
            # 将url和mongodb中的进行对比
            # db_data = self.query_url_by_kw(url, ver_no)
            # if not db_data:
            # 说明这一条url是最新的,只爬取这一条
            # 处理的不好,使用集合进行去重,差集的处理更好
            logger.info("===>>>开始爬取{ver_no}...".format(ver_no=ver_no))
            cookie = self.get_target_page_cookie(url)
            filename = "".join([save_path, str(TODAY), "-", ver_no, ".txt"])
            self.save_target_data(cookie, url, filename)
            logger.info("===>>>{ver_no}更新日志已保存".format(ver_no=ver_no))
            time.sleep(5)

        # 注意这个driver退出的位置
        self.driver.quit()

    def get_latest_rhel_data(self, items, save_path):
        """爬取最新的"""
        self.craw_data(items, save_path)

    def get_all_rhel_data(self, rhel_ver):
        """爬取所有rhel的数据"""
        if rhel_ver == "rhel8":
            save_path = RHEL8_STORAGE_DIR
        else:
            save_path = RHEL7_STORAGE_DIR

        self.get_rhel_urls(rhel_ver)
        # items = zip(self.ver_nos, self.urls)
        # 取出网页爬取的真实url-ver_no
        objs = [(ver_no, url) for ver_no, url in zip(self.ver_nos, self.urls)]
        ver_nos = list()
        for obj in objs:
            ver_no = obj[0]
            ver_nos.append(ver_no)

        if self.is_first == "false":
            # 这里的问题:查询的时候应该根据指定的版本号去对应的表查询
            db_ver_nos = self.query_all_ver_nos(rhel_ver)
            logger.info(f"当前网页的版本号: {ver_nos}")
            logger.info(f"数据库中已有版本号: {db_ver_nos}")
            # 取差集
            latest_ver_nos = list(set(ver_nos) - set(db_ver_nos))
            logger.info(f"最新的版本号: {latest_ver_nos}")
            latest_items = [obj for obj in objs if obj[0] in latest_ver_nos]
            logger.info(objs)
            logger.info(f"最新的版本号和url链接: {latest_items}")
            # 后续爬取的就是差集部分这些
            # 然后爬完也要把数据存入mongodb
            self.get_latest_rhel_data(latest_items, save_path)
            self.save_url_to_mongodb(latest_items, rhel_ver)
            return

        self.craw_data(zip(self.ver_nos, self.urls), save_path)
        # if self.failed_urls:
        #     self.get_lost_data()
        # import pdb
        # pdb.set_trace()
        # 第一次爬完,将url存入mongodb
        self.save_url_to_mongodb(zip(self.ver_nos, self.urls), rhel_ver)
        # 标识量置为False,但是再次执行脚本,这里还是会为True, 无法持久化保存
        # 所以:办法 1、存入数据库这个变量 2、存入配置文件
        self.is_first = "false"
        update_config(self.is_first)

    def get_all_rhel7_data(self):
        """爬取所有rhel7的数据"""

        # 先登录
        self.login_red_website()
        version2urls = self.get_all_rhel_urls(self.rhel7_base_url)

        for item in version2urls:
            url_suffix = [i for i in item.values()][0]
            url = "".join([REDHAT_DOMAIN, url_suffix])
            ver_no = [i for i in item.keys()][0]
            logger.info("===>>>开始爬取{ver_no}...".format(ver_no=ver_no))
            cookie = self.get_target_page_cookie(url)
            filename = "".join([RHEL7_STORAGE_DIR, str(TODAY), "-", ver_no, ".txt"])
            self.save_target_data(cookie, url, filename)
            logger.info("===>>>{ver_no}更新日志已保存".format(ver_no=ver_no))
            time.sleep(5)
        self.driver.quit()
        logger.info("============开始爬取失败的url==========================")
        if self.failed_urls:
            self.get_lost_data()

    def get_lost_data(self):
        """爬取丢失的数据"""
        if self.failed_urls:
            self.login_red_website()
            for url in self.failed_urls:
                ver_no = url.split("/")[-4]
                logger.info("===>>>开始爬取{ver_no}...".format(ver_no=ver_no))
                cookie = self.get_target_page_cookie(url)
                filename = "".join([RHEL7_STORAGE_DIR, str(TODAY), "-", ver_no, ".txt"])
                self.save_target_data(cookie, url, filename)
                logger.info("===>>>{ver_no}更新日志已保存".format(ver_no=ver_no))
                time.sleep(5)
            self.driver.quit()
        else:
            pass


@time_it
def main():
    red_spider = IncrementalWebCrawler(LOGIN_URL, USERNAME, PASSWORD)
    rhel_ver = get_rhel_version()
    red_spider.get_all_rhel_data(rhel_ver)
    # red_spider.get_lost_data()


if __name__ == '__main__':
    start_time = get_current_time()
    update_start_crawl_time(start_time)
    main()
    end_time = get_current_time()
    update_end_crawl_time(end_time)



