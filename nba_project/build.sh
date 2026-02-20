#!/usr/bin/env bash
# exit on error
set -o errexit

echo "===== Starting build process ====="
echo "Python version: $(python --version)"

echo "===== Upgrading pip ====="
pip install --upgrade pip

echo "===== Installing dependencies ====="
pip install -r requirements.txt

echo "===== Collecting static files ====="
python manage.py collectstatic --no-input

echo "===== Running database migrations ====="
python manage.py migrate --no-input

echo "===== Build completed successfully! ====="
