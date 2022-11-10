import sys,os
import traceback,pdb,warnings
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('file_id', nargs = '*', help = "The file_ids to fetch")
parser.add_argument('--test', '-t', action = 'store_true', help = "If provided, submit a loopback request to the beta server for testing, which sets a special tracking id and validates the result. Also randomly chooses a docket number if none are specified")
parser.add_argument('--beta',default = False, help = "If provided, hit the beta/development server instead of production jnet. Not necessary if you use `--test`")
parser.add_argument('--development', '--dev', '-d', default=True, action = 'store_true', help="Source the module in the python directory instead of using the installed package. Also turns on --debug")
parser.add_argument('--verbose', '-v', default=True, action = 'store_true', help="Prints out extra details about the request and response")
parser.add_argument('--debug', default=False, action = 'store_true', help="Run with postmortem debugger to investigate an error")
args = parser.parse_args()

if args.development:
    args.debug = True   
    sys.path.insert(0, 'python')

import jnet

if not args.file_id:
    if args.test:
        # set a default for testing
        args.file_id = ['636a7062aa467208b0b64477']        
    else:
        raise Exception("No docket number specified")

def runprogram():

    jnetclient = jnet.CCE(
        test = args.test, 
        endpoint = 'beta' if args.beta else None,               
        verbose = args.verbose,
    )

    for file_id in args.file_id:
        print(f"Making request for file_id {file_id}")

        # request docket
        resp = jnetclient.fetch_request(file_id)
    
        # print data
        print(f"--- Result for File {file_id} ---")
        print(resp.data)

        if args.development:    
            print("** Develoment Review:\n\tAccess `jnetclient` for the client, or `resp` for the response object")
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