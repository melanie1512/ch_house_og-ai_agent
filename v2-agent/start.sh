#!/bin/bash
# Start script for App Runner

echo "Installing dependencies..."
python3 -m pip install --quiet --no-cache-dir -r requirements.txt

echo "Starting application..."
# Start uvicorn using python module
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
