import sys,os
import traceback,pdb,warnings
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('docket_number', nargs = '+', help = "The docket number(s) to request")
parser.add_argument('--output', '-o', default=None, help="A path to a file or directory in which to dump the results. If multiple dockets are specified for a directory output, they will be named separately; if multiple dockets are specified for a single output file, they will all be dumped together.")
parser.add_argument('--timeout', '-t', default=None, help="Set an alternate timeout.")
parser.add_argument('--review', '-r', default=False, action = 'store_true', help="Opens an interactive shell to review the results in python.")
parser.add_argument('--beta', default = None, action = 'store_true', help = "If provided, hit the beta/development server instead of production jnet. Not necessarily if you have the endpoint configured in your settings file.")
parser.add_argument('--verbose', '-v', default=False, action = 'store_true', help="Prints out technical details about the request and response")
parser.add_argument('--debug', default=False, action = 'store_true', help="Run with postmortem debugger to investigate an error")
parser.add_argument('--development', '--dev', default=None, action = 'store_true', help="Source the module in the python directory instead of using the installed package.")
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

    output_type = None
    if not args.output:
        output_path = None
    elif args.output.endswith('.json'):
        output_path = args.output
        output_type = 'file'
    else:
        # assume directory
        output_type = 'dir'
        output_path = args.output
        if output_path[-1] == '/':
            output_path = output_path[:-1]
        if not os.path.exists(output_path):
            os.makedirs(output_path)

    docket_numbers = args.docket_number
    alldata = []
    for docket_number in docket_numbers:
        filedata = jnetclient.fetch_docket_data(docket_number, timeout = args.timeout)

        if output_type == 'dir':
            with open(f"{output_path}/{docket_number}.json", 'w') as fh:
                json.dump(filedata, fh)
                print(f"    *** Wrote {docket_number} to {output_path}/ ***")
        elif not output_type:
            print(f"--- {docket_number} Data ---")
            print(json.dumps(filedata, indent=4))

        alldata.extend(filedata)

    if output_type =='file':
        with open(output_path, 'w') as fh:
            if len(alldata) == 1:
                json.dump(alldata[0], fh)
            else:
                json.dump(alldata, fh)
            print(f"    *** Wrote {docket_numbers} to {output_path} ***")

    if args.review or args.debug:
        if len(alldata) == 1:
            print(f"** Develoment Review for docket {docket_number}:\n\tAccess `jnetclient` for the client\n\t`filedata` for the response object")
        else:
            print(f"** Develoment Review:\n\tDockets: {docket_numbers}\n\tAccess `jnetclient` for the client\n\t`filedata` for the last docket response object\n\t`alldata` for a list of all retrieved data")
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
