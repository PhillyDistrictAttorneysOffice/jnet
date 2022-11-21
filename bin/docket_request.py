import sys,os
import traceback,pdb,warnings
from pprint import pprint
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('docket_number', nargs = '*', help = "The docket number(s) to request")
parser.add_argument('--test', '-t', action = 'store_true', default=False, help = "If provided, submit a loopback request to the beta server for testing, which sets a special tracking id and validates the result. Also randomly chooses a docket number if none are specified")
parser.add_argument('--beta',default = False, action = 'store_true', help = "If provided, hit the beta/development server instead of production jnet. Not necessary if you use `--test`")
parser.add_argument('--review', '-r', default=False, action = 'store_true', help="Opens an interactive shell to review the results in python.")
parser.add_argument('--development', '--dev', '-d', default=True, action = 'store_true', help="Source the module in the python directory instead of using the installed package.")
parser.add_argument('--verbose', '-v', default=False, action = 'store_true', help="Prints out extra details about the request and response")
parser.add_argument('--debug', default=False, action = 'store_true', help="Run with postmortem debugger to investigate an error")
args = parser.parse_args()

if args.development:
    sys.path.insert(0, 'jnet-package')

import jnet

if not args.docket_number:
    if args.test:
        # set a default for testing
        args.docket_number = ['MC-51-CR-9000039-2021']
        # CP example - CP-51-CR-0000003-2021
    else:
        raise Exception("No docket number specified")

def runprogram():

    jnetclient = jnet.CCE(
        test = args.test, 
        endpoint = 'beta' if args.beta else None,               
        verbose = args.verbose,
    )

    for dn in args.docket_number:
        print(f"Making request for docket {dn}")

        # request docket
        resp = jnetclient.request_docket(
            dn,
        )
    
        # print response                
        print(f"\n----Response Data-----")
        print(resp.data_string)
        print(f"\nTracking ID: {resp.tracking_id}\n")

        if args.review or args.debug:    
            print("** Develoment Review Ready **\n\tAccess `jnetclient` for the client, or `resp` for the response object")
            pdb.set_trace()
            pass
        
        
if __name__ == '__main__':
    
    if not len(args.docket_number):
        args.docket_number = ['CP-51-CR-0000003-2021']

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