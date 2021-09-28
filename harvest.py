"""
Harvest items needing librisxl id.

"""
from bs4 import BeautifulSoup
import requests
# import isfdb

HOST = 'http://www.isfdb.org'
MISSING_LIBRISXL_REPORT = 300

# rename file something with libris


# move to isfdb.py - replaced by get_xml_data_by_record_id()
def _get_record_page(record_id):
    url = '{0}/cgi-bin/pl.cgi?{1}'.format(HOST, record_id)
    r = requests.get(url)
    return r.content


# largely replaced by replaced by get_xml_data_by_record_id()
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


# move to isfdb
def _get_cleanup_report(report_id):
    browser = log_in()
    url = '{0}/cgi-bin/edit/cleanup_report.cgi?{1}'.format(HOST, report_id)
    browser.get(url)
    return browser.page_source


# move to isfdb
# load username and password from credentials but allow getting password from
# `from getpass import getpass \n password = getpass()`
# to run headless (if debug=False) see https://stackoverflow.com/questions/46753393
# Note that you may need browser.implicitly_wait(XSECONDS)
def log_in(username=None, password=None):
    # this should set some sort of flag about us being logged in
    if not username:
        username = input('Username: ')
    if not password:
        from getpass import getpass
        password = getpass()
    from selenium import webdriver
    # required geckodriver
    browser = webdriver.Firefox()
    # load login page
    url = '{0}/cgi-bin/dologin.cgi?dologin.cgi+0'.format(HOST)
    browser.get(url)
    browser.find_element_by_name('login').send_keys(username)
    browser.find_element_by_name('password').send_keys(password)
    browser.find_element_by_xpath("//input[@value='submit']").click()
    # wait for login to complete
    browser.implicitly_wait(3)
    result = (
        browser.find_element_by_id('statusbar')
        .find_element_by_tag_name('h2')
        .text)
    if result.lower().startswith('login failed'):
        msg = (
            browser.find_element_by_id('main2')
            .find_element_by_tag_name('h2')
            .text)
        browser.quit()
        raise Exception(msg)  # @todo: find more appropriate exception
    else:
        return browser


# make generic by returning [(cols), ] or OrderedList({col_label: col_value})?
# would then have to run soup on each row though
# For this one return [ (id, name), ]
def harvest_records_from_cleanup_report(max=5):
    count = 0
    records = []
    soup = BeautifulSoup(
        _get_cleanup_report(MISSING_LIBRISXL_REPORT),
        features='html5lib')
    for link in soup.find(id='main2').find_all('a'):
        record_id = link.get('href').split('?')[1]
        libris_id = find_libris_id(record_id)
        records.append((libris_id, link.text))
        count += 1
        if count >= max:
            break
    print('Found {0} records.'.format(len(records)))
    # temp for debug
    for id, name in records:
        print('{0}\t{1}'.format(id, name))
    return records


# drop
def test():
    # find_libris_id(669460)
    harvest_records_from_cleanup_report()


# drop
if __name__ == "__main__":
    test()
