#!/usr/bin/env python3
"""Energytool"""

from setuptools import setup, find_packages

# Get the long description from the README file
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="energytool",
    version="0.1",
    description="Tools for EnergyPlus",
    long_description=long_description,
    # url="",
    author="Nobatek/INEF4",
    author_email="bdurandestebe@nobatek.com",
    # license="",
    # keywords=[
    # ],
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.7",
    install_requires=[
        "numpy>=1.22.3",
        "pandas>=1.4.2",
        "eppy>=0.5.57",
        "fastprogress>=1.0.2",
        "contextvars>=2.4",
        "plotly>=5.8.0",
        "SALib>=1.4.5",
    ],
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
)
