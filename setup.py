#!/usr/bin/env python3

"""Bolt OS packaging scripts and tools."""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name='build-box-utils',
    version='1.0.0',
    url='https://github.com/tobijk/build-box-utils',
    author='Tobias Koch',
    author_email='tobias.koch@gmail.com',
    license='MIT',
    packages=[
        'boltlinux.buildbox',
        'boltlinux.buildbox.misc',
    ],
    package_dir={'': 'lib'},
    data_files=[
        ('/usr/bin', ['bin/build-box', 'bin/build-box-do']),
    ],
    platforms=['Linux'],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3'
    ],

    keywords='boltOS cross-compile rootstrap',
    description='Build Box NG utilities for managing Bolt OS build roots',
    long_description='Build Box NG utilities for managing Bolt OS build roots',
)
