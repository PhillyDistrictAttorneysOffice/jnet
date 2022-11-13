import os 
import sys
import json 
import re
import requests
import zeep
import zeep.wsse
import lxml
import pathlib
import pdb,warnings

from .signature import JNetSignature
from .response import SOAPResponse

class Client():
    """
    Baseclass for communicating with jnet.

    Args:
        config: May be a dict of configuration parameters or a string pointing to a json file with a configuration. By default, will look in the runtime directory for a `settings.json` file.
        key_file: The path to the PEM-format file with the private key for the client certificate. If not provided, uses a config value for `private-key`, or searches the cert/ directory for a file that ends in `webservice.key.pem`.
        cert_file: The path to the PEM-format fie with the client certificate. If not provided, uses a config value for `client-certificate`, or searches the cert/ directory for a file that ends in `webservice.cert.pem`.
        endpoint: The url to send the request to. Accepts a URL or ('jnet', 'beta') shorthand to refer to the standard JNET service endpoints. If not provided, uses a config value for `endpoint`. If still not provided, defaults to the beta endpoint.
        server_certificate: The SSL certificate for the endpoint. If not provided, uses a config value for `server-certificate`, or search the cert directory for a certificate with the same name as the endpoint domain. If `False`, the endpoint's certificate will not be verified, which may help to simplify testing but should not be used in production contexts.
        user_id: The client user id, which is provided by AOPC. This may also be taken from the 'user-id' field of the a config file.
        quiet: If True, does not print detailed messages when actions are taken. Default is False.
    """

    # The wsdl_path must be defined in each subclass and specify the WSDL file for the requests 
    # that may be included
    wsdl_path = None
    
    # The URL Path is the subclass-specific path for the endpoint, 
    # i.e. for "https://ws.jnet.beta.pa.gov/AOPC/CCERequest", 
    # the "endpoint" is "https://ws.jnet.beta.pa.gov/" and the "url_path" is "/AOPC/CCERequest". 
    # These are separate because the url_path is expected to be the same for all requests in a class, 
    # but the endpoint can change from one request to another (beta vs production)
    url_path = None

    def __init__(
        self, 
        config = None,
        key_file:str = None, 
        cert_file:str = None, 
        endpoint:str = None, 
        server_certificate:str = None,
        user_id:str = None,
        verbose:bool = False,
        test:bool = False,
    ):

        self._zeep = None
        self.verbose = verbose
        self.test = test

        if config:
            if type(config) is not dict:
                with open(config) as fh:
                    config = json.load(fh)
        elif os.path.exists('settings.json'):                    
            with open('settings.json') as fh:
                config = json.load(fh)
        
        if key_file:
            self.key_file = key_file
        elif config and "private-key" in config:
            self.key_file = config['private-key']
        else:
            self.key_file = self.find_certificate("webservice.key.pem")

        if cert_file:
            self.cert_file = cert_file
        elif config and "client-certificate" in config:
            self.cert_file = config['client-certificate']
        else:
            self.cert_file = self.find_certificate("webservice.cert.pem")

        if endpoint:
            if endpoint == 'jnet':
                self.endpoint = 'https://ws.jnet.pa.gov/'
            elif endpoint == 'beta':
                self.endpoint = 'https://ws.jnet.beta.pa.gov/'
            else:
                self.endpoint = endpoint                
        elif config and 'endpoint' in config:
            # this may be a fully qualfied endpoint that includes the path and may not be correct,
            # so we do a search
            m = re.search(r'^((http(s)://)?[^\/]+\/)', config['endpoint'])
            if not m:
                raise Exception(f"Cannot identify the endpoint from {config['endpoint']}")
            else:
                self.endpoint = m.group(1)
        else:
            self.endpoint = 'https://ws.jnet.beta.pa.gov/'            

        if server_certificate or server_certificate is False:
            self.server_certificate = server_certificate
        elif config and 'server-certificate' in config:
            self.server_certificate = config['server-certificate']
        else: 
            # find a certificate for the endpoint 
            m = re.search(r'(https?://)?([^\/]+)', self.endpoint)
            if m:
                self.server_certificate = self.find_certificate(m.group(2) + ".crt")
            
            if not self.server_certificate:
                raise Exception(f"Cannot determine a server certificate for the endpoint {self.endpoint}")
        
        if user_id:
            self.user_id = user_id
        elif config and 'userid' in config:
            self.user_id = config['userid']
        elif config and 'user-id' in config:
            self.user_id = config['user-id']
        else:
            raise Exception("No Authenticated User ID provided")

    def find_certificate(self, strmatch):
        """ Attempt to find a certificate in the cert/ folder that matches the string. """

        def recurse_subdir(dirpath):
            for fobj in dirpath.iterdir():
                if not fobj.is_dir():
                    if strmatch in fobj.name:
                        return(fobj)
                else:                    
                    result = recurse_subdir(fobj)
                    if result:
                        return(result)

        cert = pathlib.Path("cert")
        if not cert.exists() or not cert.is_dir():
            raise FileNotFoundError(f"There is no cert/ directory to attempt to find a certificate matching {strmatch}")
        
        certfile = recurse_subdir(cert)
        if not certfile:
            raise FileNotFoundError(f"Could not find a certificate matching {strmatch} in the cert/ folder")
        
        return(certfile.as_posix())


    @property
    def zeep(self):
        """ The actual zeep client for handling requests.  
        
        Initializes the default client and then calls `configure_client(client)`, which must be defined in the subclass. The default client includes standard namescapes for web transport, client certificates, gjxdm, and jnet.        
        """
        if not self._zeep:
            
            if not self.wsdl_path:
                raise Exception("wsdl_path required to be defined as either a class or instance variable")

            client = zeep.Client(
                self.wsdl_path,
                wsse = JNetSignature(
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
        """ Function for customizing the client, including setting additional namespace prefixes """
        raise Exception("This must be configured in the subclass")

    def get_endpoint_url(self, node=None):
        """ Gets the full endpoint url, usually just `self.endpoint + self.url_path`
        
        Function provided to allow for per-request customization in subclasses.
        """
        full_url = self.endpoint
        # join with url_path, but avoid duplicate /'s
        if full_url[-1] == '/' and self.url_path[0] == '/':
            full_url += self.url_path[1:]
        else:
            full_url += self.url_path
        
        return(full_url)

    def make_request(self, node):
        """ Sends the request to jnet. 
        
        Primarily intended to be an internal function at the end of subclass-specific functions.
        """
        if self.verbose:
            print("---- REQUEST ----")        
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        headers = {'Content-Type': 'application/soap+xml; charset=utf-8'}

        if not self.url_path:
            raise Exception("No url path provided, which must be defined in the subclass to specify the full endpoint to make a request to.")

        try:            
            response = requests.post(
                self.get_endpoint_url(node),
                headers=headers, 
                data=lxml.etree.tostring(node),                        
                verify = self.server_certificate,
            )
        except requests.exceptions.SSLError as sslerr:
            # it's easy to forget that requests expects server certificates to be the entire
            # chain and not just the endpoint - so we'll add an extra message.
            if self.server_certificate and "certificate verify failed: unable to get local issuer" in f"{sslerr}":
                print("***Server Certificate verification failed****\nNote: This can occur if you specified the SSL certificate for the endpoint but did not include the full certificate chain. \nRun with `server_certificate = False` to temporarily skip verification", file = sys.stderr)
            raise

        if not response.ok:
            # requests that succeed in getting through to JNet will have XML error details in the response text.
            # So print it all out in the Exception.
            raise Exception(f"Request failed!\n\tStatus Code:{response.status_code}\n\tReason: {response.reason}\n\n--- TEXT ---\n{response.text}")

        obj = SOAPResponse(response)
        if self.verbose:
            print(f"\n\n---- Response ----\n{obj}")        

        return(obj)

