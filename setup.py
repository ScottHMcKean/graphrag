"""
setup.py configuration script describing how to build and package this project.

This file is primarily used by the setuptools library and typically should not
be executed directly. See README.md for how to deploy, test, and run
the graphrag project.
"""

from setuptools import setup, find_packages

import datetime

setup(
    name="graphrag",
    # We use timestamp as Local version identifier (https://peps.python.org/pep-0440/#local-version-identifiers.)
    # to ensure that changes to wheel package are picked up when used on all-purpose clusters
    version="0.0.1" + "+" + datetime.datetime.utcnow().strftime("%Y%m%d.%H%M%S"),
    url="https://databricks.com",
    author="scott.mckean@databricks.com",
    description="wheel file based on graphrag/src",
    packages=find_packages(where="./src"),
    package_dir={"": "src"},
    entry_points={"console_scripts": ["graphrag=graphrag.main:main"]},
    install_requires=[
        # Dependencies in case the output wheel file is used as a library dependency.
        # For defining dependencies, when this package is used in Databricks, see:
        # https://docs.databricks.com/dev-tools/bundles/library-dependencies.html
        "setuptools",
        "requests>=2.25.0",
        "beautifulsoup4>=4.9.0",
    ],
)
