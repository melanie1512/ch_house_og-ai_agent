#!/bin/bash
# Start script for App Runner

# Add common Python bin directories to PATH
export PATH="/usr/local/bin:$PATH"
export PATH="/opt/python/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"

# Start uvicorn
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
