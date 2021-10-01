"""Add LibrisXL ids to publications with only Libris ids."""
import requests
from bs4 import BeautifulSoup

from isfdb import IsfdbSession

LIBRIS_IDTYPE = 30
LIBRISXL_IDTYPE = 31
MISSING_LIBRISXL_REPORT = 300


def harvest_records_from_cleanup_report(isfdb, max=5, debug=False):
    """Parse the cleanup report to isolate affected publication records."""
    count = 0
    records = []
    soup = BeautifulSoup(
        isfdb.get_cleanup_report(MISSING_LIBRISXL_REPORT),
        features='html5lib')
    for link in soup.find(id='main2').find_all('a'):
        record_id = link.get('href').split('?')[1]
        records.append((record_id, link.text))
        count += 1
        if count >= max:
            break
    print('Found {0} records.'.format(len(records)))

    if debug:
        for id, name in records:
            print('{0}\t{1}'.format(id, name))

    return records


def get_librisxl_id(libris_id):
    """Lookup LibrisXL id by resolving Libris id in XL interface."""
    clearing_url = 'https://libris.kb.se/resource/bib/{0}'.format(libris_id)
    r = requests.head(clearing_url, allow_redirects=True)
    resolved_url = r.url
    if r.status_code != 500:
        raise ValueError('Unable to get LibrisXL id')
    return resolved_url.rpartition('/')[2].partition('#')[0]


def add_librisxl_id(isfdb, record_id):
    """
    Add the Libris XL id to a publication record.

    Skips entries already containing a LibrisXL id or multiple Libris ids.

    Structure of external-id part is:
    External_IDs
       External_ID
          IDtype
          IDvalue
    """
    mod_note = 'Adding LibrisXL ID based on Libris ID (by api)'
    # get entry to ensure it exists and to get remaining external-ids
    record_result = isfdb.get_pub_data_by_record_id(record_id)
    old_data = record_result['ISFDB']['Publications']['Publication']

    # extract all pre-existing identifiers and check for edge cases
    # note that submission format does not include the IDtypeName key
    external_id = []
    libris_id = None
    for entry in old_data.get('External_IDs').get('External_ID'):
        if int(entry.get('IDtype')) == LIBRISXL_IDTYPE:
            raise ValueError('Publication already has LibrisXL ID.')
        elif int(entry.get('IDtype')) == LIBRIS_IDTYPE:
            if libris_id:
                raise ValueError('Publication has multiple Libris IDs.')
            libris_id = entry.get('IDvalue')
        external_id.append({
            'IDtype': entry.get('IDtype'),
            'IDvalue': entry.get('IDvalue')})

    # add new id
    librisxl_id = get_librisxl_id(libris_id)
    external_id.append({
        'IDtype': LIBRISXL_IDTYPE,
        'IDvalue': librisxl_id})

    # package as update
    update = {'External_IDs': {'External_ID': external_id}}
    return isfdb.update_publication(old_data, update, mod_note)


def run():
    """Add up to 20 LibrisXL ids to publications listed in cleanup report."""
    with IsfdbSession(dry=False) as isfdb:
        records = harvest_records_from_cleanup_report(isfdb, max=20)
        for record_id, name in records:
            add_librisxl_id(isfdb, record_id)
            print('Added librisxl to: ({0}){1}'.format(record_id, name))
        print('Done for now')


# drop
def test():
    """Test function to validate methods."""
    with IsfdbSession() as isfdb:
        print('===Harvest records===')
        harvest_records_from_cleanup_report(isfdb, debug=True)
        print('===Update an entry new===')
        add_librisxl_id(isfdb, 645691)


# drop
if __name__ == "__main__":
    test()
