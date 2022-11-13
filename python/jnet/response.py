import lxml
import xmltodict
import re 
import json


regex = re.compile(r'^[^:]+:')

class SOAPResponse():
    """ A class to encapsulate and simplify JNET responses.  

    Printing the response object or including it in string form will pretty-print the XML. 
    Functions `xml` and `json` provide minified representations of the data, and `data` 
    returns the data in python dictionary format. Additional properties may also be added
    by specific requests.    
    """
    def __init__(self, http_response, **extra_params):
        
        if not http_response.ok:
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
        if type(struct) is dict:
            newdata = {}
            for k,v in struct.items():
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
