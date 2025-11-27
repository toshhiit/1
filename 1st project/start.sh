#!/bin/bash
echo "Starting backend on Railway..."
gunicorn server:app --bind 0.0.0.0:$PORT --workers 4
