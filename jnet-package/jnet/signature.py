# This program is part of the jnet package.  
# https://github.com/PhillyDistrictAttorneysOffice/jnet

# Copyright (C) 2022-present
# Kevin Crouse, The Philadelphia District Attorney's Office, City of Philadelphia, PA.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/gpl-3.0.en.html>

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
    