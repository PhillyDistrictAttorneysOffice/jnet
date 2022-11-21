[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://opensource.org/licenses/GPL-3.0)

# daocore

This package provides a low-level interface to system, core, and non-analytic functions in the 
  Philadelphia District Attorney Office. It is expected to be a root package used by other DAO packages. 
  Many of the functions are to support multiple development environments, abstracting out testing contexts,
  and decoupling core paths from the current server it is being run on.

## Distribution

This is part of the [shared-system-library](https://github.com/PhillyDistrictAttorneysOffice/shared-system-library)

## Installation

    deployr --production .

or

    python3 -m pip install .

## Usage

Many examples of usage are available in the tests/ subdirectory. Documentation is also available in the [GitHub repository](https://github.com/PhillyDistrictAttorneysOffice/shared-system-library)

## Contributors

* [Kevin Crouse](mailto:kevin.crouse@phila.gov)

## License

This module was developed by and for the Information Technology unit in the Philadelphia District Attorney's Office. Any code, data, tools, or intellectual property follows open source, share-alike principles and is licensed under the GNU Public License (GPL) 3.0, except where required to be in the public domain by law. [A copy of the GPL](LICENSE) is in the root of this package.

[GPL 3.0](https://opensource.org/licenses/GPL-3.0)
