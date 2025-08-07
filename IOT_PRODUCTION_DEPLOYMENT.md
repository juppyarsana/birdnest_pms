# IoT Production Deployment Checklist

## 🚨 Troubleshooting 500 Error on `/iot`

### **Step 1: Check Database Migrations**
```bash
# Run these commands on your production server
python manage.py showmigrations iot
python manage.py migrate iot
python manage.py migrate
```

### **Step 2: Verify Dependencies**
Ensure all required packages are installed:
```bash
pip install -r requirements.txt
```

Required packages for IoT:
- `requests>=2.31,<3.0` (for ESP32 communication)
- `Django>=5.0,<6.0`

### **Step 3: Collect Static Files**
```bash
python manage.py collectstatic --noinput
```

### **Step 4: Check Environment Variables**
Ensure your production `.env` file has:
```env
# IoT Configuration
ESP32_DEFAULT_USERNAME=admin
ESP32_DEFAULT_PASSWORD=your-esp32-password-here
IOT_NETWORK_ALLOWED=True
IOT_CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### **Step 5: Verify Django Settings**
In `settings.py`, ensure:
```python
INSTALLED_APPS = [
    # ... other apps
    'iot',  # Make sure this is included
]
```

### **Step 6: Check URL Configuration**
In main `urls.py`, ensure:
```python
urlpatterns = [
    # ... other patterns
    path('iot/', include('iot.urls')),
]
```

### **Step 7: Test Database Connection**
```bash
python manage.py shell
```
Then run:
```python
from iot.models import ESP32Device, RoomControls
from pms.models import Room

# Test if models can be imported and queried
print("IoT models imported successfully")
print(f"Rooms count: {Room.objects.count()}")
print(f"ESP32 devices count: {ESP32Device.objects.count()}")
```

### **Step 8: Check Server Logs**
Look for specific error messages in your server logs:
- Apache/Nginx error logs
- Django application logs
- Gunicorn logs (if using Gunicorn)

### **Step 9: Debug Mode (Temporarily)**
**⚠️ ONLY for debugging - disable immediately after:**
```env
DJANGO_DEBUG=True
```
This will show the actual error message instead of generic 500.

### **Step 10: Common Production Issues**

#### **Database Issues:**
- Missing IoT tables (run migrations)
- Foreign key constraints (ensure PMS app is migrated first)

#### **Permission Issues:**
- Static files directory permissions
- Database file permissions (if using SQLite)
- Log directory permissions

#### **Network Issues:**
- ESP32 devices not reachable from production server
- Firewall blocking ESP32 communication ports

#### **Template Issues:**
- Missing template files
- Template syntax errors
- Missing template context variables

## **Quick Fix Commands**

Run these commands in order on your production server:

```bash
# 1. Apply all migrations
python manage.py migrate

# 2. Collect static files
python manage.py collectstatic --noinput

# 3. Create superuser if needed
python manage.py createsuperuser

# 4. Test IoT models
python manage.py shell -c "from iot.models import ESP32Device; print('IoT models OK')"

# 5. Restart your web server
# For Gunicorn:
sudo systemctl restart gunicorn
# For Apache:
sudo systemctl restart apache2
# For Nginx:
sudo systemctl restart nginx
```

## **Production-Specific IoT Configuration**

### **1. Database Setup**
If using PostgreSQL/MySQL in production:
```sql
-- Ensure proper permissions for IoT tables
GRANT ALL PRIVILEGES ON iot_* TO your_db_user;
```

### **2. Network Configuration**
- Ensure ESP32 devices are on the same network as production server
- Configure firewall rules to allow ESP32 communication
- Set up static IP addresses for ESP32 devices

### **3. Security Settings**
```python
# In production settings.py
if not DEBUG:
    # Add your production domain
    ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
    
    # CORS settings for ESP32 communication
    IOT_CORS_ORIGINS = ['https://yourdomain.com']
```

### **4. Monitoring**
Set up monitoring for:
- ESP32 device connectivity
- IoT command success rates
- Database performance for IoT operations

## **Testing IoT Functionality**

After deployment, test these URLs:
1. `https://yourdomain.com/iot/` - Should show room access page
2. `https://yourdomain.com/iot/smart/` - Should show smart room access
3. `https://yourdomain.com/iot/room/101/` - Should show room control (if room 101 exists)
4. `https://yourdomain.com/admin/iot/` - Should show IoT admin interface

## **Emergency Rollback**

If IoT functionality breaks production:
1. Comment out IoT URLs in main `urls.py`:
   ```python
   # path('iot/', include('iot.urls')),
   ```
2. Restart web server
3. Fix issues and re-enable