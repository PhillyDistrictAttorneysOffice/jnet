import pytest
import jnet
import lxml
import pdb 
import xmlsec
import warnings 

import traceback
import warnings
import sys

def load_client():
    jnetclient = jnet.CCE(
        test = True, 
        endpoint = 'beta',               
        verbose = False,
    )

    assert jnetclient, "Client created"
    assert jnetclient.get_endpoint_url() == "https://ws.jnet.beta.pa.gov/AOPC/CCERequest"
    return(jnetclient)

def test_request_court_case_event():

    jnetclient = load_client()

    # get node, but don't make request
    resp = jnetclient.request_docket(
        'CP-51-CR-0000003-2022',
        tracking_id = "my-test-1",
        send_request = False,
    )
    assert type(resp) is lxml.etree._Element
    obj = jnet.SOAPResponse(xml = resp)
    data = obj.data
    assert 'Id' in data and type(data['Id']) is str
    assert 'RequestCourtCaseEvent' in data
    assert 'RequestMetadata' in data['RequestCourtCaseEvent']
    
    metadata = data['RequestCourtCaseEvent']['RequestMetadata']
    assert 'UserDefinedTrackingID' in metadata and metadata['UserDefinedTrackingID'] == "158354"
    assert 'ReplyToAddressURI' in metadata and type(metadata['ReplyToAddressURI']) is str
    assert 'RequestAuthenticatedUserID' in metadata and metadata['RequestAuthenticatedUserID'] == jnetclient.user_id
    
    assert 'CourtCaseRequest' in data['RequestCourtCaseEvent'] 
    assert 'CaseDocketIDCriteria' in data['RequestCourtCaseEvent']['CourtCaseRequest'] 
    assert 'CaseDocketID' in data['RequestCourtCaseEvent']['CourtCaseRequest']['CaseDocketIDCriteria'] and  data['RequestCourtCaseEvent']['CourtCaseRequest']['CaseDocketIDCriteria']['CaseDocketID'] == 'CP-51-CR-0000003-2022'

    # request docket
    resp = jnetclient.request_docket(
        'CP-51-CR-0000003-2021',
    )

    assert resp.tracking_id == '158354'
    assert resp.xml is not None
    assert resp.data
    assert resp.data['RequestCourtCaseEventResponse']['ResponseStatusCode'] == 'SUCCESS'
    assert resp.data['RequestCourtCaseEventResponse']['ResponseStatusDescriptionText'] == 'Routed to JNET Loopback Queue'



def test_request_court_case_event_info():

    jnetclient = load_client()

    # get node, but don't make request
    resp = jnetclient.check_requests()
    data = resp.data
    assert data['RequestCourtCaseEventInfoResponse']['RecordCount'] == 100
    assert len(data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']) == data['RequestCourtCaseEventInfoResponse']['RecordCount']

    for record in data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']:
        assert type(record['FileTrackingID']) is str


    resp2 = jnetclient.check_requests(record_limit = 10, pending_only = False)
    data = resp2.data
    assert data['RequestCourtCaseEventInfoResponse']['RecordCount'] == 10
    assert len(data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']) == data['RequestCourtCaseEventInfoResponse']['RecordCount']

    for record in data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']:
        assert type(record['FileTrackingID']) is str


def test_client_receive():

    jnetclient = load_client()
    req = jnetclient.check_requests()
    file_tracking_id = req.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'][0]['FileTrackingID']
    
    # request docket
    resp = jnetclient.retrieve_request(file_tracking_id)
    data = resp.data
    assert data['ReceiveCourtCaseEventReply']['ResponseMetadata']['UserDefinedTrackingID'] == req.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'][0]['UserDefinedTrackingID']
    assert type(data['ReceiveCourtCaseEventReply']['CourtCaseEvent']) is dict


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
            'CP-51-CR-0000003-2021',
        )

    #
    #  certifcate referecend exists but is wrong
    #
    jnetclient.client_certificate = "cert/ws.jnet.beta.pa.gov_2022/ws.jnet.beta.pa.gov.crt"
    # fail on docket request with a bad cert file
    with pytest.raises(ValueError):
        resp = jnetclient.request_docket(
            'CP-51-CR-0000003-2021',
        )
    # reset
    jnetclient.client_certificate = None
    
    # no password
    passwd = jnetclient.client_password 
    jnetclient.config['client-password'] = None
    jnetclient.client_password = None
    with pytest.raises(Exception):
        resp = jnetclient.request_docket(
            'CP-51-CR-0000003-2021',
        )

    jnetclient.client_password = "woof woof"
    with pytest.raises(ValueError):
        resp = jnetclient.request_docket(
            'CP-51-CR-0000003-2021',
        )

    # reset to the correct one
    jnetclient.client_password = passwd
    # cut out the user id
    correct_user_id = jnetclient.user_id
    jnetclient.config['user-id'] = None
    jnetclient.user_id = None
    with pytest.raises(jnet.exceptions.AuthenticationUseridError):
        jnetclient.request_docket(
            'CP-51-CR-0000003-2021',
        )

    jnetclient.user_id = 'woof woof'
    #jnetclient.verbose = True
    #with pytest.raises(jnet.exceptions.AuthenticationUseridError):
    resp = jnetclient.check_requests()
    print("this is weird - why isn't there an error here?")

