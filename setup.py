# Copyright (c) Cassiny.io OÜ.

import re
from setuptools import setup, find_packages
from pathlib import Path


with (Path(__file__).parent / 'cassinyspawner' / '__init__.py').open() as fp:
    try:
        version = re.findall(r"^__version__ = '([^']+)'\r?$",
                             fp.read(), re.M)[0]
    except IndexError:
        raise RuntimeError('Unable to determine version.')

with open('./requirements/base.txt') as test_reqs_txt:
    requirements = list(iter(test_reqs_txt))

long_description = open('README.rst').read()


setup(
    name='swarmspawner',
    version=version,
    long_description=long_description,
    description="""
                SwarmSpawner: A spawner for JupyterHub that uses Docker Swarm's services
                """,
    url='https://github.com/cassinyio/SwarmSpawner',
    # Author details
    author='Christian Barra',
    author_email='info@cassiny.io',
    license='BSD',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords=['Interactive', 'Interpreter', 'Shell', 'Web'],
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=requirements,
    extras_require={},
)
