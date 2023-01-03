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

import lxml
import xmltodict
from collections import OrderedDict
import re 
import json


regex = re.compile(r'^[^:]+:')
xmlnsre = re.compile(r'^\@xmlns(:[\w\-]+)?$')

class SOAPResponse():
    """ A class to encapsulate and simplify JNET responses.  

    Constructor Args:
        http_response: A response with SOAP xml contact that follows the interface for a requests.post response. Optional if xml is provided instead.
        xml: An lxml.etree object to set as the underlying data. Allowed only as an alternative to http_response
        allow_failure: If True, process a response that is not "ok." By default, an error is thrown on a non-good response to minimize hard to track down errors.  Default is False.
        **kwargs: Any additional parameters will be added as accessors on the object, allowing custom clients to quickly add features to the response objects without requiring subclassing.

    Printing the response object or including it in string form will pretty-print the XML. 
    Functions `xml` and `json` provide minified representations of the data, and `data` 
    returns the data in python dictionary format. Additional properties may also be added
    by specific requests.    
    """
    def __init__(self, http_response = None, xml = None, allow_failure = False, **extra_params):
        
        if http_response is None:
            if xml is None:
                raise Exception("Neither an http_response nor an xml object provided")
            if type(xml) is str:
                self.xml = xml
            else:
                self._xml = xml
        else:
            if not http_response.ok and not allow_failure:
                raise Exception("Response does not have an okay value.  Failing.")

            self.xml = http_response.text #http_response.text.encode()
        
        self._data = None
        if extra_params:
            self._add_properties(**extra_params)
    
    def _add_properties(self, **kwargs):
        """ Adds additional properties for the response.  
        
        This allows quick customization of the response by the request class when
        there are details to provide beyond the xml fields.
        """
        for k,v in kwargs.items():
            setattr(self, k, v)
    
    @classmethod
    def _recurse_datastruct(cls, struct):
        if type(struct) in (dict, OrderedDict):
            newdata = {}
            for k,v in struct.items():
                if xmlnsre.fullmatch(k):
                    # skip xml namespace keys
                    continue
                newdata[re.sub(regex, '', k)] = cls._recurse_datastruct(v)                        
            return(newdata)
        elif type(struct) in (tuple, list):
            return([cls._recurse_datastruct(var) for var in struct])
        else:
            return(struct)

    @property
    def xml(self):
        """Return the lxml etree representing the complete xml. 
        
        The setter can take either a regular string or a binary string, which will be processed into an lxml.etree"""
        return(self._xml)

    @xml.setter
    def xml(self, xml_string):
        if type(xml_string) is str:
            self._xml = lxml.etree.fromstring(xml_string.encode())
        else:
            self._xml = lxml.etree.fromstring(xml_string)

    @property
    def xml_string(self):
        """ Returns a string representing the XML. Note that this is minfiied and suitiable for writing to a file.  For a pretty representation, use the object in string form."""
        return(lxml.etree.tostring(self.xml))

    @property
    def data(self):        
        """ Reduce the XML data to a pythonic data structure. 
        
        This function converts the xml into a dict and then strips out all of the XML
        namespaces to give a data structure that is more accessible to the average user.

        Because this can be a comparatively time consuming processes, it is done lasily
        on first access and the result is saved for future accesses.
        """

        if not self._data:
            # process the first time it's calle 
            # unwrap the envelope
            bodyregex = re.compile(r':body$', re.I)
            rawdata = next(iter(xmltodict.parse(self.xml_string).values()))
            # find the body            
            for k in rawdata.keys():
                if bodyregex.search(k):
                    rawdata = rawdata[k]
                    break
            self._data = self._recurse_datastruct(rawdata)
            
        return(self._data)
    
    @property
    def data_string(self):
        """ Returns a string representing the response data. """
        return(json.dumps(self.data, sort_keys = True, indent = 4))

    def print_data(self):
        """ Print the response data to the screen. Shorthand for print(obj.data_string())"""
        print(self.data_string)

    def __str__(self):    
        """Return a pretty string of the xml for printing or output."""
        return(lxml.etree.tostring(self.xml, pretty_print = True).decode('utf-8'))
