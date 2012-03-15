# setup.py?

from setuptools import setup, find_packages
#from distutils.core import setup 

import os

# directory containing this file
here = os.path.dirname(os.path.abspath(__file__))

# all python packages
all_packages = [i for i in os.listdir(here)
                if os.path.exists(os.path.join(here, i, 'setup.py'))]


setup(name='Mozbase',
      version='1.0',
      description='lots of moz packages',
      author='Mozilla',
      author_email='me@mozilla',
      url='mozbase',
      dependency_links = [
         'mozprofile/', 
      ],     
      install_requires=all_packages,
)

