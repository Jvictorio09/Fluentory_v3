#!/bin/bash
# Startup script for Django deployment
# This ensures migrations and static files are collected before starting the server

set -e  # Exit on error

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:${PORT:-8000} myProject.wsgi:application

