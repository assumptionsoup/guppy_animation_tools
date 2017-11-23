#! /usr/bin/env bash

# Make sure pytest is installed for maya first.
# Quick'n dirty way to install pytest in linux:
# Download get-pip.py, then run:
#
# cd /usr/autodesk/maya2018/bin/
# sudo ./mayapy /path/to/get-pip.py
# sudo ./mayapy -m pip install pytest

mayapy -m pytest
