import sys,os
import traceback,pdb,warnings
from pprint import pprint
import json
import argparse
import datetime

parser = argparse.ArgumentParser()
parser.add_argument('docket_number', nargs = '*', help = "The docket number(s) to request")
parser.add_argument('--tracking-id', '-t', default = None, help = "The user defined tracking id")
parser.add_argument('--output', '-o', default=None, help="A path to a file to dump the results.")
parser.add_argument('--beta',default = None, action = 'store_true', help = "If provided, hit the beta/development server instead of production jnet. Not necessary if you use `--test`")
parser.add_argument('--review', '-r', default=True, action = 'store_true', help="Opens an interactive shell to review the results in python.")
parser.add_argument('--verbose', '-v', default=False, action = 'store_true', help="Prints out extra details about the request and response")
parser.add_argument('--debug', default=True, action = 'store_true', help="Run with postmortem debugger to investigate an error")
parser.add_argument('--development', '--dev', default=True, action = 'store_true', help="Source the module in the python directory instead of using the installed package.")
args = parser.parse_args()

if args.development:
    sys.path.insert(0, 'jnet-package')
elif args.development is None:
    try:
        import jnet
    except ModuleNotFoundError:
        sys.path.insert(0, 'jnet-package')

import jnet

def runprogram():

    jnetclient = jnet.CCE(
        endpoint = 'beta' if args.beta else None,
        verbose = args.verbose,
    )

    requestdata = []
    print(f"Making request for person")

    # request docket
    resp = jnetclient.request_participant(
        first_name = 'Joel',
        last_name = 'Polk',
        birthdate = datetime.date(1971, 5, 23),
        tracking_id = args.tracking_id,
    )

    pdb.set_trace()
    # print response
    print(f"\n----Response Data-----")
    print(resp.data_string)
    print(f"\nTracking ID: {resp.tracking_id}\n")

    requestdata.append(resp.data)

    if args.review or args.debug:
        print("** Develoment Review Ready **\n\tAccess `jnetclient` for the client, or `resp` for the response object")
        pdb.set_trace()
        pass

    if args.output:
        with open(args.output, 'w') as fh:
            if len(requestdata) == 1:
                json.dump(requestdata[0], fh)
            else:
                json.dump(requestdata, fh)


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
