"""
Harvest items needing librisxl id.

"""
from bs4 import BeautifulSoup
import requests

HOST = 'http://www.isfdb.org'
MISSING_LIBRISXL_REPORT = 300


def _get_record_page(record_id):
    url = '{0}/cgi-bin/pl.cgi?{1}'.format(HOST, record_id)
    r = requests.get(url)
    return r.content


def find_libris_id(record_id):
    ext_ids = None
    soup = BeautifulSoup(_get_record_page(record_id), features='html5lib')
    # must limit search to external ID field to not pick up abbr tags in notes
    for entry in soup.find_all('b'):
        if entry.get_text() == 'External IDs:':
            ext_ids = entry.parent
    libris_links = ext_ids.find_all(
        'abbr', {'title': 'Libris - National Library of Sweden'})
    if len(libris_links) != 1:
        raise Exception(
            '{0} contained {1} libris entries which is not supported'.format(
                record_id, len(libris_links)))
    libris_id = libris_links[0].next_sibling.strip(': ')
    return libris_id


def _load_cleanup_report_from_file(report_id):
    # filename = 'cleanup_report_{}.html'.format(report_id)
    # with open(filename, encoding='iso-8859-1') as f:
    # copy pasting source worked better than trying to save the page, unclear why
    filename = 'cleanup_report_{}_paste.html'.format(report_id)
    with open(filename) as f:
        return f.read()


def _get_cleanup_report(report_id):
    browser = log_in()
    url = '{0}/cgi-bin/edit/cleanup_report.cgi?{1}'.format(HOST, report_id)
    browser.get(url)
    return browser.page_source


def log_in(username, password):
    # this should set some sort of flag about us being logged in
    from selenium import webdriver
    from selenium.webdriver.support.ui import WebDriverWait
    # required geckodriver
    browser = webdriver.Firefox()
    # load login page
    url = '{0}/cgi-bin/dologin.cgi?dologin.cgi+0'.format(HOST)
    browser.get(url)
    browser.find_element_by_name('login').send_keys(username)
    browser.find_element_by_name('password').send_keys(password)
    browser.find_element_by_xpath("//input[@value='submit']").click()
    # wait for login to complete
    WebDriverWait(driver=browser, timeout=10).until(
        lambda x: x.execute_script(
            "return document.readyState === 'complete'"))
    # verify success
    result = (
        browser.find_element_by_id('statusbar')
        .find_element_by_tag_name('h2'))
    if result.text.startswith('Login failed'):
        msg = (
            browser.find_element_by_id('main2')
            .find_element_by_tag_name('h2'))
        raise Exception(msg.text)
    else:
        return browser


def harvest_records_from_cleanup_report(max=5):
    count = 0
    records = {}
    soup = BeautifulSoup(
        _load_cleanup_report_from_file(MISSING_LIBRISXL_REPORT),
        features='html5lib')
    for link in soup.find(id='main2').find_all('a'):
        record_id = link.get('href').split('?')[1]
        libris_id = find_libris_id(record_id)
        records[record_id] = libris_id
        count += 1
        if count >= max:
            break
    print('Found {0} records.'.format(len(records)))
    for k, v in records.items():
        print('{0}\t{1}'.format(k, v))


# find_libris_id(669460)
