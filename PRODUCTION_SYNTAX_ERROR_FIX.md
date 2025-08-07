# Production Syntax Error Fix Guide

## Problem
Getting `SyntaxError: invalid syntax` when running `python manage.py migrate` in production, but it works fine locally.

## Quick Fix Commands

### 1. Check Python Version
```bash
python --version
python3 --version
```
**Required:** Python 3.8+ for Django 4.x

### 2. Clear Python Cache
```bash
# Remove all __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} +

# Remove all .pyc files
find . -name "*.pyc" -delete
```

### 3. Check File Encoding
```bash
# Run the fix script
python fix_production_migration.py
```

### 4. Alternative Migration Commands
```bash
# Check Django installation
python -c "import django; print(django.get_version())"

# Check project syntax
python manage.py check

# Try fake initial migration
python manage.py migrate --fake-initial

# Run migrations one by one
python manage.py migrate pms
python manage.py migrate iot
```

## Common Causes & Solutions

### 1. Python Version Mismatch
**Problem:** Production uses Python 2.7 or older Python 3.x
**Solution:**
```bash
# Install Python 3.8+
sudo apt update
sudo apt install python3.8 python3.8-pip

# Use specific Python version
python3.8 manage.py migrate
```

### 2. File Encoding Issues
**Problem:** Files have Windows line endings or wrong encoding
**Solution:**
```bash
# Convert line endings (Linux/Mac)
dos2unix manage.py
dos2unix hotel_pms/settings.py
dos2unix iot/models.py

# Or use the fix script
python fix_production_migration.py
```

### 3. Corrupted Files During Deployment
**Problem:** Files got corrupted during upload/deployment
**Solution:**
```bash
# Re-upload files with proper encoding
# Ensure FTP/deployment tool uses binary mode for .py files

# Or re-clone from git
git pull origin main
```

### 4. Missing Dependencies
**Problem:** Django or other packages not properly installed
**Solution:**
```bash
# Reinstall requirements
pip install -r requirements.txt

# Or install Django specifically
pip install Django==4.2.7
```

### 5. Virtual Environment Issues
**Problem:** Wrong virtual environment or no virtual environment
**Solution:**
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install requirements
pip install -r requirements.txt
```

## Step-by-Step Troubleshooting

### Step 1: Environment Check
```bash
# Check current directory
pwd
ls -la

# Check Python and Django
python --version
python -c "import django; print(django.get_version())"
```

### Step 2: File Integrity Check
```bash
# Check if manage.py is readable
cat manage.py | head -5

# Check file permissions
ls -la manage.py
chmod +x manage.py
```

### Step 3: Django Settings Check
```bash
# Test Django settings
python manage.py check

# Check if settings can be imported
python -c "from hotel_pms import settings; print('Settings OK')"
```

### Step 4: Migration-Specific Check
```bash
# Check migration files
python manage.py showmigrations

# Check for migration conflicts
python manage.py showmigrations --plan
```

### Step 5: Run Fix Script
```bash
# Run the comprehensive fix script
python fix_production_migration.py
```

## Emergency Rollback

If migrations continue to fail:

### Option 1: Reset Migrations
```bash
# Backup database first!
cp db.sqlite3 db.sqlite3.backup

# Remove migration files (keep __init__.py)
rm iot/migrations/0*.py
rm pms/migrations/0*.py

# Recreate migrations
python manage.py makemigrations
python manage.py migrate
```

### Option 2: Use Fake Migrations
```bash
# Mark migrations as applied without running them
python manage.py migrate --fake

# Then run specific migrations
python manage.py migrate iot 0007 --fake
python manage.py migrate pms --fake
```

## Production Environment Setup

### Recommended Production Setup
```bash
# 1. Use Python 3.8+
python3.8 -m venv venv
source venv/bin/activate

# 2. Install requirements
pip install -r requirements.txt

# 3. Set environment variables
export DJANGO_SETTINGS_MODULE=hotel_pms.settings
export DJANGO_DEBUG=False

# 4. Run checks
python manage.py check --deploy

# 5. Collect static files
python manage.py collectstatic --noinput

# 6. Run migrations
python manage.py migrate
```

## Prevention Tips

1. **Use same Python version** in development and production
2. **Test deployment** in staging environment first
3. **Use proper file transfer** (binary mode for .py files)
4. **Set up proper virtual environment** in production
5. **Use environment variables** for configuration
6. **Regular backups** before migrations

## Need Help?

If the issue persists:

1. Run `python fix_production_migration.py` and share the output
2. Check your web server error logs
3. Verify your deployment process
4. Consider using Docker for consistent environments