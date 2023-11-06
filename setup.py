#!/usr/bin/env python3
"""Energytool"""

from setuptools import setup, find_packages

EXTRAS_REQUIRE = {
    "tests": [
        "pytest==7.3.1",
    ],
    "lint": [
        "pre-commit==3.3.2",
    ],
}

EXTRAS_REQUIRE["dev"] = EXTRAS_REQUIRE["tests"] + EXTRAS_REQUIRE["lint"]

# Get the long description from the README file
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="energytool",
    version="0.1",
    description="Tools for EnergyPlus",
    long_description=long_description,
    url="https://github.com/BuildingEnergySimulationTools/energytool",
    author="Nobatek/INEF4",
    author_email="bdurandestebe@nobatek.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.26.0",
        "pandas>=2.1.2",
        "eppy>=0.5.63",
        "corrai>=0.1.0",
    ],
    extras_require=EXTRAS_REQUIRE,
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
)
