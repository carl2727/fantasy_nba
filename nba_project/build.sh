#!/usr/bin/env bash
# exit on error
set -o errexit

echo "===== Starting build process ====="
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

echo "===== Upgrading pip ====="
pip install --upgrade pip setuptools wheel

echo "===== Installing dependencies ====="
# Install all dependencies - binary wheels will be used automatically when available
pip install -r requirements.txt

echo "===== Collecting static files ====="
python manage.py collectstatic --no-input

echo "===== Running database migrations ====="
python manage.py migrate --no-input

echo "===== Build completed successfully! ====="
