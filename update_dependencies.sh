#!/bin/bash

pip-compile --upgrade requirements.in
pip install -r requirements.txt
