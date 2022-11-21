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

from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption,PublicFormat
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates



from .signature import JNetSignature
from .response import SOAPResponse

class Client():
    """
    Baseclass for communicating with jnet.

    Note that at present, JNet uses PKCS8-formatted certificates (PFX extension), 
    but the requests use the private key and client certificate in PEM format. In
    the future possibility of separating out the private key and client certificate, it would be trivial to add arguments that connect to the `client_pem_key` and `client_pem_cert` properties.

    Class Properties:
        wsdl_path: The wsdl_path must be defined in each subclass and specify the WSDL file for the requests that may be included.
        url_path: The URL Path is the subclass-specific path for the endpoint, i.e. for "https://ws.jnet.beta.pa.gov/AOPC/CCERequest", the "endpoint" is "https://ws.jnet.beta.pa.gov/" and the "url_path" is "/AOPC/CCERequest". These are separate because the url_path is expected to be the same for all requests in a class, but the endpoint can change from one request to another (beta vs production)

    """

    wsdl_path = None
    url_path = None

    def __init__(
        self, 
        config = None,
        client_certificate:str = None,
        client_password:str = None,
        endpoint:str = None, 
        server_certificate:str = None,
        user_id:str = None,
        verbose:bool = False,
        test:bool = False,
    ):
        """     
        Args:
            verbose: If True, prints detailed messages when actions are taken so you can trace the messages built and received. Default is False.
            test: If True, sets parameters in order to use the pre-production testing settings for JNet.
            config: Set the dictionary for the configuration. 
            client_certificate: Custom override for the property - see details in property documentation. 
            client_password: Custom override for the property - see details in property documentation.
            endpoint: Custom override for the property - see details in property documentation.
            server_certificate: Custom override for the property - see details in property documentation. 
            user_id: Custom override for the property - see details in property documentation.
        """

        self._zeep = None
        self.error = None
        self._cert_data = None

        self.verbose = verbose
        self.test = test

        # naively set all user/config settings,
        # though if not provided the property
        # setters will set defaults
        self.config = config
        self.client_certificate = client_certificate
        self.client_password = client_password
        self.endpoint = endpoint
        self.server_certificate = server_certificate
        self.user_id = user_id
        

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
                    self.client_pem_key,
                    self.client_pem_cert,
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

    @property
    def cert_data(self):
        """ dict: Retains the data for the private_key and client certificate as parsed from the client certificate file. """
        if not self._cert_data:
            if not self.client_certificate:
                raise FileNotFoundError("No client certificate provided or found")
            if not os.path.exists(self.client_certificate):
                raise FileNotFoundError(f"Provided '{self.client_certificate}' as the client certificate, but no file exists at that location")
            if not self.client_password:
                raise Exception("No client password to decrypt the client certificate")
            pfx = pathlib.Path(self.client_certificate).read_bytes()
            private_key, main_cert, add_certs = load_key_and_certificates(pfx, self.client_password.encode('utf-8'), None)
            self._cert_data = {
                'private_key': private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()),
                'certificate': main_cert.public_bytes(Encoding.PEM).decode()
            }

        return(self._cert_data)

    @property
    def client_pem_key(self):
        """ The PEM-formated private key for the client certificate. This is pulled from the PFX client certificate. """

        return(self.cert_data['private_key'])

    @property
    def client_pem_cert(self):
        """ The PEM-formated main client certificate. This is pulled from the PFX client certificate. """
        return(self.cert_data['certificate'])


    @property
    def config(self):
        """ A dict that provides configuration details for the client. If set, it may be a dict of configuration parameters or a string pointing to either a json file with the custom config or a folder with a `settings.json` file. If not provided, a `settings.json` file in the runtime directory will be used, if it exists."""
        return(self._config)

    @config.setter
    def config(self, config):

        if not config:
            # the default is triggered in the 
            # constructor
            if os.path.exists('settings.json'):                    
                with open('settings.json') as fh:
                    self._config = json.load(fh)
            else:
                self._config = None
            return

        if type(config) is dict:
            self._config = config
        elif os.path.isdir(config) and os.path.exists(config + os.sep + '/settings.json'):
            with open(config + os.sep + '/settings.json') as fh:
                self._config = json.load(fh)
        else:
            with open(config) as fh:
                self._config = json.load(fh)
    
    @property
    def client_certificate(self):
        """The PKCS8/pfx client-side certificate file that is used to sign requests to JNET. This is provided by JNet. If not provided to the object constructor, checks the config for 'client-certificate', and following, searches the `cert/` directory for a file that ends in `webservice.pfx`."""
        return(self._client_certificate)

    @client_certificate.setter
    def client_certificate(self, client_certificate):
        if client_certificate:
            self._client_certificate = client_certificate
        elif self.config and "client-certificate" in self.config:
            self._client_certificate = self.config['client-certificate']
        else:
            self.client_certificate = self.find_certificate("webservice.pfx")

    @property
    def client_password(self):
        """The password to decrypt the client_certificate. If not provided to the constructor, checks the config for 'client-password'."""
        return(self._client_password)

    @client_password.setter
    def client_password(self, client_password):
        if client_password:
            self._client_password = client_password
        elif self.config and "client-password" in self.config:
            self._client_password = self.config['client-password']
        else:
            self._client_password = None

    @property
    def endpoint(self):
        """The url to send the request to. Accepts a URL or ('jnet', 'beta') shorthand to refer to the standard JNET service endpoints. If not provided, checks the config for 'endpoint'. If still not provided, defaults to the beta endpoint."""
        return(self._endpoint)

    @endpoint.setter
    def endpoint(self, endpoint):
        if endpoint:
            if endpoint == 'jnet':
                self._endpoint = 'https://ws.jnet.pa.gov/'
            elif endpoint == 'beta':
                self._endpoint = 'https://ws.jnet.beta.pa.gov/'
            else:
                self._endpoint = endpoint                
        elif self.config and 'endpoint' in self.config:
            # this may be a fully qualfied endpoint that includes the path and may not be correct,
            # so we do a search
            m = re.search(r'^((http(s)://)?[^\/]+\/)', self.config['endpoint'])
            if not m:
                raise Exception(f"Cannot identify the endpoint from {self.config['endpoint']}")
            else:
                self._endpoint = m.group(1)
        else:
            self._endpoint = 'https://ws.jnet.beta.pa.gov/'            

    @property
    def server_certificate(self):
        """The SSL certificate for the endpoint. If not provided, checks the config for `server-certificate`, or searches the `cert/` directory for a certificate with the same name as the endpoint domain. If `False`, the endpoint's certificate will not be verified, which may help to simplify testing but should not be used in production contexts. """
        return(self._server_certificate)

    @server_certificate.setter
    def server_certificate(self, server_certificate):
        if server_certificate or server_certificate is False:
            self._server_certificate = server_certificate
        elif self.config and 'server-certificate' in self.config:
            self._server_certificate = self.config['server-certificate']
        else: 
            # find a certificate for the endpoint 
            m = re.search(r'(https?://)?([^\/]+)', self.endpoint)
            if m:
                self._server_certificate = self.find_certificate(m.group(2) + ".crt")
            
            if not self._server_certificate:
                raise Exception(f"Cannot determine a server certificate for the endpoint {self.endpoint}")

    @property
    def user_id(self):
        """The client user id, which is provided by AOPC. If not provided, checks the config for 'user-id'."""
        return(self._user_id)

    @user_id.setter
    def user_id(self, user_id):
        if user_id:
            self._user_id = user_id
        elif self.config and 'userid' in self.config:
            self._user_id = self.config['userid']
        elif self.config and 'user-id' in self.config:
            self._user_id = self.config['user-id']
        else:
            raise Exception("No Authenticated User ID provided")

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
            from .exceptions import error_factory
            raise error_factory(response)

        obj = SOAPResponse(response)
        if self.verbose:
            print(f"\n\n---- Response ----\n{obj}")        

        return(obj)

