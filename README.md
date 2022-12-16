# jnet

Project to support programmatic interaction with the Pennsylvania Justice Network (JNET).

# Authorship

The code in this project was developed and is maintained by [DATA Lab](https://phillyda.org/data-lab/) in the Philadelphia District Attorney's Office (DAO) in order to provide generalized, programmatic access to the services offered by JNET.

The project is not officially licensed, maintained, developed, or distributed by either the Pennsylvania Justice Network (JNET) or Administrative Office of Pennsylvania Courts (AOPC).

# Usage

Usage requires installing the package and setting up the configuration details. JNET is **not** open access or open data, and so all clients require client-specific credentials that need to be available to the modules.

# Prerequisites

You must be an appropriate Criminal Justice agency and have an account with JNET and official authorization before you can connect programmatically. 

Then:
* JNET will provide a PKCS8 (with a `.pfx` extension) client certificate which is used to sign all requests.
* JNET will provide the client password to decrypt the client certificate.
* JNET will provide the Provider ID, which will be a single string.
* You are encouraged to download the server certificates to verify that you are connecting to legimitate JNET endpoints:
    - Here are the the [production server certificates](https://www.jnet.pa.gov/public/Web%20Services/WSCertInfoProduction.html) 
    - Here are the [beta server certificate](https://www.jnet.pa.gov/public/Web%20Services/WSCertInfoBETAWS.html)

# Installing the python package

See the [README.md](jnet-package/) in the `jnet_package` subdirectory for details on installing the JNET python package. 

If configuration parameters are defined in multiple places, the `jnet` package will first use a parameter in the script code, then a parameter defined in the a `json` configuration file, and finally something found in the certificate search path (when applicable). 

# Client Configuration

There are mutiple ways to provide configuration options:

**Option A**: If all of your scripts will be by a single use and from a single location, you can take advantage of the **search path** features for your certificates and a `settings.json` file, which reduces the parameters to remember when creating new client objects.

**Option B**: If you (or your team) is writing several scripts that will reside in different locations, it may make sense to have a central location for your certificates and configuration json file and specify the location of the shared configuration file in each script.

**Option C**: You can specify the configuration details as parameters to the jnet client in the code of each script - but *please* do **not** save any sensitive information in git or any other version control system that you may someday share.

## The Default Search Path

If no other parameters are provided, the `jnet` package will search for the client certificate, server certificates, and a `settings.json` file based on the runtime directory location. This is useful for testing and when all your jnet applications are executing from the same location. 

Here is what is searched:
1. **json configuration file**: If a file named `settings.json` exists in the `cfg/` directory, it is used; otherwise, if one exists in the runtime directory, it is used. 
1. **client certificate**: If a filename ending in `webservice.pfx` exists in the `cert/` subdirectory or any subdirectory underneath it, it will be used.
1. **server certificate**: If there is a filename matching `ws.jnet.beta.pa.gov.combined.crt` or `ws.jnet.pa.gov.combined.crt`, in the `cert/` subdirectory or any subdirectory underneath it, it will be used. Note that you **must** generate a combined file from the bundle of certificates provided by JNET for this to work. See the section on **Server Certificates** below to install these certificates.

## JSON Configuration Files

You can provide all configuration parameters in a json-formatted file. A value will be ignored if it does not exist or if it exists and is null. 
 
 Here is an example of creating a client with a custom json configuration file:

```python
jnetclient = jnet.CCE( config = "/usr/share/jnet/beta-settings.json" )

req = jnetclient.docket_request('CP-51-MY-DOCKET-2022')
```

An example template for a json-formatted configuration file is provided in this git repo under [`cfg/settings.json.template`](cfg/settings.json.template). You can copy that to a filename with the `.json` extension, edit it, and use it in your client configuration. If you copy it to `cfg/settings.json` relative to the runtime directory, it will be included in the search path and automatically identified. 

The available keys for the json-formatted configuration file are:
- `user-id`: the Provider Identifier, which is required for some requests and will be provided to you by JNET or AOPC.
- `client-certificate`: the path to your specific `.pfx` client certificate to sign all requests, provided by JNET.
- `client-password`: the password to decrypt the client-certificate. This is provided to you by JNET and required to make all requests.
- `server-certificate`: the path to the SSL server certificate to verify the identify of the server you are connecting to. This should be either the certificate for the jnet production or beta server.
- `endpoint`: The base URL to send requets to. This is `https://ws.jnet.beta.pa.gov/` or `https://ws.jnet.pa.gov/` or the shorthand versions `beta` and `jnet`, respectively. If the `server-certificate` does not match the `endpoint`, your requests will fail.

### Managing configuration in code

The jnet client object can receive all configuration parameters directly. The following example shows the specification of all parameters. the jnet package will use the search path to fill in all the values that are not provided

```python
jnetclient = jnet.CCE(
    client_certificate = '/usr/share/jnet/my_client_certificate.pfx',
    client_password = 'secure_password',
    user_id = 'our_organization',
    endpoint = 'beta',
    server_certificate = '/usr/share/jnet/beta-certificates/',
)

req = jnetclient.docket_request('CP-51-MY-DOCKET-2022')
```

Parameters specified in code take precedence over both the json configuration file and values 
found in the search path. Here is an example of using a general config file but routing to the beta endpoint instead:

```python
jnetclient = jnet.CCE(
    config = '/usr/share/jnet/production-settings.json',
    endpoint = 'beta',
    server_certificate = '/usr/share/jnet/beta-certificates/',
)

req = jnetclient.docket_request('CP-51-MY-DOCKET-2022')
```

# Certificates

Proper, secure use of JNET requires the use of a client certificate to sign the request and the verification of the server certificate to ensure you are contacting the real JNET endpoint.

## Client Certificate

Your client certificate should be named something like `{MyOrganization}_webservice.pfx`. If you are planning for the certificate to be identified automatically by the search path, the important part is that it ends in `webservice.pfx` and you will need to rename it with that suffix if it is named differently. 

If it does not make sense to put your client certificate in the `cert/` subdirectory, you should set the path to the certificate in the json configuration file or set it on the jnet client object in your script.

## Server Certificates

Using the server certificates is important to avoid possible man-in-the-middle attacks, but also can be complicated in the python environment because python's request package requires the full certificate chain to verify the endpoint, but it does not provide flexible options to incorporate these certificates as the separate files provided by JNET. 

Furthermore, server certificates are not strictly required for functionality. If you are frustated and think it may be a server certificate issue, you can pass `server_certificate = False` into the client to disable host verification, but you should not do this in a production context.

To set up functional server certificates for the jnet package, you have 2 options:

### Option 1: Create a combined certificate

If you want to take advantage of the **search path** to identify the server certificates, you can unzip the server certificate bundle in the `cert/` subdirectory and create a combined certificate chain file. 

To do this:
1. Unzip the server certificate bundle(s) for the beta and/or production jnet endpoints into the `cert/` subdirectory (or any other directory of your choosing).
1. Run `python bin/create_certificate_chain.py path/to/certs` 
1. This will create a single file with the root, intermediate, and endpoint certificates in the same directory.
    * If this was the `cert/` directory (or a subdirectory thereof), you're done! The jnet package will find it automatically because that is the *search path*. 
    * Otherwise, you will need to specify the path to the new combined file as the `server-certificate` in your json configuration file or provide the path as the `server_certificate` parmaeter to the jnet client.

### Option 2: Install the certificates in the python certifi bundle

The jnet package ultimately will trust any servers whose certificates are in the `certifi` certificate bundle, and so you can install the certificates globally. This will make it so that none of your scripts that use the jnet package will have to manually configure the server certificates.

To do this:
1. Unzip the server certificate bundle(s) for the beta and/or production jnet endpoints.
1. Run `python bin/install_certificate.py path/to/certs`
1. If the prior command fails with a permission issue, you may need to run the command with `sudo` or as an administrator.
1. The jnet package should now verify the endpoints with the installed server certificates whenever they are run. You do not need to set the `server_certificate` values anywhere.

# Commandline Scripts

The primary JNET requests also have command-line scripts located in the `bin/` subdirectory and each has several command line arguments.  Run `python bin/<script> --help` for all of the arguments.

These scripts may not be robust for different configuration options. You may need to modify them to work correctly if you have a config that cannot be easily inferred.

# Tutorial - Getting Started

This is a minimal tutorial to get yourself started from scratch. You should read everything above and think about the best setup for your needs before you start using JNET in production.

Procedure:

1. Put your client certificates in the `cert/` subdirectory. 
1. Set up the server certificates by either installing the certificates globally or creating the combined certificate. See the options in the section on **Server Certificates** above.
1. Copy `cfg/settings.json.template` to `cfg/settings.json`, edit the file, and fill in the required organization-specific values for `client_password` and `user-id`.
1. Install the jnet package by running `pip install jnet_package`

Then, you should be able to run the following:

```sh
# Request the docket
# Note: if you are doing loopback testing, your tracking ID below must be "158354".
python bin/make_docket_request.py CP-51-CR-0000100-2021 --tracking-id this-tracking-test-1010101

# Check the docket status - if nothing comes up, wait a minute and try again
python bin/check_request_status.py --tracking-id this-tracking-test-1010101

# Retrieve the full json file
# Note: the file tracking id parameter will be custom to your specific request:
python bin/retrieve_requested_file.py --tracking-id this-tracking-test-1010101
```

Also note that all scripts have an `--output` argument that will specify a filename to dump the resultant json to, i.e.: `python bin/retrieve_requested_file.py --tracking-id this-tracking-test-1010101 --output first-docket.json`

# Contributing

We welcome Pull Requests for package improvements as well as collaboration on meaningful criminal justice data tools.

# License

This module was developed by and for the Philadelphia District Attorney's Office to interact with the JNET portal. All code, data, tools, or intellectual property follows open source, share-alike principles and is licensed under the GNU Public License (GPL) 3.0, except where required to be in the public domain by law. [A copy of the GPL](LICENSE) is in the root of this package.

[GPL 3.0](https://opensource.org/licenses/GPL-3.0)

# Contact

For questions or comments, please write to the DATA Lab's Data Engineer, [Kevin Crouse](mailto:kevin.crouse@phila.gov). 