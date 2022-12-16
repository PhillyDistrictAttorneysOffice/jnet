# jnet

Project to support programmatic interaction with the Pennsylvania Justice Network (JNET).

# Authorship

The code in this project was developed and is maintained by [DATA Lab](https://phillyda.org/data-lab/) in the Philadelphia District Attorney's Office (DAO) in order to provide generalized, programmatic access to the services offered by JNET.

The project is not officially licensed, maintained, developed, or distributed by either the Pennsylvania Justice Network (JNET) or Administrative Office of Pennsylvania Courts (AOPC).

# Usage

Usage requires installing the package and setting up the configuration details. JNET is **not** open access or open data, and so all clients require client-specific credentials that need to be available to the modules.

## Prerequisites

You must be an appropriate Criminal Justice agency and have an account with JNET and official authorization before you can connect programmatically. 

Then:
* JNET will provide a PKCS8 (with a `.pfx` extension) client certificate which is used to sign all requests.
* JNET will provide the client password to decrypt the client certificate.
* JNET will provide the Provider ID, which will be a single string
* You are encouraged to download the server certificates to verify that you are connecting to legimitate JNET endpoints:
    - here are the the [production server certificates](https://www.jnet.pa.gov/public/Web%20Services/WSCertInfoProduction.html) 
    - here are the [beta server certificate](https://www.jnet.pa.gov/public/Web%20Services/WSCertInfoBETAWS.html)

## Installing the python package

See the [README.md](jnet-package/README.md) in the `jnet_package` subdirectory for details on installing the JNET python package in particular. 

If configuration parameters are defined in multiple places, the `jnet` package will first use a parameter in the script code, then a parameter defined in the a `json` config file, and finally something found in the search path (if applicable). 

## Client Configuration

There are mutiple ways to provide configuration options - it can be done in code or via a json file. 

In most other cases, you will want to use a settings json file for at least some of the configuration options. If all of your scripts will be executed by one user, the certificates can be identified automatically from that location, as detailed bellow.

If you are writing several random scripts that will reside in different locations, it may make sense to have a central location for your certificates and specify the details in the code of each script - but *please* do **not** save any sensitive information in git or any other version control system that you may someday share.

### Client Certificate

The `cert/` subdirectory, relataive to the runtime directory, will be searched (along with all subdirectories) for the client certificate.  

In order to do this:
1. Identify the runtime directory where your script will run from. Put the client certificate in the `cert/` subdirectory of that location.
1. Your client certificate should be named something like `{MyOrganization}_webservice.pfx` - the important part is that it ends in `webservice.pfx`. If it is not, rename it with that suffix.

If it does not make sense to put your client certificate in the `cert/` subdirectory (because, for instance, it is in a shared global location), you should set the path to the certificate in the json configuration file or set it on the jnet client object.

### Server Certificates

Using the server certificates is important to avoid possible man-in-the-middle attacks, but it is not strictlly required for functionality. If you are frustated and think it may be a server certificate issue, you can pass `server_certificate = False` into the client to disable host verification, but you should not do this in a production context.

Python's request requires the full certificate chain to verify the endpoint, but it does not provide flexible options to incorporate these certificates. Therefore, for the jnet package, you have 2 options:

#### Option 1: Create a combined certificate

If all JNET scripts will be running from the same runtime directory, you can unzip the server certificate bundle in the `cert/` subdirectory (or any other subdirectory of your choosing). 

To do this:
1. Unzip the server certificate bundle(s) for the beta and/or production jnet endpoints. 
1. Run `python bin/create_certificate_chain.py path/to/certs` (the path is not needed if it is in the `cert/` subdirectory)
1. This will create a single file with the root, intermediate, and endpoint certificates in the same directory.
    * If this was the `cert/` directory (or a subdirectory thereof), you're done! The jnet package will find it automatically. 
    * Otherwise, you will need to specify the path to the new combined file as the `server-certificate` in your json configuration file or provide the path as the `server_certificate` parmaeter to the jnet client.

#### Option 2: Install the certificates in the python certifi bundle

The jnet package ultimately will trust any servers whose certificaets are in the certifi bundle, and so you can install the certificates globally. This will make it so that none of your scripts that use the jnet package will have to manually configure the server certificates.

To do this:
1. Unzip the server certificate bundle(s) for the beta and/or production jnet endpoints.
1. Run `python bin/install_certificate.py path/to/certs`
1. If the prior command fails with a permission issue, you may need to run it with `sudo` or as an administrator.
1. The jnet package should not verify the endpoints with the installed server certificates whenever they are run. You do not need to set the `server_certificate` values.

### Managing Configuration in a settings.json file

You can provide all configuration parameters in a json-formatted file. A value will be ignored if it does not exist or if it exists and is null. You can also provide the configuration parameters to the jnet client object as a hash/dictionary, which may be useful in testing.
 
By default, the `jnet` packages will look for a `settings.json` file in the `cfg/` subfolder of the runtime directory and the runtime directory, in that order. Configuration files may be kept in other locations or with other names and provided for the constructor of the jnet client object. As an example, this specifies a shared path for a settings file:

```python3
jnetclient = jnet.CCE( config = "/usr/share/jnet/beta-settings.json" )

req = jnetclient.docket_request('CP-51-MY-DOCKET-2022')
```

An example template for a json-formmated configuration file is provided in this git repo under [`cfg/settings.json.template`](cfg/settings.json.template). You can copy that to `cfg/settings.json` and set any or all parameters that you wish. 

The available keys for the json-formatted configuration file are:
- `user-id`: the Provider Identifier, which is required for some requests and will be provided to you by JNET or AOPC.
- `client-certificate`: the path to your specific `.pfx` client certificate to sign all requests, provided by JNET.
- `client-password`: the password to decrypt the client-certificate. This is provided to you by JNET and required to make all requests.
- `server-certificate`: the path to the SSL server certificate to verify the identify of the server you are connecting to. This should be either the certificate for the jnet production or beta server.
- `endpoint`: The base URL to send requets to. This is either `https://ws.jnet.beta.pa.gov/` or `https://ws.jnet.pa.gov/` and must correspond to the `server-certificate`. This commonly is also handled in code so that you can easily switch between production and test endpoints.

### Managing configuration in code

The jnet client object can receive the configuration parameters directly. For example, the following python code block specifies the user_id, client_password, and client_certificate, which are all required to make any request:

```python3
jnetclient = jnet.CCE(
    client_certificate = '/usr/share/jnet/my_client_certificate.pfx',
    client_password = 'secure_password',
    user_id = 'our_organization',
)

req = jnetclient.docket_request('CP-51-MY-DOCKET-2022')
```

## Commandline Scripts

The primary JNET requests also have command-line scripts located in the `bin/` subdirectory and each has several command line arguments.  Run `python3 bin/<script> --help` for all of the arguments.

These scripts are not very robust for different configuration options and need to be modified to work correctly if you have configs that cannot be easily inferred.

# Tutorial - Getting Started

To test your ability to connect, you can follow this starter workflow. 

**First**, put your client certificates in the `cert/` subdirectory. 

**Then**, set up the server certificates by either installing the certificates globally or creating the combined certificate. See the options in the section on **Server Certificates** above.

**Then**, copy `cfg/settings.json.template` to `settings.json`, edit the file, and fill in the required organization-specific values for `client_password` and `user-id`.

Then, you should be able to run the following:

```sh
# Request the docket
# Note: if you are doing loopback testing, your tracking ID below must be "158354".
python3 bin/docket_request.py CP-51-CR-0000100-2021 --tracking-id this-tracking-test-1010101

# Check the docket status - if nothing comes up, wait a minute and try again
python3 bin/cce_request_status.py --tracking-id this-tracking-test-1010101

# Retrieve the full json file
# Note: the file tracking id parameter will be custom to your specific request:
python3 bin/retrieve_cce.py --tracking-id this-tracking-test-1010101
```

Also note that all scripts have an `--output` argument that will specify a filename to dump the resultant json to, i.e.: `python3 bin/retrieve_cce.py --tracking-id this-tracking-test-1010101 --output first-docket.json`

# Contributing

We welcome Pull Requests for package improvements and well as collaboration on meaningful criminal justice data tools.

# License

This module was developed by and for the Philadelphia District Attorney's Office to interact with the JNET portal. All code, data, tools, or intellectual property follows open source, share-alike principles and is licensed under the GNU Public License (GPL) 3.0, except where required to be in the public domain by law. [A copy of the GPL](LICENSE) is in the root of this package.

[GPL 3.0](https://opensource.org/licenses/GPL-3.0)

# Contact

For questions or comments, please write to the DATA Lab's Data Engineer, [Kevin Crouse](mailto:kevin.crouse@phila.gov). 