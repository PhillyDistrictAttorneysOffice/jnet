[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://opensource.org/licenses/GPL-3.0)

# jnet

This package provides clients to interact with the Pennsylvania Justice Network (JNET) SOAP-XML services.

## Installation

    python3 -m pip install jnet-package

## Usage

Many examples of function-based usage are available in tests in the `t/` subdirectory. 

## Testing

Several tests are provided. They will only work if you have set up your credentials correctly, and different tests are designed to be used in different JNET contexts. Because this package was developed in different stages of access, we cannot guarantee that that the loopback tests continue to work.

To run the test against the beta server, run this from the root directory of your git checkout.

```python
PYTHONPATH=jnet-package pytest jnet-package/t/test_cce_docket.py
```

To better debug errors in the test against the beta server, run this from the root directory of your git checkout:

```python
PYTHONPATH=jnet-package pytest jnet-package/t/test_cce_docket.py --pdb -vv -s
```


## Contributing

We welcome Pull Requests for package improvements and well as collaboration on meaningful criminal justice data tools.

## Attribution

The code in this project was developed and is maintained by [DATA Lab](https://phillyda.org/data-lab/) in the Philadelphia District Attorney's Office (DAO). 

The project is not officially licensed, maintained, developed, or distributed by either the Pennsylvania Justice Network (JNET) or Administrative Office of Pennsylvania Courts (AOPC).

## Contributors 

* [Kevin Crouse](mailto:kevin.crouse@phila.gov)

## License

This module was developed by and for the Philadelphia District Attorney's Office to interact with the JNET portal. All code, data, tools, or intellectual property follows open source, share-alike principles and is licensed under the GNU Public License (GPL) 3.0, except where required to be in the public domain by law. [A copy of the GPL](LICENSE) is in the root of this package.

[GPL 3.0](https://opensource.org/licenses/GPL-3.0)
