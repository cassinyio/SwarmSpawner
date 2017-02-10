"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Copyright (c) Cassiny.io OÜ.

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path
import sys

v = sys.version_info
if v[:2] < (3,3):
    error = "SwarmSpawner requires Python version 3.3 or above."
    print(error, file=sys.stderr)
    sys.exit(1)

here = path.abspath(path.dirname(__file__))


setup(
    name = 'swarmspawner',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version = '0.1',

    description="SwarmSpawner: A spawner for JupyterHub that uses Docker Swarm's services",

    # The project's main homepage.
    url='https://github.com/cassinyio/SwarmSpawner',

    # Author details
    author='Cassiny.io OÜ',
    author_email='info@cassiny.io',

    # Choose your license
    license='BSD',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: BSD License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    # What does your project relate to?
    keywords = ['Interactive', 'Interpreter', 'Shell', 'Web'],

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['jupyterhub', 'docker'],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={},
)
