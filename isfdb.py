"""
Small script for interacting with isfdb.org.

Based on http://www.isfdb.org/wiki/index.php/Web_API
"""
import json

import requests
import xmltodict
from xml.parsers.expat import ExpatError as XmlParseError


HOST = 'http://www.isfdb.org'
HEADERS = {
    'User-Agent': 'Lokal_Profil ISFDB test script 0.1'
}
CREDENTIALS = {}

# @TODO: Set up a class IsfdSession which takes the user agent (or parts
# thereof), max submissions = 20, stores browser (to avoid re-login), sets dry
# stores credentials...
# Add a get_pending_edits_number
# Add mechanism for closing session and killing browser


# if adding optional password then validation needs to change as does passing
# credentials straight to make_submission
# can then use more sane credentials labels
def _load_credentials():
    global CREDENTIALS
    if not CREDENTIALS:
        with open('.credentials.json') as f:
            data = json.load(f)
            if not set(data.keys()) == set(['Submitter', 'LicenseKey']):
                raise ValueError('Incorrectly formatted credentials file')
            CREDENTIALS = data
    return CREDENTIALS


def get_pub_data_by_extid(extid_type, extid):
    """."""
    url = '{0}/cgi-bin/rest/getpub_by_ID.cgi?{1}+{2}'.format(
        HOST, extid_type, extid)
    r = requests.get(url, headers=HEADERS)
    return validate_and_parse_xml_response(r)


def get_pub_data_by_record_id(record_id):
    """."""
    url = '{0}/cgi-bin/rest/getpub_by_internal_ID.cgi?{1}'.format(
        HOST, record_id)
    r = requests.get(url, headers=HEADERS)
    return validate_and_parse_xml_response(r)


def validate_and_parse_xml_response(request):
    """Check if response is xml, if so parse, else raise error."""
    try:
        data = xmltodict.parse(request.content)
    except XmlParseError:
        raise Exception(request.content.strip())  # @todo find better exception
    else:
        return data


# add holder support - class variable
def make_submission(submission_type, data, subject, mod_note, dry=True):
    """
    data is dict, subject is string, submissionType is string.
    subject might have a default value
    Add global counter to max out at 20
    """
    payload = {
        'IsfdbSubmission': {
            submission_type: {
                'Subject': subject,
                'ModNote': mod_note,
                ** data,
                **_load_credentials()
            }
        }
    }
    url = '{0}/cgi-bin/rest/submission.cgi'.format(HOST)
    if dry:
        print(xml_encode(payload))
    else:
        r = requests.post(url, data=xml_encode(payload), headers=HEADERS)
        parse_submission_result(r)
        return r


def parse_submission_result(r):
    """Check submission result to flag any failure"""
    result = validate_and_parse_xml_response(r)
    status = result.get('ISFDB').get('Status')
    if status == 'FAIL':
        raise ConnectionError(result.get('ISFDB').get('Error'))


def xml_encode(payload):
    """Encode dict as xml with the appropriate encoding."""
    return xmltodict.unparse(payload, encoding='iso-8859-1', pretty=True)


# add holder support
def update_publication(old_data, update, mod_note):
    """
    Can make this only support additions for now?
    Expect data to be a dict. build xml_payload later

    http://www.isfdb.org/wiki/index.php/XML:PubUpdate
    """
    data = {
        'Record': old_data['Record'],
        **update
    }
    return make_submission('PubUpdate', data, old_data['Title'], mod_note)


# less generic from here
LIBRISXL_IDTYPE = 31


def get_libris_data(libris_id):
    """."""
    d = get_pub_data_by_extid('Libris', libris_id)
    if int(d['ISFDB']['Records']) != 1:
        if int(d['ISFDB']['Records']) > 1:
            raise ValueError('Non-unique Libris match')
        else:
            raise ValueError('No matching Libris entry')
    return d['ISFDB']['Publications']['Publication']


def get_librisxl_id(libris_id):
    clearing_url = 'https://libris.kb.se/resource/bib/{0}'.format(libris_id)
    r = requests.head(clearing_url, allow_redirects=True)
    resolved_url = r.url
    if r.status_code != 500:
        raise ValueError('Unable to get LibrisXL id')
    return resolved_url.rpartition('/')[2].partition('#')[0]


def add_librisxl_id(libris_id):
    """
    Structure of external-id part is:
    External_IDs
       External_ID
          IDtype
          IDvalue
    """
    mod_note = 'Adding LibrisXL ID based on Libris ID (by api)'
    # get entry to ensure it exists and to get remaining external-ids
    old_data = get_libris_data(libris_id)
    # get new id
    librisxl_id = get_librisxl_id(libris_id)
    # extract all pre-existing external ids
    external_id = []
    for entry in old_data.get('External_IDs').get('External_ID'):
        if entry.get('IDtype') == LIBRISXL_IDTYPE:
            raise ValueError('Record already has LibrisXL ID.')
        external_id.append({
            'IDtype': entry.get('IDtype'),
            'IDvalue': entry.get('IDvalue')})
    # add new id
    external_id.append({
        'IDtype': LIBRISXL_IDTYPE,
        'IDvalue': librisxl_id})
    # package as update
    update = {'External_IDs': {'External_ID': external_id}}
    return update_publication(old_data, update, mod_note)


# drop
def test():
    add_librisxl_id(7245873)
    # print(json.dumps(get_libris_data(7245873), indent=4))


# drop
if __name__ == "__main__":
    test()


# SQLGetPubById - the internal mechanism by which pub record could be retieved
