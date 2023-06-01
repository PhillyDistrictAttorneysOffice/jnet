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

import zeep
import lxml
import datetime
import random
import re
import time
from .client import Client
from .exceptions import *
import warnings


# for debugging
import pdb

class CCE(Client):
    """ Subclass to handle Court Case Event request-reply actions (which are sent to /AOPC/CCERequest endpoint)."""

    wsdl_path = "wsdl/CCERequestReply.wsdl"
    url_path = "AOPC/CCERequest"

    def configure_client(self, client):
        """ Sets the namespace prefixes for the CCERequestReply protocol. """
        client.set_ns_prefix("aopc-cce", "http://www.jnet.state.pa.us/niem/aopc/CourtCaseRequest/1")
        client.set_ns_prefix("aopc-crr", "http://jnet.state.pa.us/message/aopc/CCERequestReply/1")

    #----------------------
    # Private Helper Functions
    #----------------------

    def _metadata_block(self, additional = None):
        """ Returns the basic RequestMetadata object, for when the metadata block is expected by the WSDL.

        Note that if the RequestMetadata is pushed into an `Any` block, you will need to use `_alt_request_metadata()` because the definition needs to be provided.

        Returns:
            dict of fields to set the `RequestMetadata` parameter to.
        """

        xmldata = {
            'RequestAuthenticatedUserID': self.user_id,
        }
        if additional:
            xmldata.update(additional)
        return(xmldata)


    def _alt_request_metadata(self):
        """ Generates the RequestMetadata object suitable to map to an `Any` type block.

        This creates a `zeep.xsd.AnyObject` suitable to map to an `Any` param defined in the WSDL file and that represents the `RequestMetadata` entity. This happens because `RequestMetadata` is required by the server but not consistently/accurately defined in the WSDL file provided by JNET."""

        metadata_definition = zeep.xsd.Element(
            "{http://www.jnet.state.pa.us/niem/jnet/metadata/1}RequestMetadata",
            zeep.xsd.ComplexType([
                zeep.xsd.Element( "{http://www.jnet.state.pa.us/niem/jnet/metadata/1}RequestAuthenticatedUserID", zeep.xsd.String() ),
            ]),
        )
        RequestMetadata = zeep.xsd.AnyObject(metadata_definition, {
            'RequestAuthenticatedUserID': self.user_id
        })
        return(RequestMetadata)

    # ----------------------
    # CCE Functions when using Docket Numbers
    # ----------------------

    def fetch_docket_data(self, docket_number:str, timeout:int = 100, quiet:bool = False):
        """ Request data for a docket and wait until it is available.

        This is an all-in-one function that will wait/block until the data is available (or until the timeout expires).

        Args:
            docket_number: The docket number to request
            timeout: How long to wait before throwing an exception
            quiet: If True, do not print time-based poll updates. Default is False.
        Returns:
            list: all data returned by JNET for the docket number, in no particular order.
        Raises:
            jnet.exceptions.NotFound if the docket_number is not found.
            jnet.exceptions.QueuedError if the request is queued and won't be available until after 5pm.
            TimeoutError if the data is not returned beofre the timeout expires.
        """
        if not timeout:
            timeout = 80
        request = self.request_docket(docket_number)

        timer = time.time()
        time.sleep(5)
        # first, check with check = False to avoid exceptions
        data = self.check_requests(
            tracking_id = request.tracking_id,
            docket_number = docket_number,
            check = False,
        )
        print(f"Waiting and polling for {docket_number} to be ready")
        while not len(data):
            elapsed_time = time.time() - timer
            if elapsed_time > timeout:
                raise TimeoutError(f"Request to fetch JNET data for docket {docket_number} could not be completed within {timeout} seconds")
            print(f"    ... data not yet available after {format(elapsed_time, '.1f')} s. Waiting more.")
            time.sleep(10)
            data = self.check_requests(
                tracking_id = request.tracking_id,
                docket_number = docket_number,
                check = False,
            )
        data = self.retrieve_requests(
            tracking_id = request.tracking_id,
            docket_number = docket_number,
        )
        return(data)



    def request_docket(self, docket_number:str, send_request = True, tracking_id = None):
        """ Make an initial request for a new court case dataset based on the docket number.

        Args:
            docket_number: The docket number to request
            tracking_id: If provided, the tracking ID to find the request downstream. If not provided, a semi-random ID will be generated. The tracking_id will be added as a property of the response object.
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
        Returns:
            The SOAPResponse for the request if `send_request` is `True`. Otherwise the lxml.etree for the request.
        Errors:
            An exception along with the error details if the request failed
        """

        # here we generate a new, random tracking id
        if not tracking_id:
            tracking_id = datetime.date.today().isoformat() + f"-{random.randrange(100000, 999999)}"

        request_metadata = self._metadata_block({
            'UserDefinedTrackingID': tracking_id,
            'ReplyToAddressURI': 'deprecated but required field',
        })

        #
        # The current WSDL does not correctly define the case docket information, and
        # only provide a nondescript Any entity, so we'll need to custom build the element.
        # If this changes in the future, this should be the correct data representation.
        #
        case_docket_data = {
            'CaseDocketIDCriteria': {
                'CaseDocketID': docket_number,
            },
        }

        # - Custom Build xml to submit as the main docket information
        court_case_event_builder = zeep.xsd.Element(
            "{http://www.jnet.state.pa.us/niem/aopc/CourtCaseRequest/1}CourtCaseRequest",
            zeep.xsd.ComplexType([
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
            case_docket_data,
        )
        # - End custom build of docket xml

        node = self.zeep.create_message(
            self.zeep.service,
            'RequestCourtCaseEvent',
            RequestMetadata = request_metadata,
            _value_1 = docket_any,
        )
        if not send_request:
            return(node)

        #send it, but add the tracking number to the response
        result = self.make_request(node)
        result._add_properties(tracking_id=tracking_id, docket_number=docket_number)

        return(result)


    def request_otn(self, otn:str, send_request = True, tracking_id = None):
        """ Make an initial request for a new court case dataset based on the Offense Tracking Number (OTN).

        Args:
            otn: The Offense Tracking Number (OTN) to request
            tracking_id: If provided, the tracking ID to find the request downstream. If not provided, a semi-random ID will be generated. The tracking_id will be added as a property of the response object.
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
        Returns:
            The SOAPResponse for the request if `send_request` is `True`. Otherwise the lxml.etree for the request.
        Errors:
            An exception along with the error details if the request failed
        """

        # here we generate a new, random tracking id
        if not tracking_id:
            tracking_id = datetime.date.today().isoformat() + f"-{random.randrange(100000, 999999)}"

        request_metadata = self._metadata_block({
            'UserDefinedTrackingID': tracking_id,
            'ReplyToAddressURI': 'deprecated but required field',
        })

        # If the WSDL is updated to handle the specific schema for the OTN request
        # this should be the appropriate data structure.
        otn_data = {
            'ChargeTrackingIdentificationCriteria': {
                'ChargeTrackingIdentification': {
                    'IdentificationID': otn,
                },
            },
        }

        otn_court_case_event_builder = zeep.xsd.Element(
            "{http://www.jnet.state.pa.us/niem/aopc/CourtCaseRequest/1}CourtCaseRequest",
            zeep.xsd.ComplexType([
                zeep.xsd.Element(
                    "{http://us.pacourts.us/niem/aopc/Extension/2}ChargeTrackingIdentificationCriteria",
                    zeep.xsd.ComplexType([
                        zeep.xsd.Element(
                            "{http://niem.gov/niem/domains/jxdm/4.0}ChargeTrackingIdentification",
                            zeep.xsd.ComplexType([
                                zeep.xsd.Element( "{http://niem.gov/niem/niem-core/2.0}IdentificationID", zeep.xsd.String() ),
                            ]),
                        ),
                    ])
                ),
            ]),
        )

        otn_any = zeep.xsd.AnyObject(
            otn_court_case_event_builder,
            otn_data,
        )

        node = self.zeep.create_message(
            self.zeep.service,
            'RequestCourtCaseEvent',
            RequestMetadata = request_metadata,
            _value_1 = otn_any,
        )
        if not send_request:
            return(node)

        #send it, but add the tracking number to the response
        result = self.make_request(node)
        result._add_properties(tracking_id=tracking_id)

        return(result)

    def check_requests(self, tracking_id = None, *, pending_only = True, record_limit = 500, docket_number = None, otn = None, clean = True, check = True, send_request = True, raw = False):
        """ Check the status of existing requests. The request may include records that were requested both by OTN or by Docket Number - they are not designated to separate queues.

        Args:
            tracking_id: If provided, filter requests for the provided tracking number and throw a JNET.exceptions.RequestNotFound exception is not found.
            pending_only: If True, only list prending requests. Default is True.
            record_limit: Set the maximum return count. Default is 500.
            docket_number: If provided, filter requests for the provided docket number and throw a JNET.exceptions.RequestNotFound exception is not found.
            otn: If provided, filter requests for the provided OTN and throw a JNET.exceptions.RequestNotFound exception is not found.
            clean: If True, calls `clean_info_response_data` to return cleaner data. If False, returns the full data. Default is True.
            check: If True, raises an exception if a docket_number or otn *is specified* and cannot be found. If False, it will return the not found records. If neither `otn` nor `docket_number` is specified, this parameter is ignored. Default is True.
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
            raw: If True, returns the raw SOAPResponse. If False, converts to data. If `docket_number` or `otn` is provided, this parameter is ignored and interpreted as `False`. Default is False.
        Returns:
            If `send_request` is `False`, returns the lxml.etree for the request.
            If `raw` is `True`, returns the SOAPResponse returned from the request.
            Otherwise, returns an array of data elements.
        """
        node = self.zeep.create_message(
            self.zeep.service,
            'RequestCourtCaseEventInfo',
            _value_1 = self._alt_request_metadata(),
            RecordLimit = record_limit,
            UserDefinedTrackingID = tracking_id,
            PendingOnly = pending_only,
        )

        if self.verbose:
            print("---- REQUEST ----")
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        if not send_request:
            return(node)

        #send it!
        result = self.make_request(node)

        # change the record count to an integer
        result.data['RequestCourtCaseEventInfoResponse']['RecordCount'] = int(result.data['RequestCourtCaseEventInfoResponse']['RecordCount']
        )

        if result.data['RequestCourtCaseEventInfoResponse']['RecordCount'] == 0:
            # -- no records!
            if pending_only:
                errmessage = "No pending CCE Requests exist at all"
            else:
                errmessage = "No CCE Requests exist at all"
            if docket_number and check:
                raise NoResults(errmessage + f", let alone for docket {docket_number}", soap_response = result)
            elif otn and check:
                raise NoResults(errmessage + f", let alone for OTN {otn}", soap_response = result)
            elif raw:
                return(result)
            return([])
        elif type(result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']) is dict:
            # make the metadata an array even if it only contains 1 element
            result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'] = [ result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'] ]

        if result.data['RequestCourtCaseEventInfoResponse']['RecordCount'] == record_limit:
            warnings.warn(f"check_requests returned the limit of {record_limit} records - you likely are not getting all outstanding requests")

        # -- if docket_number or tracking_id are provided, filter here
        if docket_number:
            filtered_results = []
            match_string = 'DOCKET NUMBER ' + docket_number.upper()
            for req in result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']:
                for header in req['HeaderField']:
                    if header['HeaderName'] == 'ActivityTypeText':
                        if match_string in header['HeaderValueText']:
                            # matched!
                            filtered_results.append(req)
                        elif 'DOCKET NUMBER ' in header['HeaderValueText']:
                            # some other docket number - skip
                            continue
                        elif 'DOCKET NOT FOUND: ' + docket_number.upper() in  header['HeaderValueText']:
                            # AOPC received the request, but didn't find anything!
                            if check:
                                raise NotFound(f"AOPC returned NOT FOUND for Docket Number {docket_number}", data = req, soap_response = result)
                            else:
                                filtered_results.append(req)
                        elif 'DOCKET' in header['HeaderValueText'] and docket_number.upper() in header['HeaderValueText']:
                            raise Exception(f"Header Value appears to refer to dockets but not understood by the CCE Client: '{header['HeaderValueText']}'")
                        else:
                            # we don't know what this is (or it is related to another docket number)... so just keep on keeping on
                            continue

            if not len(filtered_results):
                if check:
                    raise NoResults(f"No CCE Request for docket number {docket_number} found, but no 'NOT FOUND' requests identified", soap_response = result)
                return([])
            if clean:
                return(self.clean_info_response_data(filtered_results))
            else:
                return(filtered_results) # this could be empty if check is False

        if otn:
            # TODO: this probably doesn't work right now.
            filtered_results = []
            requests_not_found = []
            match_string = 'OTN ' + otn.upper()
            for req in result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata']:
                for header in req['HeaderField']:
                    if header['HeaderName'] == 'ActivityTypeText':
                        if match_string in header['HeaderValueText']:
                            filtered_results.append(req)
                        elif 'OTN NOT FOUND' in header['HeaderValueText']:
                            requests_not_found.append(req['UserDefinedTrackingID'])
                        elif 'OTN' in header['HeaderValueText']:
                            raise Exception(f"Header Value appears to refer to OTN but not understood by the CCE Client: '{header['HeaderValueText']}'")

            if len(filtered_results):
                if clean:
                    return(self.clean_info_response_data(filtered_results))
                return(filtered_results)
            elif requests_not_found:
                raise NotFound(f"No CCE Request for OTN {otn} found, and JNET returned NOT FOUND for tracking numbers {requests_not_found}", data = requests_not_found, soap_response = result)
            else:
                raise NoResults(f"No CCE Request for OTN {otn} found, but no 'NOT FOUND' requests identified", soap_response = result)

        if raw:
            return(result)
        elif clean:
            return(self.clean_info_response_data(result.data))
        return(result.data['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'])


    def retrieve_file_data(self, file_id:str, check:bool = True, allow_queued:bool = True, send_request:bool = True, raw:bool = False):
        """ Fetch the data!

        This is a low-level request with a required file_id. If you are looking to retrieve the data based on Docket Number, OTN, etc, look at `retrieve_requests`

        Also if you are using this in batch mode with multiple files, be careful!  `check == True` by default because it is assumed that if you are making a single file request, you know what you are doing and you probably only want real requests. A successful message will take the file out of pending status, which affects checking the request status, and so if you are receiving multiple files, and an exception is thrown after some of them are retrieved, the ones that were successful may be removed from future searches / fetches.

        Args:
            file_id: The File Tracking ID provided when the request was made
            check: If True, checks the response metadata and throws an error for anything other than a successful document
            allow_queued: If False, throw a QueuedError if the record is Queued (and check is True). If check is False, this parameter is ignored. The data in a queued record is accurate, but Charging and Financial data is missing, and so `allow_queued = False` ensures that you have only complete records. Default is True, allowing the return of Queued records.
            send_request: If True, sends the request to JNET and returns to the SOAPResponse. If False, returns the generated lxml.etree for the request only.
            raw: If True, returns the SOAPResponse object instead of the converted data. Default is False.
        Returns:
            The SOAPResponse for the request if `send_request` is `True`. Otherwise the lxml.etree for the request.
        Raises:
            jnet.exceptions.NoResults if check is True and the file_id does not exist.
            jnet.exceptions.NotFound if check is True and the Docket Number that was requested does not exist.
            jnet.exceptions.JNETError if unknown errors are received.
        """

        node = self.zeep.create_message(
            self.zeep.service,
            'ReceiveCourtCaseEventReply',
            _value_1 = self._alt_request_metadata(),
            FileTrackingID = file_id,
        )

        if self.verbose:
            print("---- REQUEST ----")
            print(lxml.etree.tostring(node, pretty_print = True).decode('utf-8'))

        if not send_request:
            return(node)

        #send it!
        result = self.make_request(node)

        # see if there's an error
        data = result.data
        # determine what the non-error return value would be
        if raw:
            return_value = result
        else:
            return_value = data

        # -- these errors happen if the file_id is invalid / does not exist-
        #    We throw the error here because there's no data, so we aren't worried about data loss
        if "ResponseStatusCode" in data["ReceiveCourtCaseEventReply"] and \
            data["ReceiveCourtCaseEventReply"]["ResponseStatusCode"] == "ERROR":
            # return the raw stuff if check is False
            if not check:
                return(return_value)
            if data["ReceiveCourtCaseEventReply"]["ResponseActionText"] == "No Record Found.":
                raise NoResults(
                    f"JNET does not have a record for File ID {file_id}",
                    data = data,
                    soap_response = result,
                )
            elif "ResponseActionText" in data["ReceiveCourtCaseEventReply"]:
                raise JNETError(f"Attempt to retrieve file {file_id} led to an unknown ERROR {data['ReceiveCourtCaseEventReply']['ResponseActionText']}", data = data, soap_response = result)
            else:
                raise JNETError(f"Attempt to retrieve file {file_id} led to an unknown ERROR!", data = data, soap_response = result)

        metadata = data["ReceiveCourtCaseEventReply"]["ResponseMetadata"]

        if "BackendSystemReturn" not in metadata:
            raise JNETError(
                "Not sure what happens here? It is not an expected structure and not a failure",
                data = data,
                soap_response = result,
            )

        if metadata["BackendSystemReturn"]["BackendSystemReturnCode"] == "FAILURE":
            # -- these errors happen if the file_id exists, but the Docket Number tha was requested
            #    does not.
            if "DOCKET NOT FOUND" in metadata["BackendSystemReturn"]["BackendSystemReturnText"]:
                if check:
                    raise NotFound(
                        data['ReceiveCourtCaseEventReply']['AOPCFault']['Reason'],
                        data = data,
                        soap_response = result
                        )
                return(return_value)
            elif "OTN NOT FOUND" in metadata["BackendSystemReturn"]["BackendSystemReturnText"]:
                if check:
                    raise NotFound(
                        data['ReceiveCourtCaseEventReply']['AOPCFault']['Reason'],
                        data = data,
                        soap_response = result,
                    )
                return(return_value)
            elif "Invalid Request Object! Docket Number not supported!" in metadata["BackendSystemReturn"]["BackendSystemReturnText"]:
                if check:
                    raise InvalidRequest(
                        data['ReceiveCourtCaseEventReply']['AOPCFault']['Reason'],
                        data = data,
                        soap_response = result,
                    )
                return(return_value)
            elif check:
                # some failure/error that we do not know
                raise JNETError(
                    f"Unknown FAILURE in attempt to retrieve file id {file_id}: {metadata['BackendSystemReturn']['BackendSystemReturnText']}",
                    data = data,
                    soap_response = result,
                )
            # FAILURE - final return
            return(return_value)

        elif metadata["BackendSystemReturn"]["BackendSystemReturnCode"] != "SUCCESS":
            #-- handle unknown non-success statuses
            if check:
                raise JNETError(
                    f"Do not know haow to interpret a BackendSystemReturnCode of '{metadata['BackendSystemReturn']['BackendSystemReturnCode']}'",
                    data = data,
                    soap_response = result,
                )
            # NON-SUCCESS final case
            return(return_value)

        if check and "Queued DOCKET NUMBER " in metadata["BackendSystemReturn"]["BackendSystemReturnText"] and not allow_queued:
            #-- this is "successful" but incomplete - so we throw this error if check is true!
            docket = re.search(r'Queued DOCKET NUMBER (\S+)', metadata["BackendSystemReturn"]["BackendSystemReturnText"])
            tracking = re.search(r'Queued DOCKET NUMBER (\S+)', metadata["BackendSystemReturn"]["BackendSystemReturnText"])
            raise QueuedError(f"Docket {docket.group(1)} - Tracking ID {metadata['UserDefinedTrackingID']}: this request is queued and accurate data would not be provided if retrieved at this time.", data = data)

        # success and everything is just as expected! return the result
        return(return_value)


    def retrieve_requests(self, tracking_id = None, *, docket_number = None, pending_only = True, raw = False, check = False, ignore_queued = True, ignore_not_found = False, include_metadata = False):
        """ Fetch all requests that are currently available.

        Because of the constraints of the upstream SOAP system, the combination of ignore/check param can be confusing and differ based on what you want to do. Remember if a file is fetched, is will be removed from the pending queue and no longer show up in `check_request_status` by default.

        Therefore, note the following:
            - If there are files for a Queued request and also the complementary completed request, the queued results will be fetched (to remove them from pending) but not returned, so as not to duplicate record data. Only the Completed Request will be returned.
            - With the default parameters, unfulfilled queued requests will *not* be returned, not-found and no-results requests *will* be returned, and exceptions will not be thrown.
            - Add `ignore_queued = False` if you want to retrieve the data for unfulfilled queued requests. This data is generally accurate but missing Charging and Financial data.
            - Add `ignore_not_found = True` if you don't want to retrieve files that have no case information. This is an easy way to guarantee you are only getting full records with actual case data.
            - If you add `check = True`, errors will be thrown if (a) no results are found, (b) any files are Not Found (if `ignore_not_found` is False) or (c) any files are Queued and unfulfilled (if `ignore_queued` is False)

        Args:
            tracking_id: If provided, only fetch requests with the given user defined tracking id.
            docket_number: If provided, fetches all requests for the given docket number.
            pending_only: If True, only considers pending requests. Default is True.
            raw: If True, returns an array of SOAPResponse objects rather than the data directly. Default is False.
            check: If True, check each retrieved call to ensure that something is fetched. Default is True.
            ignore_queued: If True, do not fetch records that queued and unfulfilled. If False, the records will be returned.
            ignore_not_found: If True, neither fetch nor throw an exception for not found records - just ignore them. Default is False.
            include_metadata: If True, includes the `ResponseMetadata` data envelope in the return value; otherwise returns only the `CourtCaseEvent` data. Default is False.
        Returns:
            If `raw` is `True`, returns an array of SOAPResponse objects for each file.
            If `include_metadata` is `True`, returns an array of the full data structure returned, including the `ResponseMetadata` that indicates information about the BackendRequest.
            Otherwise, returns an array of the `CourtCaseEvent` data. May be an empty array if no requests are pending.
        Raises:
            If `check` is True and there was a backend error retrieving one of the files, raises a JNETError.
        """
        to_fetch = self.check_requests(
            pending_only = pending_only,
            tracking_id = tracking_id,
            docket_number = docket_number,
            check = False
        )

        if len(to_fetch) == 0:
            if check:
                if docket_number:
                    raise NotFound(f"Could not find any available files for docket {docket_number}")
                elif tracking_id:
                    raise NotFound(f"Could not find any available files for tracking id {tracking_id}")
            return([])

        result = []
        queued_data = {}
        docket_data = {}
        not_found = []
        files_to_return = []
        extra_fetches = []

        # pre-screen the requests to fetch and throw errors if there are any problems
        for request_info in to_fetch:
            if request_info['queued']:
                queued_data.setdefault(request_info['tracking_id'], [])
                queued_data[request_info['tracking_id']].append(request_info)
            elif not request_info['found']:
                not_found.append(request_info)
                if not ignore_not_found:
                    files_to_return.append(request_info)
            else:
                docket_data[request_info['tracking_id']] = True
                files_to_return.append(request_info)

        # throw errors!
        if check and not_found and not ignore_not_found:
            if len(not_found == 1):
                raise NotFound(f"Docket {not_found[0]['docket_number']} (tracking id {not_found[0]['tracking_id']} was not found (and is not retrieved)!", data = not_found)
            else:
                raise NotFound(f"Some requests were not found:  " '; '.join([f"Docket {req['docket_number']} - Tracking {req['tracking_id']}" for req in not_found]))

        if queued_data:
            # see if the queued data has
            error_data = []
            for tracking, queued in queued_data.items():
                if tracking in docket_data:
                    # queued requests were fulfilled! so fetch them but don't return them
                    extra_fetches.extend(queued)
                elif ignore_queued:
                    # just skip them, leave them pending as they are.
                    continue
                elif check:
                    # unfilled queued request exist, and check is requested - so get ready to
                    # throw an exception (though in case there are multiple, don't throw it yet)
                    error_data.extend(queued)
                else:
                    # unfilled queued requests exists, and we aren't suppoed to ignore, so
                    # return them!
                    files_to_return.extend(queued)

            if error_data:
                raise QueuedError(f"Incomplete queued data found!:  " '; '.join([f"Docket {req['docket_number']} - Tracking {req['tracking_id']}" for req in error_data]))

        for request_info in files_to_return:
            retrieved = self.retrieve_file_data(request_info['file_id'], check = False, raw = raw)
            if raw or include_metadata or 'CourtCaseEvent' not in retrieved['ReceiveCourtCaseEventReply']:
                result.append(retrieved)
            else:
                result.append(retrieved['ReceiveCourtCaseEventReply']['CourtCaseEvent'])

        # -- now handle "additional" requests, i.e. queued requests for which we fetched the completed data.
        # We do not add these to the return data because more complete data is provided, but we do this
        # to remove them from JNET's pending queue
        for request_info in extra_fetches:
            retrieved = self.retrieve_file_data(request_info['file_id'], check = False)

        return(result)

    @classmethod
    def clean_info_response_data(cls, request):
        """ Simplify the request status JSON to something more usable.

        Args:
            request: a data representation of a status request, or a list of the same. This can be found by (a) providing status_request_response.data, or (b)  manually providing 1 or more of the 'RequestCourtCaseEventInfoResponse' -> 'RequestCourtCaseEventInfoMetadata' elements.
        Returns:
            Usually, a list of objects; however, if the request is a single dict of a single record, it will return a single object. The data structure is defined as follows:
                queued: If the element is 'queued', i.e. not yet available for download.
                tracking_id: The user defined tracking id.
                file_id: The file tracking id
                found: Boolean to indicate if the element is listed as not found. This will be None if we cannot identify the header or if seems to be still be queued
                otn: the OTN, if it can be identified
                docket_number: The docket number, if it can be identified
                type: 'otn', 'docket', or None if neither appear to be accurate
                raw: The raw request provided
        """
        if type(request) is list:
            return([cls.clean_info_response_data(req) for req in request])

        if 'RequestCourtCaseEventInfoResponse' in request:
            # this is the raw data, so reprocess
            result = cls.clean_info_response_data(request['RequestCourtCaseEventInfoResponse']['RequestCourtCaseEventInfoMetadata'])
            if type(result) is not list:
                return([result])
            return(result)

        result = {
            'raw': request,
            'file_id': request['FileTrackingID'],
            'tracking_id': request['UserDefinedTrackingID'],
            'queued': None,
            'found': None,
            'type': None,
            'docket_number': None,
            'otn': None,
        }

        docket_re = re.compile(r'DOCKET NUMBER\s+(\S+)')
        docket_notfound_re = re.compile(r'DOCKET NOT FOUND:\s+(\S+?)\s*aopc')


        activity_header_found = False
        for header in request['HeaderField']:
            if header['HeaderName'] == 'ActivityTypeText':
                if activity_header_found:
                    raise Exception("Multiple activity headers?")
                activity_header_found = True
                result['queued'] = "Queued DOCKET NUMBER " in header['HeaderValueText']
                if 'OTN NOT FOUND' in header['HeaderValueText']:
                    result['found'] = False
                    raise Exception("Not sure how to process an OTN value")
                elif 'OTN' in header['HeaderValueText']:
                    raise Exception("Not sure how to process an OTN value")
                elif 'Invalid Request Object!' in header['HeaderValueText']:
                    match = re.search(
                        r'Invalid Request Object!\s+([^!]+!)(.*?)aopc:error',
                        header['HeaderValueText'],
                        re.I
                    )
                    if not match:
                        raise Exception(f"Received an Invalid Request Object error for {request['UserDefinedTrackingID']} but the error message is not in an expected format.")
                    msg = match.group(1)
                    result['docket_number'] = match.group(2)
                    result['found'] = False
                    result['type'] = 'docket_number'
                else:
                    match = docket_re.search(header['HeaderValueText'])
                    if match:
                        result['docket_number'] = match.group(1)
                        result['found'] = True
                        result['type'] = 'docket_number'
                        continue

                    match = docket_notfound_re.search(header['HeaderValueText'])
                    if match:
                        result['docket_number'] = match.group(1)
                        result['found'] = False
                        result['type'] = 'docket_number'
                        continue

                    raise Exception(f"Not sure what this operation is: {header['HeaderValueText']}!")

        return(result)
