#!/usr/bin/env python
"""
Production Migration Fix Script
Fixes common syntax errors and migration issues in production environment.

Usage: python fix_production_migration.py
"""

import os
import sys
import subprocess
import tempfile

def check_python_version():
    """Check Python version compatibility"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    print(f"Current Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ is required for Django 4.x")
        return False
    else:
        print("✅ Python version is compatible")
        return True

def check_file_encoding():
    """Check and fix file encoding issues"""
    print("\n📝 Checking file encoding...")
    
    files_to_check = [
        'manage.py',
        'hotel_pms/settings.py',
        'iot/models.py',
        'iot/views.py',
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            try:
                # Try to read file with UTF-8 encoding
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for Windows line endings and convert if needed
                if '\r\n' in content:
                    print(f"🔧 Converting line endings for {file_path}")
                    content = content.replace('\r\n', '\n')
                    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                        f.write(content)
                
                print(f"✅ {file_path} encoding OK")
                
            except UnicodeDecodeError:
                print(f"❌ {file_path} has encoding issues")
                return False
            except Exception as e:
                print(f"⚠️ Could not check {file_path}: {e}")
    
    return True

def check_migration_files():
    """Check migration files for syntax errors"""
    print("\n🔄 Checking migration files...")
    
    migration_dirs = ['pms/migrations', 'iot/migrations']
    
    for migration_dir in migration_dirs:
        if os.path.exists(migration_dir):
            for filename in os.listdir(migration_dir):
                if filename.endswith('.py') and not filename.startswith('__'):
                    file_path = os.path.join(migration_dir, filename)
                    try:
                        # Try to compile the Python file
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        compile(content, file_path, 'exec')
                        print(f"✅ {file_path} syntax OK")
                        
                    except SyntaxError as e:
                        print(f"❌ Syntax error in {file_path}: {e}")
                        return False
                    except Exception as e:
                        print(f"⚠️ Could not check {file_path}: {e}")
    
    return True

def fix_common_issues():
    """Fix common production issues"""
    print("\n🔧 Applying common fixes...")
    
    # 1. Ensure __pycache__ is cleared
    print("Clearing Python cache files...")
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            try:
                import shutil
                shutil.rmtree(pycache_path)
                print(f"✅ Cleared {pycache_path}")
            except Exception as e:
                print(f"⚠️ Could not clear {pycache_path}: {e}")
    
    # 2. Check for .pyc files
    print("Removing .pyc files...")
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                pyc_path = os.path.join(root, file)
                try:
                    os.remove(pyc_path)
                    print(f"✅ Removed {pyc_path}")
                except Exception as e:
                    print(f"⚠️ Could not remove {pyc_path}: {e}")
    
    return True

def test_django_import():
    """Test if Django can be imported properly"""
    print("\n🧪 Testing Django import...")
    
    try:
        import django
        print(f"✅ Django version: {django.get_version()}")
        
        # Set Django settings
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_pms.settings')
        django.setup()
        
        print("✅ Django setup successful")
        return True
        
    except ImportError as e:
        print(f"❌ Django import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False

def run_safe_migration():
    """Run migration with error handling"""
    print("\n🚀 Running safe migration...")
    
    try:
        # First, check what migrations are needed
        print("Checking migration status...")
        result = subprocess.run([
            sys.executable, 'manage.py', 'showmigrations', '--plan'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Migration check successful")
            print(result.stdout)
        else:
            print(f"❌ Migration check failed: {result.stderr}")
            return False
        
        # Run makemigrations first
        print("Creating new migrations...")
        result = subprocess.run([
            sys.executable, 'manage.py', 'makemigrations'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Makemigrations successful")
            if result.stdout.strip():
                print(result.stdout)
        else:
            print(f"⚠️ Makemigrations output: {result.stderr}")
        
        # Run migrate
        print("Applying migrations...")
        result = subprocess.run([
            sys.executable, 'manage.py', 'migrate'
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✅ Migration successful")
            print(result.stdout)
            return True
        else:
            print(f"❌ Migration failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Migration timed out")
        return False
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False

def main():
    """Run all fixes and checks"""
    print("🏥 Production Migration Fix Tool")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("File Encoding", check_file_encoding),
        ("Migration Files", check_migration_files),
        ("Common Issues", fix_common_issues),
        ("Django Import", test_django_import),
    ]
    
    all_passed = True
    for name, check_func in checks:
        try:
            result = check_func()
            if not result:
                all_passed = False
                print(f"\n❌ {name} check failed!")
                break
        except Exception as e:
            print(f"\n❌ {name} check crashed: {e}")
            all_passed = False
            break
    
    if all_passed:
        print("\n" + "=" * 50)
        print("🎯 All checks passed! Running migration...")
        print("=" * 50)
        
        if run_safe_migration():
            print("\n🎉 Migration completed successfully!")
        else:
            print("\n❌ Migration failed. Check the error messages above.")
            print("\n💡 Manual steps to try:")
            print("1. Check your Python version: python --version")
            print("2. Check Django installation: pip show django")
            print("3. Try: python manage.py check")
            print("4. Try: python manage.py migrate --fake-initial")
    else:
        print("\n❌ Some checks failed. Fix the issues above first.")
    
    print("\n📋 Production Deployment Checklist:")
    print("✓ Python 3.8+ installed")
    print("✓ All dependencies installed: pip install -r requirements.txt")
    print("✓ Environment variables set (.env file)")
    print("✓ Database configured")
    print("✓ Static files collected: python manage.py collectstatic")
    print("✓ Migrations applied")

if __name__ == "__main__":
    main()