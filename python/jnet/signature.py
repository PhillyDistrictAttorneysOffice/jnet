import zeep, zeep.wsse
import datetime

class JNetSignature(zeep.wsse.BinarySignature):
    """ Custom class to create a JNET-compliant signature.
    
    The zeep.wsse.BinarySignature class does a lot of the certificate signing steps, but 
    doesn't quite do everything necessary to interact with JNET.  

    The class fixes those issues.
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
    