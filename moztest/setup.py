# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


import os
from setuptools import setup, find_packages

PACKAGE_VERSION = '0.1'

# get documentation from the README
try:
    here = os.path.dirname(os.path.abspath(__file__))
    description = file(os.path.join(here, 'README.md')).read()
except (OSError, IOError):
    description = ''

# dependencies
deps = ['mozinfo']
try:
    import json
except ImportError:
    deps.append('simplejson')

setup(name='moztest',
      version=PACKAGE_VERSION,
      description="Package for storing and outputting Mozilla test results",
      long_description=description,
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='mozilla',
      author='Mihnea Dobrescu-Balaur',
      author_email='mbalaur@mozilla.com',
      url='https://wiki.mozilla.org/Auto-tools',
      license='MPL',
      packages=find_packages(exclude=['legacy']),
      include_package_data=True,
      zip_safe=False,
      install_requires=deps,
      )
