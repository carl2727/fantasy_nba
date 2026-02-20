#!/usr/bin/env bash
# exit on error
set -o errexit

echo "===== Starting build process ====="
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

echo "===== Upgrading pip ====="
pip install --upgrade pip

echo "===== Installing core dependencies with binary wheels only ====="
# Install numpy and pandas first with binary wheels only (no compilation)
pip install --only-binary=:all: numpy==1.24.3 pandas==2.0.3

echo "===== Installing remaining dependencies ====="
pip install -r requirements.txt

echo "===== Collecting static files ====="
python manage.py collectstatic --no-input

echo "===== Running database migrations ====="
python manage.py migrate --no-input

echo "===== Build completed successfully! ====="
