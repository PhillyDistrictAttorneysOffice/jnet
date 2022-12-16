import sys,os
import pathlib
import traceback,pdb,warnings
from pprint import pprint
import certifi
import argparse

parser = argparse.ArgumentParser(description = "Install a server certificate into the python certifi certificate library. This may need to be done for all certificates - the Intermediate and Root certificates, as well as separate endpoint certificates for both the beta and production JNET endpoints")
parser.add_argument('path', help = "A path to the folder of JNET server certificates or the path to a single file to install")
args = parser.parse_args()

with open(certifi.where()) as fh:
    certs = fh.read()


files = []
path = pathlib.Path(args.path)
if path.is_dir():
    for file in path.iterdir():
        if file.name in ('Root.crt', 'Intermediate.crt', 'ws.jnet.beta.pa.gov.crt', 'ws.jnet.pa.gov.crt'):
            files.append(file)
else:
    if not path.exists():
        raise FileNotFoundError(f"No file exists at {args.path}")
    files = [path]

if not files:
    raise FileNotFoundError(f"{path} does not include any recognizable server certificate files")

newcerts = []
newfiles = []
for file in files:
    with open(file) as fh:
        cert = fh.read()

    if cert in certs:
        print(f"*Skipping* {file.name}: already in the certificate bundle")
    else:
        newfiles.append(file.name)
        newcerts.append(cert)

if not newfiles:
    raise FileExistsError("All certificates files are already in the certificate store - you should be good to go")

try:
    with open(certifi.where(), 'a') as fh:
        if cert[-1] != "\n":
            fh.write("\n")
        for cert in newcerts:
            fh.write(cert + "\n")
except PermissionError as perm:
    print(f"\n\nYou do not have permission to open the certifi certificate bundle. You can install a user-level module and bundle locally with `pip install --force certifi` or you can install the certificates globally with `sudo python {' '.join(sys.argv)}`")
    raise

print("Added the following certificates to the certifi certificate bundle:\n\t- " + "\n\t- ".join(newfiles))