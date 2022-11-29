# jnet

Project to support programmatic interaction with the Pennsylvania Justice Network (JNET)

## Authorship

The code in this project was developed and is maintained by [DATA Lab](https://phillyda.org/data-lab/) in the Philadelphia District Attorney's Office (DAO). 

The project is not officially licensed, maintained, developed, or distributed by either the Pennsylvania Justice Network (JNET) or Administrative Office of Pennsylvania Courts (AOPC).

## Usage

### Installing the python package

See the README in the `jnet_package` subdirectory for details on the JNET python package. Installation of the JNET package generally can be done with the following command:

`python3 -m pip install jnet`

### Client Configuration

You must be an appropriate Criminal Justice agency and have an account with JNET and official authorization before you can connect programmatically. JNET will provide a PKCS8 (with a `.pfx` extension) client certificate which is used to sign all requests.

See documentation for `jnet.client` for details on all the configuration options. In general, you can set the config (a) manually when instantiating a client, (b) via a json file with settings, or (c) with default paths for where to place the client certificate and password, agency user id, and server certificates (to validate the authenticity of the JNET server).

### Commandline Scripts

The primary JNET requests also have command-line scripts located in the `bin/` subdirectory and each has several command line arguments.  Run `python3 bin/<script> --help` for all of the arguments.

For a starting workflow to test basic functionality, see the below progression of scripts. Note that if you are doing initial loopback testing your tracking ID must be "158354".

```bash

python3 bin/docket_request.py CP-51-CR-0000100-2021 --tracking-id this-tracking-test-1010101

python3 bin/cce_request_status.py --tracking-id this-tracking-test-1010101

# the file tracking id parameter will be custom to your specific request:
python3 bin/cce_request_status.py 638676cfaa467223944a817f
```

Also note that all scripts have an `--output` argument that will specify a filename to dump the resultant json to.

## Contributing

We welcome Pull Requests for package improvements and well as collaboration on meaningful criminal justice data tools.

## License

This module was developed by and for the Philadelphia District Attorney's Office to interact with the JNET portal. All code, data, tools, or intellectual property follows open source, share-alike principles and is licensed under the GNU Public License (GPL) 3.0, except where required to be in the public domain by law. [A copy of the GPL](LICENSE) is in the root of this package.

[GPL 3.0](https://opensource.org/licenses/GPL-3.0)

## Contact

For questions or comments, please write to the DATA Lab's Data Engineer, [Kevin Crouse](mailto:kevin.crouse@phila.gov). 