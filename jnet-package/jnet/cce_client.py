import zeep
import lxml
import datetime
import random
import re
import time
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

    #----------------------
    # Private Helper Functions
    #----------------------

    def _metadata_block(self, additional = None):
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

    def fetch_docket_data(self, docket_number:str, timeout:int = 80, quiet:bool = False):
        """ Request data for a docket and wait until it is available.

        This is an all-in-one function that will wait/block until the data is available (or until the timeout expires).

        Args:
            docket_number: The docket number to request
            timeout: How long to wait before throwing an exception
            quiet: If True, do not print time-based poll updates. Default is False.
        Returns:
            list: all data returned by JNET for the docket number, in no particular order.
        Raises:
            jnet.exceptions.NotFound if the docket_number is not found.
            jnet.exceptions.QueuedError if the request is queued and won't be available until after 5pm.
            TimeoutError if the data is not returned beofre the timeout expires.
        """ 
            
        request = self.request_docket(docket_number)

        timer = time.time()
        time.sleep(5)    

        # first, check with check = False to avoid exceptions
        data = self.check_requests(
            tracking_id = request.tracking_id, 
            docket_number = docket_number, 
        )
        while not len(data):
            elapsed_time = time.time() - timer
            if elapsed_time > timeout:
                raise TimeoutError(f"Request to fetch JNET data for docket {docket_number} could not be completed within {timeout} seconds")
            print(f"... data not yet available after {format(elapsed_time, '.2')} s. Waiting more.")
            time.sleep(10)
            data = self.check_requests(
                tracking_id = request.tracking_id, 
                docket_number = docket_number, 
            )
        data = self.retrieve_requests(
            tracking_id = request.tracking_id, 
            docket_number = docket_number, 
            check = False,
        )
        return(data)



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

        request_metadata = self._metadata_block({
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

        request_metadata = self._metadata_block({
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
    
    def check_requests(self, tracking_id = None, *, pending_only = True, record_limit = 100, docket_number = None, otn = None, clean = True, check = True, send_request = True, raw = False):
        """ Check the status of existing requests. The request may include records that were requested both by OTN or by Docket Number - they are not designated to separate queues.

        Args:
            tracking_id: If provided, filter requests for the provided tracking number and throw a JNET.exceptions.RequestNotFound exception is not found.
            pending_only: If True, only list prending requests. Default is True.
            record_limit: Set the maximum return count. Default is 100.
            docket_number: If provided, filter requests for the provided docket number and throw a JNET.exceptions.RequestNotFound exception is not found.
            otn: If provided, filter requests for the provided OTN and throw a JNET.exceptions.RequestNotFound exception is not found.
            clean: If True, calls `clean_info_response_data` to return cleaner data. If False, returns the full data. Default is True.
            check: If True, raises an exception if a docket_number or otn *is specified* and cannot be found. If False, it will return the not found records. If neither `otn` nor `docket_number` is specified, this parameter is ignored. Default is True.
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
            if docket_number and check:
                raise NoResults(errmessage + f", let alone for docket {docket_number}", soap_response = result)
            elif otn and check:
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
            match_string = 'DOCKET NUMBER ' + docket_number.upper()
            for req in result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']:
                for header in req['HeaderField']:
                    if header['HeaderName'] == 'ActivityTypeText':
                        if match_string in header['HeaderValueText']:
                            # matched!
                            filtered_results.append(req)
                        elif 'DOCKET NUMBER ' in header['HeaderValueText']:
                            # some other docket number - skip
                            continue
                        elif 'DOCKET NOT FOUND: ' + docket_number.upper() in  header['HeaderValueText']:
                            # AOPC received the request, but didn't find anything!
                            if check:
                                raise NotFound(f"AOPC returned NOT FOUND for Docket Number {docket_number}", data = req, soap_response = result)                            
                            else:
                                filtered_results.append(req)
                        elif 'DOCKET' in header['HeaderValueText'] and docket_number.upper() in header['HeaderValueText']:
                            raise Exception(f"Header Value appears to refer to dockets but not understood by the CCE Client: '{header['HeaderValueText']}'")
                        else:
                            # we don't know what this is (or it is related to another docket number)... so just keep on keeping on
                            continue

            if not len(filtered_results):
                if check:
                    raise NoResults(f"No CCE Request for docket number {docket_number} found, but no 'NOT FOUND' requests identified", soap_response = result)
                return([])
            if clean:
                return(self.clean_info_response_data(filtered_results))
            else:            
                return(filtered_results) # this could be empty if check is False

        if otn:
            # TODO: this probably doesn't work right now.
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
                if clean:
                    return(self.clean_info_response_data(filtered_results))
                return(filtered_results)
            elif requests_not_found:
                raise NotFound(f"No CCE Request for OTN {otn} found, and JNET returned NOT FOUND for tracking numbers {requests_not_found}", data = requests_not_found, soap_response = result)
            else:
                raise NoResults(f"No CCE Request for OTN {otn} found, but no 'NOT FOUND' requests identified", soap_response = result)

        if raw:            
            return(result)
        elif clean:
            return(self.clean_info_response_data(result.data))
        return(result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'])


    def retrieve_request(self, file_id:str, check:bool = True, send_request:bool = True, raw = False):
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
                if check:
                    raise NotFound(
                        data["ReceiveCourtCaseEventReply"]["ResponseActionText"], 
                        data = data, 
                        soap_response = result,
                    )
                elif raw:
                    return(result)
                else:
                    return(data)
            else:
                raise JNETError(data = data, soap_response = result)

        # -- these erors happen other times???
        metadata = data["ReceiveCourtCaseEventReply"]["ResponseMetadata"]
                
        if "BackendSystemReturn" in metadata:            
            if metadata["BackendSystemReturn"]["BackendSystemReturnCode"] == "FAILURE":
                # -- handle failures
                if "DOCKET NOT FOUND" in metadata["BackendSystemReturn"]["BackendSystemReturnText"]:
                    if check:
                        raise NotFound(
                            data['ReceiveCourtCaseEventReply']['AOPCFault']['Reason'], 
                            data = data, 
                            soap_response = result
                            )
                    elif raw:
                        return(result)
                    else:
                        return(data)
                elif "OTN NOT FOUND" in metadata["BackendSystemReturn"]["BackendSystemReturnText"]:
                    if check:
                        raise NotFound(
                            data['ReceiveCourtCaseEventReply']['AOPCFault']['Reason'], 
                            data = data, 
                            soap_response = result,
                        )
                    elif raw:
                        return(result)
                    else:
                        return(data)
                else:
                    raise JNETError(data = data, soap_response = result)
            elif metadata["BackendSystemReturn"]["BackendSystemReturnCode"] != "SUCCESS":
                #-- handle unknown statuses
                raise JNETError(f"Do not know haow to interpret a BackendSystemReturnCode of '{metadata['BackendSystemReturn']['BackendSystemReturnCode']}'", data = data, soap_response = result)
            elif "Queued DOCKET NUMBER " in metadata["BackendSystemReturn"]["BackendSystemReturnText"]:
                #-- this is "successful" but incomplete - so we throw this error!
                docket = re.search(r'Queued DOCKET NUMBER (\S+)', metadata["BackendSystemReturn"]["BackendSystemReturnText"])
                tracking = re.search(r'Queued DOCKET NUMBER (\S+)', metadata["BackendSystemReturn"]["BackendSystemReturnText"])
                raise QueuedError(f"Docket {docket.group(1)} - Tracking ID {metadata['UserDefinedTrackingID']}: this request is queued and accurate data would not be provided if retrieved at this time.", data = data)

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
        data = self.check_requests(
            pending_only = pending_only, 
            tracking_id = tracking_id, 
            docket_number = docket_number, 
            check = check,
        )
        
        if len(data) == 0:
            if check and docket_number:
                raise NotFound(f"Could not find any available files for docket {docket_number}")
            return([])

        result = []
        for request_info in data:
            if request_info['queued']:
                raise QueuedError(f"Docket {request_info['docket_number']} - Tracking ID {request_info['tracking_id']}: this request is queued and accurate data would not be provided if retrieved at this time.", data = request_info)
            retrieved = self.retrieve_request(request_info['file_id'], check = check)
            if raw:
                result.append(retrieved)
            elif include_metadata:
                result.append(retrieved.data)
            else:
                result.append(retrieved.data['ReceiveCourtCaseEventReply']['CourtCaseEvent'])
        return(result)

    @classmethod    
    def clean_info_response_data(cls, request):
        """ Simplify the request status JSON to something more usable.

        Args:
            request: a data representation of a status request, or a list of the same. This can be found by (a) providing status_request_response.data, or (b)  manually providing 1 or more of the 'RequestCourtCaseEventInfoResponse' -> 'RequestCourtCaseEventInfoMetadata' elements.            
        Returns:
            Usually, a list of objects; however, if the request is a single dict of a single record, it will return a single object. The data structure is defined as follows:
                queued: If the element is 'queued', i.e. not yet available for download.
                tracking_id: The user defined tracking id.
                file_id: The file tracking id
                found: Boolean to indicate if the element is listed as not found. This will be None if we cannot identify the header or if seems to be still be queued
                otn: the OTN, if it can be identified
                docket: The docket number, if it can be identified
                type: 'otn', 'docket', or None if neither appear to be accurate
                raw: The raw request provided
        """
        if type(request) is list:
            return([cls.clean_info_response_data(req) for req in request])

        if 'RequestCourtCaseEventInfoResponse' in request:
            # this is the raw data, so reprocess
            result = cls.clean_info_response_data(request['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'])
            if type(result) is not list:
                return([result])
            return(result)

        result = { 
            'raw': request,
            'file_id': request['FileTrackingID'],
            'tracking_id': request['UserDefinedTrackingID'],                 
            'queued': None,       
            'found': None,
            'type': None,
            'docket_number': None,
            'otn': None,
        }

        docket_re = re.compile(r'DOCKET NUMBER\s+(\S+)')
        docket_notfound_re = re.compile(r'DOCKET NOT FOUND:\s+(\S+?)\s*aopc')
        
        activity_header_found = False
        for header in request['HeaderField']:
            if header['HeaderName'] == 'ActivityTypeText':
                if activity_header_found:
                    raise Exception("Multiple activity headers?")
                activity_header_found = True
                result['queued'] = "Queued DOCKET NUMBER " in header['HeaderValueText']
                if 'OTN NOT FOUND' in header['HeaderValueText']:
                    result['found'] = False
                    raise Exception("Not sure how to process an OTN value")
                elif 'OTN' in header['HeaderValueText']:
                    raise Exception("Not sure how to process an OTN value")
                else:
                    match = docket_re.search(header['HeaderValueText'])
                    if match:
                        result['docket_number'] = match.group(1)
                        result['found'] = True
                        result['type'] = 'docket_number'
                        continue

                    match = docket_notfound_re.search(header['HeaderValueText'])
                    if match:
                        result['docket_number'] = match.group(1)
                        result['found'] = False
                        result['type'] = 'docket_number'
                        continue

                    raise Exception(f"Not sure what this operation is: {header['HeaderValueText']}!")

        return(result)
