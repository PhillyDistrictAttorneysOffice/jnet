import zeep
import lxml
import datetime
import random
from .client import Client

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
        
        This creates a `zeep.xsd.AnyObject` suitable to map to an `Any` param defined in the WSDL file and that represents the `RequestMetadata` entity. This happens because `RequestMetadata` is required by the server but not consistently/accurately defined in the WSDL file provided by JNet."""
        
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
        """ Make an initial request for a new court case dataset.
        
        Args:
            docket_number: The docket number to request
            tracking_id: If provided, the tracking ID to find the request downstream. If not provided, a semi-random ID will be generated. The tracking_id will be added as a property of the response object. 
            send_request: If True, sends the request to JNET. If False, returns the generated lxml.etree for the request.
        Returns: 
            The requests response, if send_request is True. Otherwise the lxml.etree for the request.
        Errors: 
            An exception along with the error details if the request failed
        """

        # here we generate a new, random tracking id
        if not tracking_id:
            tracking_id = datetime.date.today().isoformat() + f"-{random.randrange(100000, 999999)}"

        if self.test:
            # If in test mode, set the loopback value
            tracking_id = '158354'

        request_metadata = self.metadata_block({
            'UserDefinedTrackingID': tracking_id,
            'ReplyToAddressURI': 'deprecated but required field',
        })
        
        case_docket = {
            'CaseDocketIDCriteria': {
                'CaseDocketID': docket_number,
            },
        }

        court_case_event_builder = zeep.xsd.Element(
            "{http://www.jnet.state.pa.us/niem/aopc/CourtCaseRequest/1}CourtCaseRequest",
            zeep.xsd.ComplexType([
                #zeep.xsd.Element(
                #    "{http://www.jnet.state.pa.us/niem/jnet/metadata/1}ExchangeMetadata",                    
                #    zeep.xsd.ComplexType([
                #        zeep.xsd.Element('{http://www.jnet.state.pa.us/niem/jnet/metadata/1}MajorSchemaVersionID',zeep.xsd.Integer()),
                        #zeep.xsd.Element('{http://www.jnet.state.pa.us/niem/jnet/metadata/1}MinorSchemaVersionID',zeep.xsd.Integer()),
                    #])
                #),
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
             {
             'CaseDocketIDCriteria': {'CaseDocketID': docket_number}
            }
        )
        
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
    
    def check_docket_request(self, pending_only = True, record_limit = 100, send_request = True):
        """ Check the status of the provided tracking id.

        Args:
            tracking_id: The tracking ID provided when the request was made
        """
        node = self.zeep.create_message(
            self.zeep.service, 
            'RequestCourtCaseEventInfo',
            #_value_1 = docket_any,
            _value_1 = self._alt_request_metadata(),            
            RecordLimit = record_limit, 
            #UserDefinedTrackingID: xsd:string, 
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
        return(result)


    def retrieve_docket_request(self, tracking_id:str, send_request = True):
        """ Fetch the data!

        Args:
            tracking_id: The tracking ID provided when the request was made
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


    # ----------------------
    # CCE Functions when using OTNs
    # ----------------------

    def request_otn(self, docket_number:str, send_request = True, tracking_id = None):
        """ Make an initial request for a new court case dataset.
        
        Args:
            docket_number: The docket number to request
            tracking_id: If provided, the tracking ID to find the request downstream. If not provided, a semi-random ID will be generated. The tracking_id will be added as a property of the response object. 
            send_request: If True, sends the request to JNET. If False, returns the generated lxml.etree for the request.
        Returns: 
            The requests response, if send_request is True. Otherwise the lxml.etree for the request.
        Errors: 
            An exception along with the error details if the request failed
        """

        # here we generate a new, random tracking id
        if not tracking_id:
            tracking_id = datetime.date.today().isoformat() + f"-{random.randrange(100000, 999999)}"

        if self.test:
            # If in test mode, set the loopback value
            tracking_id = '158354'

        request_metadata = self.metadata_block({
            'UserDefinedTrackingID': tracking_id,
            'ReplyToAddressURI': 'deprecated but required field',
        })
        
        case_docket = {
            'ChargeTrackingIdentificationCriteria': {
                'ChargeTrackingIdentification': docket_number,
            },
        }

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
             {
             'CaseDocketIDCriteria': {'CaseDocketID': docket_number}
            }
        )
        
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
    
    def check_otn_request(self, pending_only = True, record_limit = 100, send_request = True):
        """ Check the status of the provided tracking id.

        Args:
            tracking_id: The tracking ID provided when the request was made
        """
        node = self.zeep.create_message(
            self.zeep.service, 
            'RequestCourtCaseEventInfo',
            #_value_1 = docket_any,
            _value_1 = self._alt_request_metadata(),            
            RecordLimit = record_limit, 
            #UserDefinedTrackingID: xsd:string, 
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
        return(result)


    def retrieve_otn_request(self, tracking_id:str, send_request = True):
        """ Fetch the data!

        Args:
            tracking_id: The tracking ID provided when the request was made
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