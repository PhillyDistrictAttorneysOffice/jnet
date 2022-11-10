import sys,os
import traceback,pdb,warnings
from pprint import pprint
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--pending-only', '--pending', '-p', action = 'store_true', help = "Only show pending requests")
parser.add_argument('-n', default = 100, type = int, help = "Specify a record limit (default 100)")
parser.add_argument('--tracking-id', '-t', nargs = '*', default = None, help = "Specify a specific tracking id (multiple allowed)")
parser.add_argument('--test', action = 'store_true', help = "If provided, submit a loopback request to the beta server for testing, which sets a special tracking id and validates the result. Also randomly chooses a docket number if none are specified")
parser.add_argument('--beta',default = False, help = "If provided, hit the beta/development server instead of production jnet. Not necessary if you use `--test`")
parser.add_argument('--development', '--dev', '-d', default=True, action = 'store_true', help="Source the module in the python directory instead of using the installed package. Also turns on --debug")
parser.add_argument('--verbose', '-v', default=True, action = 'store_true', help="Prints out extra details about the request and response")
parser.add_argument('--debug', default=False, action = 'store_true', help="Run with postmortem debugger to investigate an error")
args = parser.parse_args()

if args.development:
    args.debug = True   
    sys.path.insert(0, 'python')

import jnet

def runprogram():

    jnetclient = jnet.CCE(
        test = args.test, 
        endpoint = 'beta' if args.beta else None,               
        verbose = args.verbose,
    )

    if args.tracking_id:
        
        # request docket
        for tracking_id in args.tracking_id:
            resp = jnetclient.check_request(
                tracking_id = tracking_id
            )

            # print response                
            print(f"\n----Tracking ID {tracking_id}-----")
            pprint(resp.data)
    
    else:
        # request docket
        resp = jnetclient.check_request(
            pending_only = args.pending_only,
            record_limit = args.n,
        )

        # print response                
        print(f"\n----Response Data-----")
        pprint(resp.data)
        print("\nTracking ID: {resp.tracking_id}\n")

    if args.development:    
        print("** Develoment Review Ready **\n\tAccess `jnetclient` for the client, or `resp` for the response object")
        pdb.set_trace()
        pass
    
        
if __name__ == '__main__':

    if not args.debug:
            runprogram()
    else:
        try:
            runprogram()
        except Exception as e:
            errtype, value, tb = sys.exc_info()
            #tb = tb.tb_next # Skip *this* frame
            sys.last_type, sys.last_value, sys.last_traceback = errtype, value, tb
            print("\n*** Error caught, preparing for post-mortem debugging ***\n------------" )
            traceback.print_exception(errtype, value, tb)
            print("\n------------\n")
            pdb.post_mortem(tb)
            raise