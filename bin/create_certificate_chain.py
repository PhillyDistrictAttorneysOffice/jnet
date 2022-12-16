import sys,os
import pathlib
import traceback,pdb,warnings
from pprint import pprint
import certifi
import argparse

parser = argparse.ArgumentParser(description = "Creates a combined PEM certificate that includes the full Root -> Intermediate -> Endpoint certificate chain.  Pass in the path to the directory that includes the unzipped server certificates downloaded from JNET")
parser.add_argument('path', default="cert", nargs='?', help = "A path to the folder of JNET server certificates")
args = parser.parse_args()

path = pathlib.Path(args.path)
if not path.exists() or not path.is_dir():
    raise FileNotFoundError(f"There is no directory at {path}")

if not (path / 'Root.crt').exists():
    raise FileNotFoundError(f"Cannot find the Root certificate in {path}")

if not (path / 'Intermediate.crt').exists():
    raise FileNotFoundError(f"Cannot find the Intermediate certificate in {path}")

with open(path / "Root.crt") as fh:
    rootcert = fh.read().strip()

with open(path / "Intermediate.crt") as fh:
    intcert = fh.read().strip()

completed = False
for endpoint in ('ws.jnet.beta.pa.gov', 'ws.jnet.pa.gov'):
    if (path / (endpoint + '.crt')).exists():
        with open(path / (endpoint + '.crt')) as fh:
            servercert = fh.read().strip()
            with open(path / (endpoint + '.combined.crt'), 'w') as fh:
                fh.write(rootcert + "\n" + intcert + "\n" + servercert + "\n")
                completed = True
                print(f"Wrote combined certificate {path / (endpoint + '.combined.crt')}")

if not completed:
    raise FileNotFoundError(f"Did not find any endpoint files to create a combined server certificate chain")
