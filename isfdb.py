"""
Small script for interacting with isfdb.org.

Based on http://www.isfdb.org/wiki/index.php/Web_API
"""
import json
from getpass import getpass
from xml.parsers.expat import ExpatError as XmlParseError

import requests
import xmltodict
from selenium import webdriver

HOST = 'http://www.isfdb.org'
HEADERS = {
    'User-Agent': 'Lokal_Profil ISFDB test script 0.1'
}


# @todo: Add max_submissions = 20 and make_submission should respect this
# @todo: Add a get_pending_edits_number
# @todo: Add mechanism for closing session and killing browser
#        (see commented out)
# @todo: Make browser headless (on dry=False)
class IsfdbSession(object):
    """An isfdb.org session be it via API or browser."""

    def __init__(self, headers=None, dry=True):
        """
        Initialise an IsfdbSession.

        @param headers: Any custom request headers.
        @param dry: If session should be run in dry/debug mode. In this mode
            no submissions are made.
        """
        self._browser = None
        self._credentials = None
        self.headers = headers or HEADERS
        self.dry = dry

    # def __enter__(self):
    #     return self
    #
    # def __exit__(self):
    #     """Ensure no (headless) browsers are left after use."""
    #     if self._browser:
    #         self._browser.quit()

    @property
    def credentials(self):
        """Submission credentials for Web API."""
        if not self._credentials:
            self._credentials = IsfdbSession._load_credentials()
        return self._credentials

    # if adding web password then validation needs to change as does passing
    # credentials straight to make_submission
    # can then use more sane credentials labels
    # @todo: support password in credentials file
    @staticmethod
    def _load_credentials():
        """Load API credentials from .credentials.json file."""
        with open('.credentials.json') as f:
            data = json.load(f)
            if not set(data.keys()) == set(['Submitter', 'LicenseKey']):
                raise ValueError('Incorrectly formatted credentials file')
        return data

    @property
    def browser(self):
        """Browser logged into isfdb.org providing pages not in API."""
        if not self._browser:
            self._browser = self._initialise_browser()
        return self._browser

    # to run headless (if debug=False) see
    # https://stackoverflow.com/questions/46753393
    # @todo: support headless
    def _initialise_browser(self):
        """
        Create a selenium browser logged in to isfdb.org.

        This currently requires geckodriver to be installed and will open a
        separate browser window.
        """
        # required geckodriver
        browser = webdriver.Firefox()
        self.log_in(browser)
        return browser

    def log_in(self, browser=None):
        """
        Log into isfdb.org via browser.

        @param browser: Selenium webdriver to log in with in case the internal
            one is not prepared yet.
        """
        browser = browser or self._browser

        # load the necessary credentials
        username = self.credentials.get('Submitter')
        password = self.credentials.get('password')
        if not username:
            username = input('Username: ')
        if not password:
            password = getpass()

        # load and fill out login page
        url = '{0}/cgi-bin/dologin.cgi?0+0'.format(HOST)
        browser.get(url)
        browser.find_element_by_name('login').send_keys(username)
        browser.find_element_by_name('password').send_keys(password)
        browser.find_element_by_xpath("//input[@value='submit']").click()

        # wait for login to complete
        browser.implicitly_wait(3)

        # verify login was successful
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
            raise ConnectionError(msg)  # @todo: more appropriate exception

    def get_pub_data_by_external_id(self, extid_type: str, ext_id: int):
        """
        Get all publication records matching a provided external identifier.

        For external id type names see:
        http://www.isfdb.org/cgi-bin/adv_identifier_search.cgi

        @param extid_type: The name of the external identifier.
        @param ext_id: The value of the identifier.
        @return: The complete API response (parsed as a dict) including any
            preamble.
        """
        url = '{0}/cgi-bin/rest/getpub_by_ID.cgi?{1}+{2}'.format(
            HOST, extid_type, ext_id)
        r = requests.get(url, headers=self.headers)
        return IsfdbSession._validate_and_parse_xml_response(r)

    def get_pub_data_by_record_id(self, record_id):
        """Get the publication record matching an internal isfdb identifier."""
        url = '{0}/cgi-bin/rest/getpub_by_internal_ID.cgi?{1}'.format(
            HOST, record_id)
        r = requests.get(url, headers=self.headers)
        return IsfdbSession._validate_and_parse_xml_response(r)

    @staticmethod
    def _validate_and_parse_xml_response(request):
        """Check if response is xml, if so parse, else raise error."""
        try:
            data = xmltodict.parse(request.content)
        except XmlParseError:
            raise ValueError(request.content.strip())  # @todo right exception?
        else:
            return data

    def get_cleanup_report(self, report_id):
        """Return the html contents of a cleanup report."""
        url = '{0}/cgi-bin/edit/cleanup_report.cgi?{1}'.format(HOST, report_id)
        self.browser.get(url)
        return self.browser.page_source

    # @todo: add holder support - class variable
    # @todo: add global counter to max out at 20
    def make_submission(
            self, submission_type: str, data: dict, subject: str,
            mod_note: str):
        """
        Make a submission to isfdb.org via the Web API.

        If the 'dry' class parameter is set then request will be printed rather
        than submitted.

        @param submission_type: The submission type as defined at
            http://www.isfdb.org/wiki/index.php/Data_Submission_Formats .
        @param data: The submission payload.
        @param subject: The label by which the submission is known in the
            moderation queue. Should likely always be the title of the modified
            record.
        @param mod_note: A note to the moderators.
        @return: The resulting request.
        """
        payload = {
            'IsfdbSubmission': {
                submission_type: {
                    'Subject': subject,
                    'ModNote': mod_note,
                    **data,
                    **self.credentials
                }
            }
        }
        url = '{0}/cgi-bin/rest/submission.cgi'.format(HOST)
        if self.dry:
            print(IsfdbSession.xml_encode(payload))
        else:
            r = requests.post(
                url,
                data=IsfdbSession.xml_encode(payload),
                headers=self.headers)
            self._parse_submission_result(r)
            return r

    def _parse_submission_result(self, request):
        """Check submission result to flag any failure"""
        result = IsfdbSession.validate_and_parse_xml_response(request)
        status = result.get('ISFDB').get('Status')
        if status == 'FAIL':
            raise ConnectionError(result.get('ISFDB').get('Error'))

    @staticmethod
    def xml_encode(payload):
        """Encode dict as xml with the appropriate encoding."""
        return xmltodict.unparse(payload, encoding='iso-8859-1', pretty=True)

    # @todo: add holder support
    def update_publication(self, old_data: dict, update: dict, mod_note: str):
        """
        Update a single publication.

        See http://www.isfdb.org/wiki/index.php/XML:PubUpdate for more info.

        @param old_data: The pre-existing publication data.
        @param update: The update to be made.
        @param mod_note: A note to the moderators.
        """
        data = {
            'Record': old_data['Record'],
            **update
        }
        return self.make_submission(
            'PubUpdate', data, old_data['Title'], mod_note)
