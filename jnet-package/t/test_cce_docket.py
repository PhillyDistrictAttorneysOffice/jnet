import pytest
import jnet
import lxml
import sys
import pdb 
import warnings 
import re
import time
from pprint import pprint

""" Test all of the features for the JNET Docket request/reply framework. 

Run from commandline to verify code updates don't break something with:

```python
PYTHONPATH=jnet-package/ pytest jnet-package/t/
```

Or to debug/review failures:
```python
PYTHONPATH=jnet-package/ pytest jnet-package/t/ --pdb -s
```

"""

# number of seconds to wait before timeing out between making requests 
# and expecting them to be in the check status queue
MAX_TIME = 90 

test_docket_number = 'CP-51-CR-0000100-2021'

mc_docket = "MC-51-CR-9000022-2020"
cp_docket = "CP-51-CR-0003854-2020" 
mdjs_docket = "MJ-20301-CR-0000042-2020"
cp_outside_docket = "CP-67-CR-0005860-2020"

queued_docket = ""

expected_files = {
    mc_docket: 1,
    cp_docket: 1,
    mdjs_docket: 1,
    cp_outside_docket: 1,
}

@pytest.fixture
def jnetclient():
    jnetclient = jnet.CCE(
        test = True, 
        endpoint = 'beta',               
        verbose = False,
    )

    assert jnetclient, "Client created"
    assert jnetclient.get_endpoint_url() == "https://ws.jnet.beta.pa.gov/AOPC/CCERequest"
    return(jnetclient)


def test_request_docket_structure(jnetclient):
    """ test the xml of the request object to make sure it has all of the right components"""
    # get node, but don't make request
    test_tracking_id = "100-200-300-400"
    resp = jnetclient.request_docket(
        test_docket_number,
        tracking_id = test_tracking_id,
        send_request = False,
    )
    assert type(resp) is lxml.etree._Element
    obj = jnet.SOAPResponse(xml = resp)
    data = obj.data
    assert 'Id' in data and type(data['Id']) is str
    assert 'RequestCourtCaseEvent' in data
    assert 'RequestMetadata' in data['RequestCourtCaseEvent']
    
    metadata = data['RequestCourtCaseEvent']['RequestMetadata']
    assert 'UserDefinedTrackingID' in metadata and metadata['UserDefinedTrackingID'] == test_tracking_id
    assert 'ReplyToAddressURI' in metadata and type(metadata['ReplyToAddressURI']) is str
    assert 'RequestAuthenticatedUserID' in metadata and metadata['RequestAuthenticatedUserID'] == jnetclient.user_id
    
    assert 'CourtCaseRequest' in data['RequestCourtCaseEvent'] 
    assert 'CaseDocketIDCriteria' in data['RequestCourtCaseEvent']['CourtCaseRequest'] 
    assert 'CaseDocketID' in data['RequestCourtCaseEvent']['CourtCaseRequest']['CaseDocketIDCriteria'] and  data['RequestCourtCaseEvent']['CourtCaseRequest']['CaseDocketIDCriteria']['CaseDocketID'] == test_docket_number

# Test multiple requests, ie. if we make 2 separate requests with the same tracking id, they will be queued
# separately and we won't be able to tell the difference.  So just make sure that gets handled okay.
#
# Also testing:
#  - request_docket specified a tracking_id
#  - check_requests specifies tracking_id and has `raw = True`
#  - retrieve_request (individual) by file id

@pytest.fixture
def multiple_docket_requests(jnetclient):
    """ Do 2 docket request and make sure it looks good. This will cover both Common Pleas docket numbers. """
    # request docket 1
    resp1 = jnetclient.request_docket(
        cp_outside_docket,
        tracking_id = 'jnet-test-multiple'
    )
    # make sure the tracking id follows the pattern we set for the default
    #assert re.fullmatch(r'20\d\d-[01]\d-[0-3]\d-\d+', resp1.tracking_id)
    assert resp1.tracking_id == 'jnet-test-multiple'
    assert resp1.docket_number == cp_outside_docket
    assert resp1.xml is not None
    assert resp1.data
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'Routed to JNET Loopback Queue', "It appears you are in pre-production JNET Loopback testing! You cannot run these tests!"
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'CCE request queued to AOPC.', "Request metadata is not queued to AOPC!"

    # request docket 2
    resp2 = jnetclient.request_docket(
        cp_docket,
        tracking_id = 'jnet-test-multiple'
    )
    assert resp2.tracking_id == 'jnet-test-multiple'
    assert resp2.docket_number == cp_docket
    assert resp2.xml is not None
    assert resp2.data
    assert resp2.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'Routed to JNET Loopback Queue', "It appears you are in pre-production JNET Loopback testing! You cannot run these tests!"
    assert resp2.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'CCE request queued to AOPC.'

    return([resp1, resp2])

@pytest.fixture
def multiple_requests_check_status(jnetclient, multiple_docket_requests):
    """ It's possible there are othere/old tests in the queue, and so we lazily just check that there are at least 2 requests as made in the prior test. """

    print("Sleeping to wait for request to be queued", file = sys.stderr)
    timer = time.time()
    time.sleep(20)
    resp = jnetclient.check_requests(tracking_id = 'jnet-test-multiple', raw = True)    
    data = resp.data
    if data['RequestCourtCaseEventInfoResponse']['RecordCount'] == 0:
        if time.time() - timer > MAX_TIME:
            assert False, f"Failed to identify open requests within {MAX_TIME} seconds"
        # we'll wait a little bit...
        print("Sleeping to wait for request to be queued", file = sys.stderr)
        time.sleep(20)
        resp = jnetclient.check_requests(tracking_id = 'jnet-test-multiple', raw = True)    
        data = resp.data
    
    assert data['RequestCourtCaseEventInfoResponse']['RecordCount'] >= 2, "Request status cannot be found :("
            
    all_requests = data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']
    assert len(all_requests) == data['RequestCourtCaseEventInfoResponse']['RecordCount']
    assert data['RequestCourtCaseEventInfoResponse']['RecordCount'] >= len(multiple_docket_requests)
        
    for record in all_requests:
        assert type(record['FileTrackingID']) is str
        assert record['UserDefinedTrackingID'] == 'jnet-test-multiple'    

    clean_info = jnet.CCE.identify_request_status(data)    
    file_counts = {cp_docket:0, cp_outside_docket:0}
    for i, open_request in enumerate(clean_info):
        assert open_request['raw'] == all_requests[i]
        assert open_request['tracking_id'] == 'jnet-test-multiple'        
        assert open_request['docket_number'] is not None
        assert open_request['docket_number'] in (cp_docket, cp_outside_docket)
        file_counts[open_request['docket_number']] += 1
        assert open_request['otn'] is None
        assert open_request['found'] is True
        assert type(open_request['file_id']) is str
    
    assert file_counts[cp_docket] == expected_files[cp_docket]
    assert file_counts[cp_outside_docket] == expected_files[cp_outside_docket]
    return(clean_info)

def test_multiple_request_pipeline(jnetclient, multiple_requests_check_status):
        
    for existing_request in multiple_requests_check_status:
        retrieveresp = jnetclient.retrieve_request(existing_request['file_id'])
        
        retrievedata = retrieveresp.data
        assert retrievedata['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == existing_request['tracking_id']
        assert type(retrievedata['ReceiveCourtCaseEventReply']['CourtCaseEvent']) is dict

        # verify docket number
        assert existing_request['docket_number'] in retrievedata['ReceiveCourtCaseEventReply']["CourtCaseEvent"]["ActivityTypeText"]


# Single request pipeline - explicitly clears out any previously queued requests with the same tracking id.
# This test is important because the soap -> json data puts this as not-a-list, which we handle in the client
# and need to make sure stays consistent.
#
# Also testing:
#    - request_docket specified tracking id
#    - check_requests by tracking_id
#    - retrieve_requests (the full set) by docket_number and include_metadata = True
@pytest.fixture
def single_docket_request(jnetclient):
    """ Do 1 docket request (for an mc docket) and make sure it looks good. We also clear out the queue to verify that handling a single request works similarly to multiple requests when it comes to check status. """
    requests = jnetclient.retrieve_requests(tracking_id = "test-single-mc-docket")
    while(requests):
        print("...pausing to ensure the queue is clear!")
        time.sleep(5)
        requests = jnetclient.retrieve_requests(tracking_id = "test-single-mc-docket")

    # request docket 1
    resp1 = jnetclient.request_docket(
        mc_docket,
        tracking_id = "test-single-mc-docket"
    )
    # make sure the tracking id follows the pattern we set for the default
    #assert re.fullmatch(r'20\d\d-[01]\d-[0-3]\d-\d+', resp1.tracking_id)
    assert resp1.tracking_id == "test-single-mc-docket"
    assert resp1.docket_number == mc_docket
    assert resp1.xml is not None
    assert resp1.data
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'Routed to JNET Loopback Queue', "It appears you are in pre-production JNET Loopback testing! You cannot run these tests!"
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'CCE request queued to AOPC.'
    return(resp1)

@pytest.fixture
def single_docket_request_check_status(jnetclient, single_docket_request):
    """ It's possible there are othere/old tests in the queue, and so we lazily just check that there are at least as many requests as made in the prior test. """

    print("Sleeping to wait for request to be queued", file = sys.stderr)
    timer = time.time()
    time.sleep(20)
    clean_records = jnetclient.check_requests(tracking_id = "test-single-mc-docket")
    while not len(clean_records):
        if time.time() - timer > MAX_TIME:
            assert False, f"Failed to identify open requests within {MAX_TIME} seconds"
        # sleep and try again
        print("Sleeping again to wait for request to be queued", file = sys.stderr)
        time.sleep(20)
        clean_records = jnetclient.check_requests(tracking_id = "test-single-mc-docket")

    assert type(clean_records) is list
    assert len(clean_records) >= 1, "check_requests did not return details on the request!"

    for rawrecord in clean_records:        
        assert type(rawrecord['file_id']) is str
        assert rawrecord['tracking_id'] == "test-single-mc-docket"    

    # this should always return a list, even with 1 element!
    assert type(clean_records) is list
    
    # when testing with JNET, the docket number is not always what you requested
    # so to avoid false failures, we'll extract the first docket number and 
    # make sure all records point to the same one.
    #TODO: why isn't this true?
    #assert open_request['docket_number'] == docket_request.docket_number        
    docket_number = clean_records[0]['docket_number']
    assert docket_number == mc_docket
    assert len(clean_records) == expected_files[mc_docket]
    for i, open_request in enumerate(clean_records):
        assert open_request['tracking_id'] == "test-single-mc-docket"        
        assert open_request['docket_number'] == docket_number        
        assert open_request['otn'] is None
        assert open_request['found'] is True
        assert type(open_request['file_id']) is str
        
    return([docket_number, len(clean_records)])


def test_single_request_pipeline(jnetclient, single_docket_request_check_status):
        
    docket_number, expected_count = single_docket_request_check_status
    allretrievedata = jnetclient.retrieve_requests(docket_number = docket_number, include_metadata = True)
    
    assert len(allretrievedata) >= expected_count
    # - we didn't put the tracking id in the above retrieve, and so we need to filter out 
    # any that aren't this tracking id
    retrievedata = [rec for rec in allretrievedata 
        if rec['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == "test-single-mc-docket"
    ]

    assert len(retrievedata) == expected_count
    for retrieved in retrievedata:
        metadata = retrieved ['ReceiveCourtCaseEventReply']['ResponseMetadata']
        assert metadata['UserDefinedTrackingID'] == "test-single-mc-docket"
        record = retrieved['ReceiveCourtCaseEventReply']['CourtCaseEvent']
        assert type(record) is dict        
        # verify docket number
        assert 'DOCKET NUMBER ' + docket_number in record["ActivityTypeText"]
        assert metadata['BackendSystemReturn']['BackendSystemReturnText'] == record["ActivityTypeText"]




# MDJS request pipeline - makes a request for the MDJS test docket.
# 
# Also testing:
#    - request_docket without any extra parameters - so verifying the format for the generated tracking_id
#    - check_requests with no parameters
#    - retrieve_requests by docket_number only (no metadata)
@pytest.fixture
def mdjs_docket_request(jnetclient):
    """ Do a docket request for an mdjs docket and make sure it looks good. We also clear out the queue to verify that handling a single request works similarly to multiple requests when it comes to check status. """

    # request docket
    resp1 = jnetclient.request_docket( mdjs_docket )

    # make sure the tracking id follows the pattern we set for the default
    assert re.fullmatch(r'20\d\d-[01]\d-[0-3]\d-\d+', resp1.tracking_id)
    assert resp1.docket_number == mdjs_docket
    assert resp1.xml is not None
    assert resp1.data
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'Routed to JNET Loopback Queue', "It appears you are in pre-production JNET Loopback testing! You cannot run these tests!"
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'CCE request queued to AOPC.'
    return(resp1)

@pytest.fixture
def mdjs_request_check_status(jnetclient, mdjs_docket_request):
    """ It's possible there are othere/old tests in the queue, and so we lazily just check that there are at least as many requests as made in the prior test. """

    mdjs_tracking_id = mdjs_docket_request.tracking_id
    print("Sleeping to wait for request to be queued", file = sys.stderr)
    timer = time.time()
    time.sleep(20)
    rawrecords = jnetclient.check_requests(clean = False)
    while not len(rawrecords):
        if time.time() - timer > MAX_TIME:
            assert False, f"Failed to identify open requests within {MAX_TIME} seconds"
        # sleep and try again
        print("Sleeping again to wait for request to be queued", file = sys.stderr)
        time.sleep(20)
        rawrecords = jnetclient.check_requests()

    assert type(rawrecords) is list
    assert len(rawrecords) >= 1, "check_requests did not return details on the request!"

    # - only fetch records for this tracking id and docket number
    for rawrecord in rawrecords:        
        assert type(rawrecord['FileTrackingID']) is str       

    # this should always return a list, even with 1 element!
    all_clean_records = jnet.CCE.identify_request_status(rawrecords)
    assert type(all_clean_records) is list
    assert len(all_clean_records) == len(rawrecords)

    # -- now filter the records for the tracking id and docket number 
    # because we made a blanket check_requests() call, which may include other requests
    clean_records = []
    for rec in all_clean_records:
        if rec['docket_number'] == mdjs_docket and rec['tracking_id'] == mdjs_tracking_id:
            clean_records.append(rec)

    # when testing with JNET, the docket number is not always what you requested
    # so to avoid false failures, we'll extract the first docket number and 
    # make sure all records point to the same one.
    #TODO: why isn't this true?
    #assert open_request['docket_number'] == docket_request.docket_number        
    docket_number = clean_records[0]['docket_number']
    assert docket_number == mdjs_docket
    assert len(clean_records) == expected_files[mdjs_docket]
    for i, open_request in enumerate(clean_records):
        assert open_request['raw'] == rawrecords[i]
        assert open_request['tracking_id'] == mdjs_tracking_id        
        assert open_request['docket_number'] == docket_number        
        assert open_request['otn'] is None
        assert open_request['found'] is True
        assert type(open_request['file_id']) is str
        
    return([mdjs_tracking_id, docket_number, len(clean_records)])


def test_mdjs_request_pipeline(jnetclient, mdjs_request_check_status):
        
    mdjs_tracking_id, docket_number, expected_count = mdjs_request_check_status
    allretrievedata = jnetclient.retrieve_requests(docket_number = docket_number)
    
    assert len(allretrievedata) >= expected_count
    # - we didn't put the tracking id in the above retrieve, and so we need to filter out 
    # any that aren't this tracking id
    retrievedata = []
    for rec in allretrievedata:
        # -- make sure it has the tracking ID and docket number that we care about
        if mdjs_docket != rec["CaseDocketID"]["ID"]:
            continue

        event_ids = [ref for ref in rec["DocumentOtherMetadataField"] if ref["MetadataFieldName"] == "EVENT ID"]
        assert len(event_ids) == 1
        if event_ids[0]["MetadataFieldValueText"] != mdjs_tracking_id:
            continue
        retrievedata.append(rec)

    assert len(retrievedata) == expected_count
    # Note: we already know the docket and tracking id are correct because of how retrieveddata is
    # built above, so we don't check them in the following loop.
    # But if that changes, add in more checks below
    for record in retrievedata:
        # verify docket number exists in the activity type text
        assert 'DOCKET NUMBER ' + docket_number in record["ActivityTypeText"]
        # - just verify a bunch of fields are there
        for expected_key in ('CaseTitleText', 'CaseDocketID', 'CaseOtherID', 'CaseCourt', 'CaseCourtEvent', 'CaseDetails', 'CaseDisposition', 'CaseParticipants', 'CaseStatus', 'CaseCharge', 'CaseClassification'):
            assert record[expected_key], f"Could not find {expected_key} in the returned data!"
#
# Errors - 
#

def test_bad_docket_number(jnetclient):
    
    bad_tracking_id = "test-mc-docket-does-not-exist"
    bad_docket_number = "MC-51-DOCKET-DOES-NOT-EXIST"
    resp = jnetclient.request_docket(
        bad_docket_number,
        tracking_id = bad_tracking_id,
    )
    # this response will be successful
    assert resp.tracking_id == bad_tracking_id
    assert resp.docket_number == bad_docket_number
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
        tracking_id = bad_tracking_id, 
        docket_number = bad_docket_number, 
        check = False,
    )
    while not len(data):
        if time.time() - timer > MAX_TIME:
            assert False, f"Failed to identify open requests within {MAX_TIME} seconds"
        # sleep and try again
        print("Sleeping again to wait for request to be queued", file = sys.stderr)
        time.sleep(20)
        data = jnetclient.check_requests(
            tracking_id = bad_tracking_id, 
            docket_number = bad_docket_number, 
            check = False,
        )

    assert len(data) >= 1

    # now test the exception
    with pytest.raises(jnet.exceptions.NotFound) as nf_excinf:
        jnetclient.check_requests(tracking_id = bad_tracking_id, docket_number = bad_docket_number)
    
    # verify the exception has lots of information!
    nf = nf_excinf.value
    assert "AOPC returned NOT FOUND for Docket Number " + bad_docket_number in nf.message
    assert nf.data
    assert nf.data['FileTrackingID']    
    assert type(nf.response) is jnet.response.SOAPResponse
    assert nf.data['UserDefinedTrackingID'] == bad_tracking_id

    # the soap response of the exception has the full data set. We can't compare to nf.data 
    # because that's just the offending record.
    assert len(data) == nf.response.data['RequestCourtCaseEventInfoResponse']['RecordCount']



    # so now we need to clean all this garbage up!
    for bad_record in data:
        assert bad_record['tracking_id'] == bad_tracking_id
        assert bad_record['docket_number'] == bad_docket_number
        assert bad_record['type'] == 'docket_number'
        assert not bad_record['found']

        # fetch by default, which should throw an error
        with pytest.raises(jnet.exceptions.NotFound) as nf_excinf:
            jnetclient.retrieve_request(bad_record['file_id'])
        nfe = nf_excinf.value

        assert nfe.data['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == bad_tracking_id
        assert type(nfe.response) is jnet.response.SOAPResponse
        assert nfe.data['ReceiveCourtCaseEventReply']['ResponseMetadata']['BackendSystemReturn']['BackendSystemReturnText'] == 'DOCKET NOT FOUND: ' + bad_docket_number

        # fetch without check, giving us the actual data structure
        rec = jnetclient.retrieve_request(bad_record['file_id'], check = False)
        assert rec['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == bad_tracking_id
        assert rec['ReceiveCourtCaseEventReply']['ResponseMetadata']['BackendSystemReturn']['BackendSystemReturnText'] == 'DOCKET NOT FOUND: ' + bad_docket_number



def test_client_setup_errors():
    # Structural errors - messed up keys, pointing to the wrong certificates, etc

    #
    #  certifcate referecend doesn't exist
    #
    jnetclient = jnet.CCE(
        test = True, 
        client_certificate = "/dev/woof",
    )

    assert jnetclient, "Client created"
    assert jnetclient.get_endpoint_url() == "https://ws.jnet.beta.pa.gov/AOPC/CCERequest"

    # fail on docket request with a nonexistent key file
    with pytest.raises(FileNotFoundError):
        resp = jnetclient.request_docket(
            test_docket_number,
        )

    #
    #  certifcate referecend exists but is wrong
    #
    jnetclient.client_certificate = "cert/ws.jnet.beta.pa.gov_2022/ws.jnet.beta.pa.gov.crt"
    # fail on docket request with a bad cert file
    with pytest.raises(ValueError):
        resp = jnetclient.request_docket(
            test_docket_number,
        )
    # reset
    jnetclient.client_certificate = None
    
    # no password
    passwd = jnetclient.client_password 
    jnetclient.config['client-password'] = None
    jnetclient.client_password = None
    with pytest.raises(Exception):
        resp = jnetclient.request_docket(
            test_docket_number,
        )

    jnetclient.client_password = "woof woof"
    with pytest.raises(ValueError):
        resp = jnetclient.request_docket(
            test_docket_number,
        )

    # reset to the correct one
    jnetclient.client_password = passwd
    # cut out the user id
    correct_user_id = jnetclient.user_id
    jnetclient.config['user-id'] = None
    jnetclient.user_id = None
    with pytest.raises(jnet.exceptions.AuthenticationUseridError):
        jnetclient.request_docket(
            test_docket_number,
        )

    jnetclient.user_id = 'woof woof'
    #jnetclient.verbose = True
    #with pytest.raises(jnet.exceptions.AuthenticationUseridError):
    resp = jnetclient.check_requests()
    print("this is weird - why isn't there an error here?")

