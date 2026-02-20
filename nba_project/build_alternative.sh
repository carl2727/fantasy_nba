# Alternative build script if binary-only installation fails
# Use this by renaming to build.sh if the current build.sh doesn't work

#!/usr/bin/env bash
set -o errexit

echo "===== Alternative Build Process ====="
echo "Python: $(python --version)"

# Upgrade pip and install wheel
pip install --upgrade pip wheel setuptools

# Install packages individually with fallback
echo "Installing Django..."
pip install Django==5.0.4

echo "Installing gunicorn..."
pip install gunicorn==21.2.0

echo "Installing database packages..."
pip install psycopg2-binary==2.9.9 dj-database-url==2.1.0

echo "Installing whitenoise..."
pip install whitenoise==6.6.0

echo "Installing numpy (binary only)..."
pip install --only-binary=numpy numpy==1.24.3 || pip install numpy

echo "Installing pandas (binary only)..."  
pip install --only-binary=pandas pandas==2.0.3 || pip install pandas

echo "Installing remaining packages..."
pip install nba_api==1.4.1 requests beautifulsoup4 lxml python-dotenv

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running migrations..."
python manage.py migrate --no-input

echo "Build complete!"
