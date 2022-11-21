import zeep, zeep.wsse
import datetime

class JNetSignature(zeep.wsse.MemorySignature):
    """ Custom class to create a JNET-compliant signature.
    
    The zeep.wsse.BinarySignature class does a lot of the certificate signing steps, but 
    doesn't quite do everything necessary to interact with JNET, and it also requires a filepath for the keys instead of allowing us to load them
    separately and pass them in as binary objects.

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

        # now sign the envelope, following the same process as the 
        # BinarySignatures 
        key = zeep.wsse.signature._make_sign_key(self.key_data, self.cert_data, self.password)
        zeep.wsse.signature._sign_envelope_with_key_binary(
            envelope, key, self.signature_method, self.digest_method
        )
        return(envelope, headers)
    