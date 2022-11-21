from .response import SOAPResponse

def error_factory(http_response):
    """ Return a JNET-related error, while attempting to identify common issues. """
    try:
        obj = SOAPResponse(http_response, allow_failure = True)        
    except Exception as e:
        obj = None

    if not obj:
        return(JNETError(http_response))

    # requests that succeed in getting through to JNet will have XML error details in the response text.
    # some of these are knowable, so we'll parse them
    if http_response.status_code == 500:
        if 'Fault' in obj.data and obj.data['Fault']['faultstring'] == 'Authentication_Error':                    
            raise AuthenticationError(http_response, obj)
        elif 'Fault' in obj.data and obj.data['Fault']['faultstring'] == 'Validation_Error':                    
            raise AuthenticationUseridError(http_response, obj)

    # Some other error, just provide as much as we can
    raise JNETError(http_response, obj)


class JNETError(Exception):
    """ THe JNET Error base class, for all JNET-related errors"""
    
    def __init__(self, http_response, soap_response = None, message = None):
        self.http_response = http_response
        self.response = soap_response

        if message:
            super().__init__(message)
        else:
            super().__init__(f"Request failed!\n\tStatus Code:{http_response.status_code}\n\tReason: {http_response.reason}\n\n--- TEXT ---\n{http_response.text}")

    @property
    def message(self):
        return(self._args[0])
    
    @message.setter
    def message(self, value):
        self._args = (value,)


class AuthenticationError(JNETError):

    def __init__(self, http_response, soap_response = None):
        
        try:
            error_code = ': ' + soap_response.data['Fault']['detail']['JNETFaultDetail']['ErrorModuleText']
        except KeyError as ke:
            error_code = ''
        
        message = "Received Authentication_Error from JNET server, which usually is an issue with your client certificate or key" + error_code
        super().__init__(http_response, soap_response, message = message)

class AuthenticationUseridError(JNETError):

    def __init__(self, http_response, soap_response = None):
        
        try:
            error_code = ': ' + soap_response.data['Fault']['detail']['JNETFaultDetail']['ErrorModuleText']
        except KeyError as ke:
            error_code = ''
        
        message = "Received Validation_Error from JNET server, which usually is an issue with the user-id in the RequestMetadata. Verify that you are supplying the correct value for your organization and client certificate"
        super().__init__(http_response, soap_response, message = message)
