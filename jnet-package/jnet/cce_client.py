import zeep
import lxml
import datetime
import random
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
        result._add_properties(tracking_id=tracking_id)

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
    
    def check_requests(self, pending_only = True, record_limit = 100, tracking_id = None, docket_number = None, otn = None, send_request = True):
        """ Check the status of existing requests. The request may include records that were requested both by OTN or by Docket Number - they are not designated to separate queues.

        Args:
            pending_only: If True, only list prending requests. Default is True.
            record_limit: Set the maximum return count. Default is 100.
            tracking_id: If provided, filter requests for the provided tracking number and throw a JNET.exceptions.RequestNotFound exception is not found.
            docket_number: If provided, filter requests for the provided docket number and throw a JNET.exceptions.RequestNotFound exception is not found.
            otn: If provided, filter requests for the provided OTN and throw a JNET.exceptions.RequestNotFound exception is not found.
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
        Returns: 
            The SOAPResponse for the request if `send_request` is `True`. Otherwise the lxml.etree for the request.
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
        #pdb.set_trace()
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
                            # Not sure what a not-found looks like for docket number yet
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
            pdb.set_trace()
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

        # TODO: This is not done yet!

        return(result)


    def retrieve_request(self, file_id:str, send_request = True):
        """ Fetch the data! 
        
        Note: There is no distinction at the retrieve level between requests made by Docket Number and OTN at the request level.

        Args:
            file_id: The File Tracking ID provided when the request was made
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
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

        if "ResponseStatusCode" in data["ReceiveCourtCaseEventReply"] and \
            data["ReceiveCourtCaseEventReply"]["ResponseStatusCode"] == "ERROR":
            if data["ReceiveCourtCaseEventReply"]["ResponseActionText"] == "No Record Found.":
                raise NotFound(data = data)
            else:
                raise JNETError(data = data)

        return(result)


    # ----------------------
    # CCE Functions when using OTNs
    # ----------------------


    def retrieve_otn_request(self, tracking_id:str, send_request = True):
        """ Fetch the data!

        Args:
            tracking_id: The tracking ID provided when the request was made
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
        Returns: 
            The SOAPResponse for the request if `send_request` is `True`. Otherwise the lxml.etree for the request.
        """

        node = self.zeep.create_message(
            self.zeep.service, 
            'ReceiveCourtCaseEventReply',        
            _value_1 = self._alt_request_metadata(),            
            FileTrackingID = tracking_id,             
        )
        
        if self.verbose:
            print("---- REQUEST ----")        
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        if not send_request:
            return(node)
        
        #send it!
        return(self.make_request(node))        