import pytest
import jnet
import lxml
import sys
import pdb
import warnings
import re
import time
import pdb
from pprint import pprint

""" Test the basic features of the JNET Case Participant request/reply framework.

This is not extensively thorough as the test for the production docket tests most of
the underlying details

Run from commandline to verify code updates don't break something with:

```python
PYTHONPATH=jnet-package/ pytest jnet-package/t/test_case_participant_search.py
```

Or to debug/review failures:
```python
PYTHONPATH=jnet-package/ pytest jnet-package/t/test_case_participant_search.py --pdb -s
```

"""

# number of seconds to wait before timeing out between making requests
# and expecting them to be in the check status queue
MAX_TIME = 200

@pytest.fixture
def jnetclient():
    jnetclient = jnet.CCE(
        test = True,
        endpoint = 'jnet',
        verbose = False,
    )

    assert jnetclient, "Client created"
    assert jnetclient.get_endpoint_url() == "https://ws.jnet.pa.gov/AOPC/CCERequest"

    # let's just make sure we know what we're dealing with
    assert "ws.jnet.pa.gov.combined.crt" in jnetclient.server_certificate
    return(jnetclient)

# Single request pipeline - explicitly clears out any previously queued requests with the same tracking id.
# This test is important because the soap -> json data puts this as not-a-list, which we handle in the client
# and need to make sure stays consistent.
#
# Also testing:
#    - request_docket specified tracking id
#    - check_requests by tracking_id
#    - retrieve_requests (the full set) by docket_number and include_metadata = True
TEST_TRACKING_ID = "test-case-participant-1"

@pytest.fixture
def request_participant_history(jnetclient):
    """ Make a request for a person. """

    # clear out any old requests
    requests = jnetclient.retrieve_requests(
        tracking_id = TEST_TRACKING_ID
    )
    while(requests):
        print("...pausing to ensure the queue is clear!")
        time.sleep(5)
        requests = jnetclient.retrieve_requests(tracking_id = TEST_TRACKING_ID)

    resp = jnetclient.request_participant(
        first_name = 'joel',
        last_name = 'polk',
        birthdate = '1971-05-23',
        tracking_id = TEST_TRACKING_ID
    )

    assert resp.tracking_id == TEST_TRACKING_ID
    assert resp.xml is not None
    assert resp.data
    assert resp.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'Routed to JNET Loopback Queue', "It appears you are in pre-production JNET Loopback testing! You cannot run these tests!"
    assert resp.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'CCE request queued to AOPC.'
    return(resp)

@pytest.fixture
def participant_history_check_status(jnetclient, request_participant_history):
    """ It's possible there are othere/old tests in the queue, and so we lazily just check that there are at least as many requests as made in the prior test. """

    print("Sleeping to wait for request to be queued", file = sys.stderr)
    # unfortunately, participant searches take a while, and so we'll just
    # wait until we get to at least 30

    timer = time.time()
    time.sleep(90)
    clean_records = jnetclient.check_requests(tracking_id = TEST_TRACKING_ID)
    while len(clean_records) < 30:
        if time.time() - timer > MAX_TIME:
            assert False, f"Failed to identify open requests within {MAX_TIME} seconds"
        # sleep and try again
        print(f"Retrieved {len(clean_records)} of cases, but we're expecting at least 30 - so sleeping again to wait for request to be queued", file = sys.stderr)
        time.sleep(20)
        clean_records = jnetclient.check_requests(tracking_id = TEST_TRACKING_ID)

    assert type(clean_records) is list
    assert len(clean_records) >= 1, "check_requests did not return details on the request!"

    for rawrecord in clean_records:
        assert type(rawrecord['file_id']) is str
        assert rawrecord['tracking_id'] == TEST_TRACKING_ID

    # this should always return a list, even with 1 element!
    assert type(clean_records) is list

    assert len(clean_records) >= 30
    for i, open_request in enumerate(clean_records):
        assert open_request['tracking_id'] == TEST_TRACKING_ID
        assert open_request['found'] is True
        assert open_request['queued'] is False
        assert type(open_request['file_id']) is str
        assert open_request['participant_details']['first_name'] == 'joel'
        assert open_request['participant_details']['last_name'] == 'polk'
        assert open_request['participant_details']['birth_date'] == '1971-05-23'
        assert not open_request['docket_number']

    return(len(clean_records))


def test_participant_history_pipeline(jnetclient, participant_history_check_status):

    expected_count = participant_history_check_status

    allretrievedata = jnetclient.retrieve_requests(
        tracking_id = TEST_TRACKING_ID,
        include_metadata = True,
    )
    assert len(allretrievedata) >= expected_count
    # - we didn't put the tracking id in the above retrieve, and so we need to filter out
    # any that aren't this tracking id
    retrievedata = [rec for rec in allretrievedata
        if rec['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == TEST_TRACKING_ID
    ]

    assert len(retrievedata) == expected_count
    for retrieved in retrievedata:
        metadata = retrieved ['ReceiveCourtCaseEventReply']['ResponseMetadata']
        assert metadata['UserDefinedTrackingID'] == TEST_TRACKING_ID
        record = retrieved['ReceiveCourtCaseEventReply']['CourtCaseEvent']
        assert type(record) is dict
        # verify docket number
        assert 'CASE PARTICIPANT' in record["ActivityTypeText"]
        assert 'FirstName:joel' in record["ActivityTypeText"]
        assert 'LastName:polk' in record["ActivityTypeText"]
        assert 'BirthDate:1971-05-23' in record["ActivityTypeText"]
        assert metadata['BackendSystemReturn']['BackendSystemReturnText'] == record["ActivityTypeText"]

#
# Errors -
#

def test_person_not_found(jnetclient):

    NOTFOUND_TRACKING_ID = 'test-case-participant-notfound'
    resp = jnetclient.request_participant(
        first_name = 'gegor',
        last_name = 'mendel',
        birthdate = '1900-01-01',
        tracking_id = NOTFOUND_TRACKING_ID
    )

    # this response will be successful
    assert resp.tracking_id == NOTFOUND_TRACKING_ID

    assert resp.xml is not None
    assert resp.data
    assert resp.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'Routed to JNET Loopback Queue', "It appears you are in pre-production JNET Loopback testing! You cannot run these tests!"
    assert resp.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'CCE request queued to AOPC.', "Request metadata is not queued to AOPC!"

    print("Sleeping to wait for request to be queued", file = sys.stderr)
    timer = time.time()
    time.sleep(20)

    # first, check with check = False to avoid exceptions
    data = jnetclient.check_requests(
        tracking_id = NOTFOUND_TRACKING_ID,
        check = False,
    )
    while not len(data):
        if time.time() - timer > MAX_TIME:
            assert False, f"Failed to identify open requests within {MAX_TIME} seconds"
        # sleep and try again
        print("Sleeping again to wait for request to be queued", file = sys.stderr)
        time.sleep(20)
        data = jnetclient.check_requests(
            tracking_id = NOTFOUND_TRACKING_ID,
            docket_number = bad_docket_number,
            check = False,
        )

    assert len(data) >= 1

    # now test the exception
    with pytest.raises(jnet.exceptions.NotFound) as nf_excinf:
        jnetclient.check_requests(tracking_id = NOTFOUND_TRACKING_ID)

    # verify the exception has lots of information!
    nf = nf_excinf.value
    assert nf.data
    assert nf.data['FileTrackingID']
    assert type(nf.response) is jnet.response.SOAPResponse
    assert nf.data['UserDefinedTrackingID'] == NOTFOUND_TRACKING_ID

    # the soap response of the exception has the full data set. We can't compare to nf.data
    # because that's just the offending record.
    assert len(data) == nf.response.data['RequestCourtCaseEventInfoResponse']['RecordCount']

    # so now we need to clean all this garbage up!
    for bad_record in data:
        assert bad_record['tracking_id'] == NOTFOUND_TRACKING_ID
        assert bad_record['type'] == 'participant'
        assert not bad_record['found']
        assert bad_record['queued'] is False

        # fetch by default, which should throw an error
        with pytest.raises(jnet.exceptions.NotFound) as nf_excinf:
            jnetclient.retrieve_file_data(bad_record['file_id'])
        nfe = nf_excinf.value

        assert nfe.data['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == NOTFOUND_TRACKING_ID
        assert type(nfe.response) is jnet.response.SOAPResponse
        assert 'PARTICIPANT NOT FOUND:' in nfe.data['ReceiveCourtCaseEventReply']['ResponseMetadata']['BackendSystemReturn']['BackendSystemReturnText']

        # fetch without check, giving us the actual data structure
        rec = jnetclient.retrieve_file_data(bad_record['file_id'], check = False)
        assert rec['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == NOTFOUND_TRACKING_ID
        assert 'PARTICIPANT NOT FOUND:' in rec['ReceiveCourtCaseEventReply']['ResponseMetadata']['BackendSystemReturn']['BackendSystemReturnText']
