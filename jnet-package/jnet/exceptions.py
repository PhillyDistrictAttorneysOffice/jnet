import json 
from .response import SOAPResponse

def error_factory(http_response):
    """ Return a JNET-related error, while attempting to identify common issues. """
    try:
        obj = SOAPResponse(http_response, allow_failure = True)        
    except Exception as e:
        obj = None

    if not obj:
        return(JNETTransportError(http_response))

    # requests that succeed in getting through to JNet will have XML error details in the response text.
    # some of these are knowable, so we'll parse them
    if http_response.status_code == 500:
        if 'Fault' in obj.data and obj.data['Fault']['faultstring'] == 'Authentication_Error':                    
            raise AuthenticationError(http_response = http_response, soap_response = obj)
        elif 'Fault' in obj.data and obj.data['Fault']['faultstring'] == 'Validation_Error':                    
            raise AuthenticationUseridError(http_response = http_response, soap_response = obj)

    # Some other error, just provide as much as we can
    raise JNETTransportError(http_response = http_response, soap_response = obj)


class JNETError(Exception):
    """ THe JNET Error base class, for all JNET-related errors. 

    All jnet errors have the following accessors, though not all will be available in all error contexts:

    Attributes:
        message: The error message
        http_response: The raw repsonse from an http request via the `requests` module
        soap_response: The SOAPResponse object associated with the error
        data: Freeform data associated with the error    
    """
    
    def __init__(self,  message = None, data = None, http_response = None, soap_response = None,):
        self.http_response = http_response
        self.response = soap_response
        if data:
            self.data = data
        elif soap_response:
            self.data = soap_response.data
        else:
            self.data = None

        if not message:
            if soap_response:
                message = f"An Exception occurred with a JNET response!\n\nResponse Data:\n" + json.dumps(soap_response.data)
            elif data:
                message = f"A JNET Exception occurred!\n\nData:\n" + json.dumps(data)
            else:
                message = "A generic JNET error occurred (but no more information was provided)"

        super().__init__(message)

    @property
    def message(self):
        return(self._args[0])
    
    @message.setter
    def message(self, value):
        self._args = (value,)


class JNETTransportError(JNETError):
    """ The general JNET Error class for transport-related errors.
    
    This will render the XML error from the http response by default.
    """
    
    def __init__(self, http_response, message = None, soap_response = None, data = None):

        if not message:
            message = "Request failed!"

        # the default is to render the http_request or soap_response into a nice, pretty message
        message += f"\n\tStatus Code:{http_response.status_code}\n\tReason: {http_response.reason}\n\n--- TEXT ---\n{http_response.text}"

        super().__init__(http_response = http_response, message = None, soap_response = None, data = None)

class NotFound(JNETError):
    """ This exception happens when a request is made to JNET and no matching record is found. 
    
    This differs from the `NotFound` exception because `NotFound` is when a request is identified and JNET indicates it is not found, and `NoResults` is when JNET returns nothing to indicate that it even conducted the search. 
    """

    def __init__(self, message = "Result not Found!", data=None, **kwargs):
       
        if data:
            message += "\n\nError Data:\n" + json.dumps(data, sort_keys = True, indent = 4)
        super().__init__(message = message, data=data, **kwargs)

class NoResults(JNETError):
    """ This exception happens when the user makes a request that has no results. 
    
    This differs from the `NotFound` exception because `NotFound` is when a request is identified and JNET indicates it is not found, and `NoResults` is when JNET returns nothing to indicate that it even conducted the search. 
    """

    def __init__(self, message = "JNET returned no results!", data=None, **kwargs):

        if data:
            message += "\n\nError Data:\n" + json.dumps(data, sort_keys = True, indent = 4)
        
        super().__init__(message = message, data=data, **kwargs)

class AuthenticationError(JNETTransportError):

    def __init__(self, http_response, soap_response = None, **kwargs):
        
        if soap_response:
            try:
                error_code = ': ' + soap_response.data['Fault']['detail']['JNETFaultDetail']['ErrorModuleText']
            except KeyError as ke:
                error_code = ''
        else:
            error_code = ''
        
        message = "Received Authentication_Error from JNET server, which usually is an issue with your client certificate or key" + error_code
        super().__init__(http_response=http_response, soap_response=soap_response, message = message, **kwargs)

class AuthenticationUseridError(JNETTransportError):

    def __init__(self, http_response, soap_response = None, **kwargs):
        
        if soap_response:
            try:
                error_code = ': ' + soap_response.data['Fault']['detail']['JNETFaultDetail']['ErrorModuleText']
            except KeyError as ke:
                error_code = ''
        else:
            error_code = ''
        
        message = "Received Validation_Error from JNET server, which usually is an issue with the user-id in the RequestMetadata. Verify that you are supplying the correct value for your organization and client certificate"
        super().__init__(http_response=http_response, soap_response=soap_response, message = message, **kwargs)
