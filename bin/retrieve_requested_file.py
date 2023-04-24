import sys,os
import traceback,pdb,warnings
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('file_id', nargs = '*', help = "The file_ids to fetch")
parser.add_argument('--output', '-o', default=None, help="A path to a file to dump the results.")
parser.add_argument('--tracking-id', '--tracking', '-t', default=None, help="A tracking id to retrieve. By default, will retrieve all files with the tracking id, but it can be combined with --docket to narrow it down further")
parser.add_argument('--docket', '-d', default=None, help="A docketn umber to retrieve. By default, will retrieve all files with the docket number, but it can be combined with --tracking to narrow it down further")
parser.add_argument('--all', '-a', action = 'store_true', help = "If provided, retrieves all pending requests. Running `python retrieve_requested_file.py -all` will clear out the entire pending queue.")
parser.add_argument('--queued', '-q', action = 'store_true', help = "If provided, retrieves requests that are queued but not yet fulfilled.")
parser.add_argument('--ignore-missing', '-i', action = 'store_true', help = "If provided, don't fetch any requests that are not found.")
parser.add_argument('--review', '-r', default=False, action = 'store_true', help="Opens an interactive shell to review the results in python.")
parser.add_argument('--pretty', '-p', default=True, action = 'store_true', help="Write prett-formatted json to file.")
parser.add_argument('--beta', default = None, help = "If provided, hit the beta/development server instead of production jnet. Not necessarily if you have the endpoint configured in your settings file.")
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

if not args.file_id and not args.all and not args.docket and not args.tracking_id:
    raise Exception("No docket number specified")

def runprogram():

    jnetclient = jnet.CCE(
        endpoint = 'beta' if args.beta else None,
        verbose = args.verbose,
    )

    if args.all or args.tracking_id or args.docket:
        filedata = jnetclient.retrieve_requests(
            tracking_id = args.tracking_id,
            docket_number = args.docket,
            ignore_not_found = args.ignore_missing,
            ignore_queued = not args.queued,
        )
    else:
        filedata = []
        for file_id in args.file_id:
            print(f"Making request for file_id {file_id}")

            # request docket
            data = jnetclient.retrieve_file_data(file_id)
            filedata.append(data)


    # output
    if args.output:
        if args.output.endswith('.json'):
            with open(args.output, 'w') as fh:
                if len(filedata) == 1:
                    json.dump(filedata[0], fh)
                else:
                    json.dump(filedata, fh)
        elif args.output.endswith('.pckl') or args.output.endswith('.pickle'):
            import pickle
            with open(args.output, 'wb') as fh:
                pickle.dump(filedata, fh)
        elif os.path.isdir(args.output) or not os.path.exists(args.output):
            if not os.path.exists(args.output):
                os.makedirs(args.output)
            for docket in filedata:
                if 'ReceiveCourtCaseEventReply' in docket:
                    docket = docket['ReceiveCourtCaseEventReply']['CourtCaseEvent']
                print(f"\tWrote {docket['CaseDocketID']['ID']}")
                with open(args.output + "/" + docket['CaseDocketID']['ID'] + '.json', 'w') as fh:
                    if args.pretty:
                        json.dump(docket, fh, indent = 4)
                    else:
                        json.dump(docket, fh)
        else:
            with open(args.output, 'w') as fh:
                if len(filedata) == 1:
                    json.dump(filedata[0], fh)
                else:
                    json.dump(filedata, fh)

        print(f" Wrote {len(filedata)} retrieved files to {args.output}")
    else:
        # print data
        print(f"--- Results ---")
        print(json.dumps(filedata, indent=4))
        print(f"\nTotal Count: {len(filedata)}")

    if args.review or args.debug:
        print("** Develoment Review:\n\tAccess `jnetclient` for the client, or `filedata` for the response object")
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
