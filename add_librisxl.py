"""Add LibrisXL ids to publications with only Libris ids."""
from collections import namedtuple

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
    # get entry to ensure it exists and to get remaining external-ids
    record_result = isfdb.get_pub_data_by_record_id(record_id)
    old_data = record_result['ISFDB']['Publications']['Publication']

    # extract all pre-existing identifiers and check for edge cases
    # note that submission format does not include the IDtypeName key
    external_id = []
    libris_id = None
    for entry in listify(old_data.get('External_IDs').get('External_ID')):
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
    return isfdb.update_publication(old_data, update)


def listify(value):
    """
    Turn the given value, which might or might not be a list, into a list.

    @param value: The value to listify
    @rtype: list|None
    """
    if value is None:
        return None
    elif isinstance(value, list):
        return value
    else:
        return [value, ]


def parse_pending(isfdb):
    """
    Parse the My Pending Edits page.

    If no pending edits then contents are:
    <div id="main">
       ... text about current global queue.
       <h3>No submissions present</h3>
    </div>

    If pending edits then contents are:
    <div id="main">
       ...
       <table class="generic_table">
           <tbody>
               <tr>[table head]</tr>
               <tr>[entry]</tr>
               ...
           </tbody>
       </table>
    </div>

    Column order is:
    (Submission, Type, Time Submitted, Submitter, Holder, Affected Record, Cancel)  # noqa: E501
    """
    pending_edits = []
    soup = BeautifulSoup(
        isfdb.get_pending_edits(),
        features='html5lib')
    table = soup.find(id='main').find('table')

    # if no pending edits
    if not table:
        return pending_edits

    # if pending edits
    PendingSubmission = namedtuple(
        'PendingSubmission', ['id', 'type', 'name', 'record'])

    for row in table.find_all('tr')[1:]:  # skip header row
        # when new records are created Affected Record is not linked
        record_id = None
        affected_record = row.find_all('td')[5]
        record_link = affected_record.find('a')
        if record_link:
            record_id = record_link.get('href').split('?')[1]
        pending_edits.append(
            PendingSubmission(
                row.find('td').text,
                row.find_all('td')[1].text,
                affected_record.text,
                record_id
            )
        )

    print('You have {0} pending edits.'.format(len(pending_edits)))

    return pending_edits


def run():
    """Add up to 20 LibrisXL ids to publications listed in cleanup report."""
    mod_note = 'Adding LibrisXL ID based on Libris ID (by api)'
    with IsfdbSession(dry=False, mod_note=mod_note) as isfdb:
        pending_edits = parse_pending(isfdb)
        records = harvest_records_from_cleanup_report(isfdb, max=20)
        for record_id, name in records:
            if record_id in [edit.record for edit in pending_edits]:
                print('Skipping due to pending: ({0}){1}'.format(
                    record_id, name))
                continue
            try:
                add_librisxl_id(isfdb, record_id)
            except ValueError as e:
                print('Skipping due to "{2}": ({0}){1}'.format(
                    record_id, name, e))
            print('Added librisxl to: ({0}){1}'.format(record_id, name))
        print('Done for now')


# drop
def debug_pending_edits(isfdb):
    """Render pending edits results for debugging."""
    for edit in parse_pending(isfdb):
        print('{0} ({3})\t[{2}]\t{1}'.format(
            edit.id, edit.name, edit.record, edit.type))


def test():
    """Test function to validate methods."""
    with IsfdbSession() as isfdb:
        print('===Harvest records===')
        harvest_records_from_cleanup_report(isfdb, debug=True)
        print('===Update an entry new===')
        add_librisxl_id(isfdb, 645691)
        print('===Pending edits===')
        debug_pending_edits(isfdb)


# drop
if __name__ == "__main__":
    run()
