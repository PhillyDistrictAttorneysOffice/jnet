import os 
import json 
import requests
import zeep
import zeep.wsse
import uuid
import lxml
import xmltodict
import textwrap
import datetime

import pdb,warnings

class SOAPResponse():
    def __init__(self, http_response):
        
        if not http_response.ok:
            raise Exception("Response does not have an okay value.  Failing.")

        self.etree = lxml.etree.fromstring(http_response.text.encode())
    
    @property
    def data(self):
        dictdata = xmltodict.parse(self.xml)
        # unwrap the envelope
        ref = next(iter(dictdata.values()))
        return(ref['SOAP-ENV:Body'])
    
    @property
    def xml(self):
        return(lxml.etree.tostring(self.etree))

    def __str__(self):    
        return(lxml.etree.tostring(self.etree, pretty_print = True).decode('utf-8'))
    

class BinarySignatureTimestamp(zeep.wsse.BinarySignature):
    """
    Someday we should update this to work with a PFXfile.  

    Started: 
    def __init__(
        self,
        pfx_file,
        password = None,
        signature_method = None,
        digest_method = None,
    ):
    
        #key = _make_sign_key(_read_file(keyfile), _read_file(certfile), password)
        import xmlsec
        self.key = xmlsec.Key.from_file(pfx_file, xmlsec.KeyFormat.PKCS12_PEM, password)
        self.digest_method = digest_method
        self.signature_method = signature_method

    
    """
    def apply(self, envelope, headers):
        """
        Slightly modify the apply function to include a timestamp, as a signed signature is required by JNET.

        This code adapted from [this Github issue](https://github.com/mvantellingen/python-zeep/issues/996)
        """        
        # set the created time to now, and generate a 5 minute expiration 
        created = datetime.datetime.utcnow()
        expired = created + datetime.timedelta(minutes = 5)

        # create the Timestamp and add it to the security header
        timestamp = zeep.wsse.utils.WSU('Timestamp')
        timestamp.append(zeep.wsse.utils.WSU('Created', created.replace(microsecond=0).isoformat()+'Z'))
        timestamp.append(zeep.wsse.utils.WSU('Expires', expired.replace(microsecond=0).isoformat()+'Z'))

        security = zeep.wsse.utils.get_security_header(envelope)
        security.append(timestamp)

        # now continue with the digital signature
        super().apply(envelope, headers)
        return(envelope, headers)
    
class Client():
    """
    Baseclass for communicating with jnet.
    """
    wsdl_path = None

    def __init__(self, 
        key_file = None, 
        cert_file = None, 
        config = None, 
        endpoint = 'https://ws.jnet.beta.pa.gov/', 
        server_certificate = None,
        user_id:str = 'jnet.philadelphia_districtattorney_cce_rr',
        debug = True,
    ):
        self.debug = debug
        self._zeep = None
        self.key_file = key_file
        self.cert_file = cert_file
        self.server_certificate = server_certificate
        self.endpoint = endpoint
        self.user_id = user_id

    @property
    def zeep(self):
        if not self._zeep:
            
            if not self.wsdl_path:
                raise Exception("wsdl_path required to be defined as either a class or instance variable")

            client = zeep.Client(
                self.wsdl_path,
                wsse = BinarySignatureTimestamp(
                    self.key_file,
                    self.cert_file,
                )
            )
            # set namespaces for standard schemas
            client.set_ns_prefix("wsa", zeep.ns.WSA)
            client.set_ns_prefix("xsd", zeep.ns.XSD)
            client.set_ns_prefix("xsi", zeep.ns.XSI)

            # WSSE security for client side certificate schemas
            client.set_ns_prefix("wsse-util", zeep.ns.WSU)
            client.set_ns_prefix("wsse", zeep.ns.WSSE)
            client.set_ns_prefix("xmlds", zeep.ns.DS)
            client.set_ns_prefix("wsse", zeep.ns.WSSE)

            # namespaces taht we expect to be in all jnet requests
            client.set_ns_prefix("jnet-m", "http://www.jnet.state.pa.us/niem/jnet/metadata/1")
            client.set_ns_prefix("pacourts", "http://us.pacourts.us/niem/aopc/Extension/2")
            client.set_ns_prefix("jxdm", "http://niem.gov/niem/domains/jxdm/4.0")
            client.set_ns_prefix("niem-core", "http://niem.gov/niem/niem-core/2.0")

            self.configure_client(client)
            self._zeep = client

        return(self._zeep)

    def configure_client(self, zeep):
        raise Exception("This must be configured in the subclass")

    def make_request(self, node):

        if self.debug:
            print("---- REQUEST ----")        
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        headers = {'Content-Type': 'application/soap+xml; charset=utf-8'}
        response = requests.post(
            self.endpoint + self.url_path,            
            headers=headers, 
            data=lxml.etree.tostring(node),                        
            verify = self.server_certificate,
        )

        if not response.ok:
            raise Exception(f"Request failed!\n\tStatus Code:{response.status_code}\n\tReason: {response.reason}\n\n--- TEXT ---\n{response.text}")

        obj = SOAPResponse(response)
        if self.debug:
            print(f"\n\n---- Response ----\n{obj}")        

        return(obj)


class CCE(Client):
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
             # 'ExchangeMetadata': {
             #   'MajorSchemaVersionID':1,
             #   'MinorSchemaVersionID':0,
             #},
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
        
        #send it!
        return(self.make_request(node))
    
    def check_request(self, pending_only = True, record_limit = 100, send_request = True):
        """ Check the status of the provided tracking id.

        Args:
            tracking_id: The tracking ID provided when the request was made
        """
        node = self.zeep.create_message(
            self.zeep.service, 
            'RequestCourtCaseEventInfo',
            RequestMetadata = self.metadata_block(),
            #_value_1 = docket_any,
            RecordLimit = record_limit, 
            #UserDefinedTrackingID: xsd:string, 
            PendingOnly = pending_only,
        )

        if self.debug:
            print("---- REQUEST ----")        
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        if not send_request:
            return(node)
        
        #send it!
        return(self.make_request(node))

    def fetch_request(self, tracking_id:str, send_request = True):
        """ Fetch the data!

        Args:
            tracking_id: The tracking ID provided when the request was made
        """

        metadata_definition = zeep.xsd.Element(
            "{http://www.jnet.state.pa.us/niem/jnet/metadata/1}RequestMetadata",
            zeep.xsd.ComplexType([
                zeep.xsd.Element( "{http://www.jnet.state.pa.us/niem/jnet/metadata/1}RequestAuthenticatedUserID", zeep.xsd.String() ),
            ]),
        )
        RequestMetadata = zeep.xsd.AnyObject(metadata_definition, {
            'RequestAuthenticatedUserID': self.user_id
        })
                
        node = self.zeep.create_message(
            self.zeep.service, 
            'ReceiveCourtCaseEventReply',        
            _value_1 = RequestMetadata,
            FileTrackingID = tracking_id,             
        )
        
        if self.debug:
            print("---- REQUEST ----")        
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        if not send_request:
            return(node)
        
        #send it!
        return(self.make_request(node))