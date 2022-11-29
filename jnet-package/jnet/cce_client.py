import zeep
import lxml
import datetime
import random
import re
from .client import Client
from .exceptions import *


# for debugging
import pdb 
        
class CCE(Client):
    """ Subclass to handle Court Case Event request-reply actions (which are sent to /AOPC/CCERequest endpoint)."""

    wsdl_path = "cfg/CCERequestReply.wsdl"
    url_path = "AOPC/CCERequest"

    def configure_client(self, client):
        """ Sets the namespace prefixes for the CCERequestReply protocol. """
        client.set_ns_prefix("aopc-cce", "http://www.jnet.state.pa.us/niem/aopc/CourtCaseRequest/1")
        client.set_ns_prefix("aopc-crr", "http://jnet.state.pa.us/message/aopc/CCERequestReply/1")

    def metadata_block(self, additional = None):
        """ Returns the basic RequestMetadata object, for when the metadata block is expected by the WSDL. 
        
        Note that if the RequestMetadata is pushed into an `Any` block, you will need to use `_alt_request_metadata()` because the definition needs to be provided. 
        
        Returns:
            dict of fields to set the `RequestMetadata` parameter to.
        """

        xmldata = {
            'RequestAuthenticatedUserID': self.user_id,
        }
        if additional:
            xmldata.update(additional)
        return(xmldata)


    def _alt_request_metadata(self):
        """ Generates the RequestMetadata object suitable to map to an `Any` type block.
        
        This creates a `zeep.xsd.AnyObject` suitable to map to an `Any` param defined in the WSDL file and that represents the `RequestMetadata` entity. This happens because `RequestMetadata` is required by the server but not consistently/accurately defined in the WSDL file provided by JNET."""
        
        metadata_definition = zeep.xsd.Element(
            "{http://www.jnet.state.pa.us/niem/jnet/metadata/1}RequestMetadata",
            zeep.xsd.ComplexType([
                zeep.xsd.Element( "{http://www.jnet.state.pa.us/niem/jnet/metadata/1}RequestAuthenticatedUserID", zeep.xsd.String() ),
            ]),
        )
        RequestMetadata = zeep.xsd.AnyObject(metadata_definition, {
            'RequestAuthenticatedUserID': self.user_id
        })
        return(RequestMetadata)
                
    # ----------------------
    # CCE Functions when using Docket Numbers
    # ----------------------

    def request_docket(self, docket_number:str, send_request = True, tracking_id = None):
        """ Make an initial request for a new court case dataset based on the docket number.
        
        Args:
            docket_number: The docket number to request
            tracking_id: If provided, the tracking ID to find the request downstream. If not provided, a semi-random ID will be generated. The tracking_id will be added as a property of the response object. 
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
        Returns: 
            The SOAPResponse for the request if `send_request` is `True`. Otherwise the lxml.etree for the request.
        Errors: 
            An exception along with the error details if the request failed
        """

        # here we generate a new, random tracking id
        if not tracking_id:
            tracking_id = datetime.date.today().isoformat() + f"-{random.randrange(100000, 999999)}"

        request_metadata = self.metadata_block({
            'UserDefinedTrackingID': tracking_id,
            'ReplyToAddressURI': 'deprecated but required field',
        })
        
        #
        # The current WSDL does not correctly define the case docket information, and
        # only provide a nondescript Any entity, so we'll need to custom build the element.
        # If this changes in the future, this should be the correct data representation.
        #
        case_docket_data = {
            'CaseDocketIDCriteria': {
                'CaseDocketID': docket_number,
            },
        }

        # - Custom Build xml to submit as the main docket information
        court_case_event_builder = zeep.xsd.Element(
            "{http://www.jnet.state.pa.us/niem/aopc/CourtCaseRequest/1}CourtCaseRequest",
            zeep.xsd.ComplexType([               
                zeep.xsd.Element(
                    "{http://us.pacourts.us/niem/aopc/Extension/2}CaseDocketIDCriteria",
                    zeep.xsd.ComplexType([
                        zeep.xsd.Element( "{http://niem.gov/niem/niem-core/2.0}CaseDocketID", zeep.xsd.String() ),
                    ])
                ),
            ]),
        )

        docket_any = zeep.xsd.AnyObject(
            court_case_event_builder,
            case_docket_data,
        )
        # - End custom build of docket xml
        
        node = self.zeep.create_message(
            self.zeep.service, 
            'RequestCourtCaseEvent',
            RequestMetadata = request_metadata,
            _value_1 = docket_any,
        )
        if not send_request:
            return(node)
        
        #send it, but add the tracking number to the response
        result = self.make_request(node)
        result._add_properties(tracking_id=tracking_id, docket_number=docket_number)

        return(result)
    

    def request_otn(self, otn:str, send_request = True, tracking_id = None):
        """ Make an initial request for a new court case dataset based on the Offense Tracking Number (OTN).
        
        Args:
            otn: The Offense Tracking Number (OTN) to request
            tracking_id: If provided, the tracking ID to find the request downstream. If not provided, a semi-random ID will be generated. The tracking_id will be added as a property of the response object. 
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
        Returns: 
            The SOAPResponse for the request if `send_request` is `True`. Otherwise the lxml.etree for the request.
        Errors: 
            An exception along with the error details if the request failed
        """

        # here we generate a new, random tracking id
        if not tracking_id:
            tracking_id = datetime.date.today().isoformat() + f"-{random.randrange(100000, 999999)}"

        request_metadata = self.metadata_block({
            'UserDefinedTrackingID': tracking_id,
            'ReplyToAddressURI': 'deprecated but required field',
        })
        
        # If the WSDL is updated to handle the specific schema for the OTN request
        # this should be the appropriate data structure.
        otn_data = {
            'ChargeTrackingIdentificationCriteria': {
                'ChargeTrackingIdentification': {
                    'IdentificationID': otn,
                },
            },
        }

        otn_court_case_event_builder = zeep.xsd.Element(
            "{http://www.jnet.state.pa.us/niem/aopc/CourtCaseRequest/1}CourtCaseRequest",
            zeep.xsd.ComplexType([
                zeep.xsd.Element(
                    "{http://us.pacourts.us/niem/aopc/Extension/2}ChargeTrackingIdentificationCriteria",
                    zeep.xsd.ComplexType([
                        zeep.xsd.Element(
                            "{http://niem.gov/niem/domains/jxdm/4.0}ChargeTrackingIdentification",
                            zeep.xsd.ComplexType([
                                zeep.xsd.Element( "{http://niem.gov/niem/niem-core/2.0}IdentificationID", zeep.xsd.String() ),
                            ]),
                        ),
                    ])
                ),
            ]),
        )

        otn_any = zeep.xsd.AnyObject(
            otn_court_case_event_builder,
            otn_data,
        )
        
        node = self.zeep.create_message(
            self.zeep.service, 
            'RequestCourtCaseEvent',
            RequestMetadata = request_metadata,
            _value_1 = otn_any,
        )
        if not send_request:
            return(node)
        
        #send it, but add the tracking number to the response
        result = self.make_request(node)
        result._add_properties(tracking_id=tracking_id)

        return(result)
    
    def check_requests(self, tracking_id = None, *, pending_only = True, record_limit = 100, docket_number = None, otn = None, send_request = True, raw = False):
        """ Check the status of existing requests. The request may include records that were requested both by OTN or by Docket Number - they are not designated to separate queues.

        Args:
            tracking_id: If provided, filter requests for the provided tracking number and throw a JNET.exceptions.RequestNotFound exception is not found.
            pending_only: If True, only list prending requests. Default is True.
            record_limit: Set the maximum return count. Default is 100.
            docket_number: If provided, filter requests for the provided docket number and throw a JNET.exceptions.RequestNotFound exception is not found.
            otn: If provided, filter requests for the provided OTN and throw a JNET.exceptions.RequestNotFound exception is not found.
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
            raw: If True, returns the raw SOAPResponse. If False, converts to data. If `docket_number` or `otn` is provided, this parameter is ignored and interpreted as `False`. Default is False.
        Returns: 
            If `send_request` is `False`, returns the lxml.etree for the request.
            If `raw` is `True`, returns the SOAPResponse returned from the request.
            Otherwise, returns an array of data elements.
        """
        node = self.zeep.create_message(
            self.zeep.service, 
            'RequestCourtCaseEventInfo',
            _value_1 = self._alt_request_metadata(),            
            RecordLimit = record_limit, 
            UserDefinedTrackingID = tracking_id, 
            PendingOnly = pending_only,
        )

        if self.verbose:
            print("---- REQUEST ----")        
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        if not send_request:
            return(node)
        
        #send it!
        result = self.make_request(node)

        # change the record count to an integer
        result.data['RequestCourtCaseEventInfoResponse']['RecordCount'] = int(result.data['RequestCourtCaseEventInfoResponse']['RecordCount']
        )

        if result.data['RequestCourtCaseEventInfoResponse']['RecordCount'] == 0:
            # -- no records!
            if pending_only:
                errmessage = "No pending CCE Requests exist at all"
            else:
                errmessage = "No CCE Requests exist at all"
            if docket_number:
                raise NoResults(errmessage + f", let alone for docket {docket_number}", soap_response = result)
            elif otn:
                raise NoResults(errmessage + f", let alone for OTN {otn}", soap_response = result)
            elif raw:
                return(result)
            return([])
        elif type(result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']) is dict:
            # make the metadata an array even if it only contains 1 element
            result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'] = [ result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'] ]

        # -- if docket_number or tracking_id are provided, filter here
        if docket_number:
            filtered_results = []
            requests_not_found = []
            match_string = 'DOCKET NUMBER ' + docket_number.upper()
            for req in result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']:
                for header in req['HeaderField']:
                    if header['HeaderName'] == 'ActivityTypeText':
                        if match_string in header['HeaderValueText']:
                            filtered_results.append(req)
                            # TODO: Not sure what a not-found looks like for docket number yet
                            # elif ...:
                            #      requests_not_found = True
                        elif 'DOCKET NUMBER' in header['HeaderValueText']:
                            # some other docket number
                            continue
                        elif 'DOCKET' in header['HeaderValueText']:
                            raise Exception(f"Header Value appears to refer to dockets but not understood by the CCE Client: '{header['HeaderValueText']}'")

            if len(filtered_results):
                return(filtered_results)
            elif requests_not_found:
                raise NotFound(f"No CCE Request for docket number {docket_number} found, and JNET returned NOT FOUND for tracking numbers {requests_not_found}", data = requests_not_found, soap_response = result)
            else:
                raise NoResults(f"No CCE Request for docket number {docket_number} found, but no 'NOT FOUND' requests identified", soap_response = result)

        if otn:
            filtered_results = []
            requests_not_found = []
            match_string = 'OTN ' + otn.upper()
            for req in result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']:
                for header in req['HeaderField']:
                    if header['HeaderName'] == 'ActivityTypeText':
                        if match_string in header['HeaderValueText']:
                            filtered_results.append(req)
                        elif 'OTN NOT FOUND' in header['HeaderValueText']:
                            requests_not_found.append(req['UserDefinedTrackingID'])                        
                        elif 'OTN' in header['HeaderValueText']:
                            raise Exception(f"Header Value appears to refer to OTN but not understood by the CCE Client: '{header['HeaderValueText']}'")                        

            if len(filtered_results):
                return(filtered_results)
            elif requests_not_found:
                raise NotFound(f"No CCE Request for OTN {otn} found, and JNET returned NOT FOUND for tracking numbers {requests_not_found}", data = requests_not_found, soap_response = result)
            else:
                raise NoResults(f"No CCE Request for OTN {otn} found, but no 'NOT FOUND' requests identified", soap_response = result)

        if raw:            
            return(result)
        return(result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'])


    def retrieve_request(self, file_id:str, check:bool = False, send_request:bool = True, raw = False):
        """ Fetch the data! 
        
        Note: There is no distinction at the retrieve level between requests made by Docket Number and OTN at the request level.

        Args:
            file_id: The File Tracking ID provided when the request was made
            check: If True, checks the response metadata and throws an error for anything other than a successful document
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
            raw: If True, returns the SOAPResponse object instead of the converted data. Default is False.
        Returns: 
            The SOAPResponse for the request if `send_request` is `True`. Otherwise the lxml.etree for the request.
        """

        node = self.zeep.create_message(
            self.zeep.service, 
            'ReceiveCourtCaseEventReply',        
            _value_1 = self._alt_request_metadata(),            
            FileTrackingID = file_id,             
        )
        
        if self.verbose:
            print("---- REQUEST ----")        
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        if not send_request:
            return(node)
        
        #send it!
        result = self.make_request(node)

        # see if there's an error
        data = result.data 

        # -- these errors happen sometimes
        if "ResponseStatusCode" in data["ReceiveCourtCaseEventReply"] and \
            data["ReceiveCourtCaseEventReply"]["ResponseStatusCode"] == "ERROR":
            if data["ReceiveCourtCaseEventReply"]["ResponseActionText"] == "No Record Found.":
                raise NotFound(data = data)
            else:
                raise JNETError(data = data)

        # -- these erors happen other times???
        metadata = data["ReceiveCourtCaseEventReply"]["ResponseMetadata"]
        
        if "BackendSystemReturn" in metadata:
            if metadata["BackendSystemReturn"]["BackendSystemReturnCode"] == "FAILURE":
                if "OTN NOT FOUND" in metadata["BackendSystemReturn"]["BackendSystemReturnText"]:
                    raise NotFound(data = data)
                else:
                    raise JNETError(data = data)
            elif metadata["BackendSystemReturn"]["BackendSystemReturnCode"] != "SUCCESS":
                raise JNETError(f"Do not know haow to interpret a BackendSystemReturnCode of '{metadata['BackendSystemReturn']['BackendSystemReturnCode']}'", data = data)

        return(result)

    def retrieve_requests(self, tracking_id = None, *, docket_number = None, pending_only = True, raw = False, check = True, include_metadata = False):
        """ Fetch all requests that are currently available. 
        
        Args:
            tracking_id: If provided, only fetch requests with the given user defined tracking id.    
            docket_number: If provided, fetches all requests for the given docket number.
            pending_only: If True, only considers pending requests. Default is True.            
            raw: If True, returns an array of SOAPResponse objects rather than the data directly. Default is False.
            check: If True, check each retrieved call to ensure that something is fetched. Default is True.
            include_metadata: If True, includes the `ResponseMetadata` data envelope in the return value; otherwise returns only the `CourtCaseEvent` data. Default is False.            
        Returns:
            If `raw` is `True`, returns an array of SOAPResponse objects for each file.
            If `include_metadata` is `True`, returns an array of the full data structure returned, including the `ResponseMetadata` that indicates information about the BackendRequest. 
            Otherwise, returns an array of the `CourtCaseEvent` data. May be an empty array if no requests are pending.
        Raises:
            If `check` is True and there was a backend error retrieving one of the files, raises a JNETError.
        """
        data = self.check_requests(pending_only = pending_only, tracking_id = tracking_id, docket_number = docket_number)
        if len(data) == 0:
            return([])

        result = []
        for request_info in self.identify_request_status(data):
            retrieved = self.retrieve_request(request_info['file_id'], check = check)
            if raw:
                result.append(retrieved)
            elif include_metadata:
                result.append(retrieved.data)
            else:
                result.append(retrieved.data['ReceiveCourtCaseEventReply']['CourtCaseEvent'])
        return(result)

    @classmethod    
    def identify_request_status(cls, request):
        """ Simplify the request status JSON to something more usable.

        Args:
            request: a data representation of a status request, or a list of the same. This can be found by (a) providing status_request_response.data, or (b)  manually providing 1 or more of the 'RequestCourtCaseEventInfoResponse' -> 'RequestCourtCaseEventInfoMetadata' elements.            
        Returns:
            Usually, a list of objects; however, if the request is a single dict of a single record, it will return a single object. The data structure is defined as follows:
                final: If the element has 'Final' in its header value
                tracking_id: The user defined tracking id.
                file_id: The file tracking id
                found: Boolean to indicate if the element is listed as not found. This will be None if we cannot identify the header or if seems to be still be queued
                otn: the OTN, if it can be identified
                docket: The docket number, if it can be identified
                type: 'otn', 'docket', or None if neither appear to be accurate
                raw: The raw request provided
        """
        if type(request) is list:
            return([cls.identify_request_status(req) for req in request])

        if 'RequestCourtCaseEventInfoResponse' in request:
            # this is the raw data, so reprocess
            result = cls.identify_request_status(request['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'])
            if type(result) is not list:
                return([result])
            return(result)

        result = { 
            'raw': request,
            'file_id': request['FileTrackingID'],
            'tracking_id': request['UserDefinedTrackingID'],                 
            'final': None,       
            'found': None,
            'type': None,
            'docket_number': None,
            'otn': None,
        }

        docket_re = re.compile('DOCKET NUMBER\s+(\S+)')
        
        activity_header_found = False
        for header in request['HeaderField']:
            if header['HeaderName'] == 'ActivityTypeText':
                if activity_header_found:
                    raise Exception("Multiple activity headers?")
                activity_header_found = True
                result['final'] = 'Final Count:' in header['HeaderValueText']
                if 'OTN NOT FOUND' in header['HeaderValueText']:
                    result['found'] = False
                elif 'OTN' in header['HeaderValueText']:
                    raise Exception("Not sure how to process an OTN value")
                else:
                    match = docket_re.search(header['HeaderValueText'])
                    if match:
                        result['docket_number'] = match.group(1)
                        result['found'] = True
                    else:
                        raise Exception("Not sure what this operation is!")

        return(result)
