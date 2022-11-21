import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("VERSION", "r") as fh:
    version = fh.read().strip()

with open("requirements.txt", "r") as fh:
    requirements = fh.read().strip()

setuptools.setup(
    name='jnet',
    version=str(version),
    author="Kevin Crouse",
    author_email="kevin.crouse@phila.gov",
    description="Fully-functional request-reply client for JNET",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta"
    ],
    install_requires=requirements,    
    scripts=[],
 )
