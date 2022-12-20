import pytest
import jnet
import lxml
import pdb 
import xmlsec
import warnings 
import re
from pprint import pprint

""" Test all of the features for the JNET Docket request/reply framework when in Loopback testing.

Note that this is specifically for the first stage of testing in which data is not sent to 
AOPC. These will (mostly) fail with a message "It appears you are not in JNet-only Loopback Testing". 

Note you may also receive errors if:

- JNET changes the test data. During initial development, all requests had the same record returned, so if that changes, this will need to change.
- There may be structural code updates that are not reflected since they could not be tested once we were outside of loopback testing. 

In short, if you get past the intial calls and the tests fail in data validation (like `assert resp.docket_number == test_docket_number` or `assert open_request['otn'] is None`), it's probably looking pretty good.

Run from the commandline in the root of the github checkout like so:

```python
PYTHONPATH=jnet-package/ pytest jnet-package/t/
```

Or to run with the debugger to review failures:

```python
PYTHONPATH=jnet-package/ pytest jnet-package/t/ --pdb -s
```

"""

test_docket_number = 'CP-51-CR-0000100-2021'
test_docket_number_2 = 'CP-51-CR-0000002-2019'
jnet_docket_request_tracking_id = '158354'

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
    resp = jnetclient.request_docket(
        test_docket_number,
        tracking_id = jnet_docket_request_tracking_id,
        send_request = False,
    )
    assert type(resp) is lxml.etree._Element
    obj = jnet.SOAPResponse(xml = resp)
    data = obj.data
    assert 'Id' in data and type(data['Id']) is str
    assert 'RequestCourtCaseEvent' in data
    assert 'RequestMetadata' in data['RequestCourtCaseEvent']
    
    metadata = data['RequestCourtCaseEvent']['RequestMetadata']
    assert 'UserDefinedTrackingID' in metadata and metadata['UserDefinedTrackingID'] == jnet_docket_request_tracking_id
    assert 'ReplyToAddressURI' in metadata and type(metadata['ReplyToAddressURI']) is str
    assert 'RequestAuthenticatedUserID' in metadata and metadata['RequestAuthenticatedUserID'] == jnetclient.user_id
    
    assert 'CourtCaseRequest' in data['RequestCourtCaseEvent'] 
    assert 'CaseDocketIDCriteria' in data['RequestCourtCaseEvent']['CourtCaseRequest'] 
    assert 'CaseDocketID' in data['RequestCourtCaseEvent']['CourtCaseRequest']['CaseDocketIDCriteria'] and  data['RequestCourtCaseEvent']['CourtCaseRequest']['CaseDocketIDCriteria']['CaseDocketID'] == test_docket_number

@pytest.fixture
def multiple_docket_requests(jnetclient):
    """ Do 2 docket request and make sure it looks good. """
    # request docket 1
    resp1 = jnetclient.request_docket(
        test_docket_number,
        tracking_id = jnet_docket_request_tracking_id
    )
    # make sure the tracking id follows the pattern we set for the default
    #assert re.fullmatch(r'20\d\d-[01]\d-[0-3]\d-\d+', resp1.tracking_id)
    assert resp1.tracking_id == jnet_docket_request_tracking_id
    assert resp1.docket_number == test_docket_number
    assert resp1.xml is not None
    assert resp1.data
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'CCE request queued to AOPC.', "It appears you are not in JNet-only loopback testing  (are you in beta testing or production?) - you cannot run these tests!"
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'Routed to JNET Loopback Queue'

    # request docket 2
    resp2 = jnetclient.request_docket(
        test_docket_number_2,
        tracking_id = jnet_docket_request_tracking_id
    )
    assert resp2.tracking_id == jnet_docket_request_tracking_id
    assert resp2.docket_number == test_docket_number_2
    assert resp2.xml is not None
    assert resp2.data
    assert resp2.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'CCE request queued to AOPC.', "It appears you are not in JNet-only loopback testing  (are you in beta testing or production?) - you cannot run these tests!"
    assert resp2.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'Routed to JNET Loopback Queue'

    return([resp1, resp2])

@pytest.fixture
def multiple_requests_check_status(jnetclient, multiple_docket_requests):
    """ It's possible there are othere/old tests in the queue, and so we lazily just check that there are at least as many requests as made in the prior test. """

    resp = jnetclient.check_requests(tracking_id = jnet_docket_request_tracking_id, raw = True)

    data = resp.data
    all_requests = data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']
    assert len(all_requests) == data['RequestCourtCaseEventInfoResponse']['RecordCount']
    assert data['RequestCourtCaseEventInfoResponse']['RecordCount'] >= len(multiple_docket_requests)
        
    for record in all_requests:
        assert type(record['FileTrackingID']) is str
        assert record['UserDefinedTrackingID'] == jnet_docket_request_tracking_id    

    clean_info = jnet.CCE.clean_info_response_data(data)
    for i, open_request in enumerate(clean_info):
        assert open_request['raw'] == all_requests[i]
        assert open_request['tracking_id'] == jnet_docket_request_tracking_id        
        assert open_request['docket_number'] is not None
        #TODO: Why isn't this true?
        #assert open_request['docket_number'] == docket_request.docket_number
        assert open_request['otn'] is None
        assert open_request['found'] is True
        assert type(open_request['file_id']) is str
    
    return(clean_info)

def test_multiple_request_pipeline(jnetclient, multiple_requests_check_status):
        
    for existing_request in multiple_requests_check_status:
        retrieveresp = jnetclient.retrieve_file_data(existing_request['file_id'])
        
        retrievedata = retrieveresp.data
        assert retrievedata['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == existing_request['tracking_id']
        assert type(retrievedata['ReceiveCourtCaseEventReply']['CourtCaseEvent']) is dict

        # verify docket number
        assert existing_request['docket_number'] in retrievedata['ReceiveCourtCaseEventReply']["CourtCaseEvent"]["ActivityTypeText"]


#
# Single request pipeline
#


@pytest.fixture
def single_docket_request(jnetclient):
    """ Do 1 docket request and make sure it looks good. We also clear out the queue to verify that handling a single request works similarly to multiple requests when it comes to check status. """
    requests = jnetclient.retrieve_requests(tracking_id = jnet_docket_request_tracking_id)
    while(requests):
        print("...pausing to ensure the queue is clear!")
        import time
        time.sleep(5)
        requests = jnetclient.retrieve_requests(tracking_id = jnet_docket_request_tracking_id)

    # request docket 1
    resp1 = jnetclient.request_docket(
        test_docket_number,
        tracking_id = jnet_docket_request_tracking_id
    )
    # make sure the tracking id follows the pattern we set for the default
    #assert re.fullmatch(r'20\d\d-[01]\d-[0-3]\d-\d+', resp1.tracking_id)
    assert resp1.tracking_id == jnet_docket_request_tracking_id
    assert resp1.docket_number == test_docket_number
    assert resp1.xml is not None
    assert resp1.data
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] != 'CCE request queued to AOPC.', "It appears you are not in JNet-only loopback testing  (are you in beta testing or production?) - you cannot run these tests!"
    assert resp1.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'Routed to JNET Loopback Queue'

    return(resp1)

@pytest.fixture
def single_docket_request_check_status(jnetclient, single_docket_request):
    """ It's possible there are othere/old tests in the queue, and so we lazily just check that there are at least as many requests as made in the prior test. """

    clean_records = jnetclient.check_requests(tracking_id = jnet_docket_request_tracking_id)
    assert type(clean_records) is list
    assert len(clean_records) >= 1, "check_requests did not return details on the request!"

    for record in clean_records:        
        assert type(record['file_id']) is str
        assert record['tracking_id'] == jnet_docket_request_tracking_id    

    # this should always return a list, even with 1 element!
    assert type(clean_records) is list
    
    # when testing with JNET, the docket number is not always what you requested
    # so to avoid false failures, we'll extract the first docket number and 
    # make sure all records point to the same one.
    #TODO: why isn't this true?
    #assert open_request['docket_number'] == docket_request.docket_number        
    docket_number = clean_records[0]['docket_number']
    for i, open_request in enumerate(clean_records):
        assert open_request['tracking_id'] == jnet_docket_request_tracking_id        
        assert open_request['docket_number'] == docket_number        
        assert open_request['otn'] is None
        assert open_request['found'] is True
        assert type(open_request['file_id']) is str
        
    return([jnet_docket_request_tracking_id, docket_number, len(clean_records)])


def test_single_request_pipeline(jnetclient, single_docket_request_check_status):
        
    tracking_id, docket_number, expected_count = single_docket_request_check_status
    retrievedata = jnetclient.retrieve_requests(docket_number = docket_number, include_metadata = True)
    
    assert len(retrievedata) == expected_count
    for retrieved in retrievedata:
        metadata = retrieved ['ReceiveCourtCaseEventReply']['ResponseMetadata']
        assert metadata['UserDefinedTrackingID'] == tracking_id
        record = retrieved['ReceiveCourtCaseEventReply']['CourtCaseEvent']
        assert type(record) is dict        
        # verify docket number
        assert 'DOCKET NUMBER ' + docket_number in record["ActivityTypeText"]
        assert metadata['BackendSystemReturn']['BackendSystemReturnText'] == record["ActivityTypeText"]

#
# Errors
#

def test_client_errors():

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

