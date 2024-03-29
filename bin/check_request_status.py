import sys,os
import traceback,pdb,warnings
from pprint import pprint
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('--output', '-o', default=None, help="A path to a file to dump the results.")
parser.add_argument('--all', action = 'store_true', help = "If provided, show all requests, not just the pending ones.  By default, `PendingOnly` is set to True, so this undoes that.")
parser.add_argument('--tracking-id', '-t', nargs = '*', default = None, help = "Specify a specific tracking id (multiple allowed)")
parser.add_argument('--docket', '-d', default = None, help = "Specify a specific docket number to search for")
parser.add_argument('--otn', default = None, help = "Specify a specific OTN to search for")
parser.add_argument('--review', '-r', default=False, action = 'store_true', help="Opens an interactive shell to review the results in python.")
parser.add_argument('-n', default = 100, type = int, help = "Specify a record limit (default 100)")
parser.add_argument('--beta',default = None, action = "store_true", help = "If provided, hit the beta/development server instead of production jnet. Not necessary if you use `--test`")
parser.add_argument('--verbose', '-v', default=False, action = 'store_true', help="Prints out extra details about the request and response")
parser.add_argument('--debug', default=False, action = 'store_true', help="Run with postmortem debugger to investigate an error")
parser.add_argument('--development', '--dev', default=None, action = 'store_true', help="Source the module in the python directory instead of using the installed package.")
parser.add_argument('--ignore-errors', '-e', default=False, action = 'store_true', help="If something is breaking and you still want the list of outstanding requests, use this to show the details.")
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

    if args.tracking_id:
        # request by tracking number
        requestdata = []
        for tracking_id in args.tracking_id:
            resp = jnetclient.check_requests(
                pending_only = not args.all,
                tracking_id = tracking_id,
            )

            # print response
            print(f"\n----Tracking ID {tracking_id}-----")
            print(json.dumps(resp, indent=4))
            requestdata.extend(resp)
    else:
        # request by docket; or everything
        requestdata = jnetclient.check_requests(
            pending_only = not args.all,
            record_limit = args.n,
            docket_number = args.docket,
            otn = args.otn,
            ignore_errors = args.ignore_errors,
        )

        # print response
        print(f"\n----Response Data-----")
        print(json.dumps(requestdata, indent = 4))

    print(f"\nTotal Count: {len(requestdata)} requests")
    if len(requestdata) == args.n:
        print("\t**Note: outstanding requests exceeds record_limit and so data does not represent all requests.\n\tYou can increase the limit by specifying `--n XXX` on the commandline.")
    if args.output:
        if len(requestdata) == 1:
            with open(args.output, 'w') as fh:
                json.dump(requestdata[0], fh)
        else:
            with open(args.output, 'w') as fh:
                json.dump(requestdata, fh)

    if args.review or args.debug:
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
