import os.path
from playwright.sync_api import Playwright, sync_playwright, expect
import logging
import requests

work_dir = '../pacong_data/'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO,
                    filename='log.txt', filemode='a', encoding='utf-8')


def download(url, page3, dir):
    u = url.split('/')
    u = u[-1]
    if '.' in u:
        try:
            dir1 = dir + url.split('/')[-1]
            response = requests.get(url)
            with open(dir1, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB per chunk
                    if chunk:
                        f.write(chunk)
        except Exception as e:
            logging.error(e)
            logging.error(f'下载失败：{url}')
        return

    links = page3.locator('xpath=//table/tbody/tr').all()[3:-1]
    num = len(links)
    i = 0

    if num == 0:
        page3.go_back(timeout=0)
        return

    for link in links:
        i = i + 1
        dir1 = dir + link.get_by_role('link').get_attribute('href', timeout=0)
        link = url + link.get_by_role('link').get_attribute('href', timeout=0)
        fp = link.split('/')[-1]
        if '.' not in fp:
            if not os.path.exists(dir1):
                os.mkdir(dir1)
            try:
                page3.goto(link, timeout=0)
                download(link, page3, dir1)
            except Exception as e:
                continue
        else:
            if not os.path.exists(dir1):
                try:
                    response = requests.get(link)
                    with open(dir1, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB per chunk
                            if chunk:
                                f.write(chunk)
                except Exception as e:
                    logging.error(e)
                    logging.error(f'下载失败：{fp}')

        if i == num:
            page3.go_back(timeout=0)
            return


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # page3 = browser.new_page()
    # page3.goto('https://www.ncei.noaa.gov/data/')

    # download('https://www.ncei.noaa.gov/data/')

    page = browser.new_page()

    # 访问网站
    try:
        logging.info('打开首页')
        page.goto("https://data.noaa.gov/onestop/", timeout=0)
    except Exception as error:
        logging.error(error)
        logging.critical('无法打开首页')
    # 获取源代码
    page_text = page.content()
    # 获取topic位置
    locator = page.get_by_role("list").filter(has_text="Weather")
    # 获取weather等按钮位置
    button_loc = locator.get_by_role("button")

    button_all = button_loc.all()

    logging.info(f'已找到类别共{len(button_all)}类，准备开始爬取')
    # 循环打开每一个种类
    for button in button_all:
        # 种类名称
        name = button.text_content()
        # 创建文件夹
        if not os.path.exists(work_dir + name):
            os.makedirs(work_dir + name)

        try:
            button.click(timeout=0)
            page.wait_for_timeout(5000)

        except Exception as error:
            logging.error(error)
            logging.error(f'<UNK>无法打开类别{name}')

        page_num = int(page.get_by_role("button", name='Go to last page -').text_content())
        logging.info(f'开始爬取类别{name}，共有{page_num}页')

        # 定位到链接按钮

        next_page_loc = page.get_by_role('button', name='Go to next page')

        for j in range(0, page_num):

            locator1 = page.get_by_role('link')
            for i in range(4, 24):
                flags = False

                # 打开这一页的每一个数据集
                button = locator1.all()[i]
                filename = button.text_content()

                if '/' in filename:
                    filename = filename.replace('/', '_', -1)
                if ':' in filename:
                    filename = filename.replace(':', '_', -1)
                dir = work_dir + name + '/' + filename + '/'
                if not os.path.exists(work_dir + name + '/' + filename):
                    os.mkdir(dir)

                fp = open('./data_download_fail.txt', 'r+')

                fpp = open('./already_data_download.txt', 'r+')
                fp.readlines()
                already_data_download = fpp.readlines()

                if filename + '\n' not in already_data_download:
                    try:
                        flags = True
                        button.click(timeout=0)
                        page.wait_for_timeout(3000)
                    except Exception as error:
                        logging.error(error)
                        logging.error(f'爬取类型{name}下第{j}页中的{filename}数据失败')

                    logging.info(f'开始爬取类型{name}下第{j}页中的{filename}的identifier信息')
                    # 爬取identifier信息
                    identify_loc = page.get_by_role("button", name="Identifier(s)")
                    identify_loc.click()
                    # file_identifier = page.get_by_text(text="File Identifier")
                    identify_text = page.locator('p')
                    t = identify_text.all()[1].text_content()

                    # 写入identifier信息
                    try:
                        with open(dir + 'Identifier' + '.txt', 'w', encoding='utf-8') as f:
                            f.write('identifier:' + t)
                    except Exception as error:
                        logging.error(error)
                        logging.error(f'爬取类型{name}下第{j}页中的{filename}的identifier信息写入失败')

                    # 爬取metadata信息
                    logging.info(f'开始爬取类型{name}下第{j}页中的{filename}的metadata信息')
                    loc_meta = page.get_by_role('button', name='Metadata Access')
                    loc_meta.click(timeout=0)
                    link = page.get_by_role('link', name="Download the full metadata")
                    # url = 'https://data.noaa.gov/' + link.get_attribute('href')

                    href = 'https://data.noaa.gov/' + link.get_attribute('href')

                    page2 = browser.new_page()
                    try:
                        page2.goto(href, timeout=0)
                        content = page2.content()
                    except Exception as error:
                        logging.error(error)
                        logging.error(f'爬取类型{name}下第{j}页中的{filename}的metadata信息失败：网页打开错误')

                    # 下载metadata
                    try:
                        with open(dir + 'metadata.xml', 'w', encoding='utf-8') as f:
                            f.write(content)
                    except Exception as error:
                        logging.error(error)
                        logging.error(f'爬取类型{name}下第{j}页中的{filename}的identifier信息写入失败')

                    page2.close()
                    # 下载data
                    logging.info(f'尝试下载类型{name}下第{j}页中的{filename}的data数据')
                    Access_loc = page.locator('xpath=//*[text()="Access"]')
                    Access_loc.click(timeout=0)

                    download_data_loc = page.locator('xpath=//*[text()="Download Data"]/../../../div[2]/div/ul/li')
                    data = download_data_loc.all()
                    if len(data) == 0:
                        logging.warning(f'类型{name}下第{j}页中的{filename}无data')
                    for d in data:
                        if d.get_by_role('link').text_content().lower() == 'NCEI Direct Download'.lower():
                            page3 = browser.new_page()
                            page3.goto(d.get_by_role('link').get_attribute('href'), timeout=0)
                            if not os.path.exists(dir + 'data/'):
                                os.mkdir(dir + 'data/')
                            download(d.get_by_role('link').get_attribute('href'), page3, dir + 'data/')
                            page3.close()
                            logging.info(f'类型{name}下第{j}页中的{filename}的data数据下载成功')
                        else:
                            fp.write(page.url + '\n')
                            logging.warning(f'类型{name}下第{j}页中的{filename}的data数据下载失败')

                    fpp.write(filename + '\n')

                if flags:
                    page.go_back(timeout=0)
                    page.wait_for_timeout(4000)

                fp.close()
                fpp.close()

            logging.info(f'第{j}页数据爬取结束')
            next_page_loc.click(timeout=0)
            page.wait_for_timeout(3000)

        page.go_back(timeout=0)

fp.close()
