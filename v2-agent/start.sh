#!/bin/bash
# Start script for App Runner

# Debug: Show Python and pip info
echo "Python version:"
python3 --version
echo "Python path:"
which python3
echo "Pip packages:"
python3 -m pip list | grep uvicorn

# Add common Python bin directories to PATH
export PATH="/usr/local/bin:$PATH"
export PATH="/opt/python/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="/opt/python:$PYTHONPATH"

# Start uvicorn using python module
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
