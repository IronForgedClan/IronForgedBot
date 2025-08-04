#!/bin/bash

/home/botuser/.local/bin/pip-compile --upgrade requirements.in
pip install -r requirements.txt
