#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing dependencies..."
pip install --upgrade pip

# Use production requirements if available, otherwise fall back to requirements.txt
if [ -f "requirements_production.txt" ]; then
    echo "Using production requirements..."
    pip install --only-binary=:all: -r requirements_production.txt || pip install -r requirements_production.txt
else
    echo "Using standard requirements..."
    pip install --only-binary=:all: numpy pandas || pip install numpy pandas
    pip install -r requirements.txt
fi

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running migrations..."
python manage.py migrate --no-input

echo "Build completed successfully!"
