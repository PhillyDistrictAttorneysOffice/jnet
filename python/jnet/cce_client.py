import zeep
import lxml
from .client import Client

class CCE(Client):
    """ Subclass to handle Court Case Event request-reply actions."""

    wsdl_path = "cfg/CCERequestReply.wsdl"
    url_path = "AOPC/CCERequest"

    def configure_client(self, client):
        """ The basic request in the CCERequestReply protocol.
        """
        client.set_ns_prefix("aopc-cce", "http://www.jnet.state.pa.us/niem/aopc/CourtCaseRequest/1")
        client.set_ns_prefix("aopc-crr", "http://jnet.state.pa.us/message/aopc/CCERequestReply/1")

    def metadata_block(self, additional = None):
        """ Returns the basic metadata object """

        xmldata = {
            'RequestAuthenticatedUserID': self.user_id,
        }
        if additional:
            xmldata.update(additional)
        return(xmldata)

    def request_docket(self, docket_number:str, send_request = True):
        """ Make an initial request for a new court case dataset.
        
        Args:
            docket_number: The docket number to request
            user_id: The user id for 
        
        Returns: 
            dict that represents the parsed XML returned by request, if successful

        Errors: 
            An exception along with the error details if the request failed
        """

        # here we generate a new, random tracking id
        if self.test:
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
             'CaseDocketIDCriteria': {'CaseDocketID': 'CP-51-CR-0000005-2021'}
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
    
    def check_request(self, pending_only = True, record_limit = 100, send_request = True):
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
        return(self.make_request(node))

    def _alt_request_metadata(self):
        """ Generates the RequestMetadata object for inclusion in fetch and status calls, as it's not defined in the wsdl (or rather, it's only defiend for the request docket)"""
        
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
                

    def fetch_request(self, tracking_id:str, send_request = True):
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