# Diyetlenio Production Deployment Guide 🚀

## 📋 Prerequisites

### System Requirements
- Ubuntu 20.04+ or CentOS 8+
- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Nginx 1.18+
- SSL Certificate

### Recommended Hardware
- **Minimum:** 2 vCPU, 4GB RAM, 50GB SSD
- **Production:** 4 vCPU, 8GB RAM, 100GB SSD

## 🔧 Server Setup

### 1. Update System
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib redis-server nginx
```

### 2. Create Application User
```bash
sudo adduser --system --group --no-create-home diyetlenio
sudo usermod -a -G www-data diyetlenio
```

### 3. Setup PostgreSQL
```bash
sudo -u postgres createuser --createdb diyetlenio_user
sudo -u postgres createdb diyetlenio_prod --owner=diyetlenio_user
sudo -u postgres psql -c "ALTER USER diyetlenio_user PASSWORD 'your-secure-password';"
```

### 4. Configure Redis
```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

## 🚀 Application Deployment

### 1. Clone Repository
```bash
cd /var/www
sudo git clone https://github.com/yourusername/diyetlenio.git
sudo chown -R diyetlenio:www-data /var/www/diyetlenio
cd /var/www/diyetlenio
```

### 2. Environment Setup
```bash
# Copy and configure environment variables
cp .env.example .env
nano .env  # Configure all variables

# Set proper permissions
chmod 600 .env
```

### 3. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-production.txt
```

### 4. Database Setup
```bash
export DJANGO_SETTINGS_MODULE=diyetlenio_project.settings_production
python manage.py migrate
python manage.py collectstatic --no-input
python manage.py setup_production --admin-password YOUR_SECURE_PASSWORD
```

### 5. Run Deployment Script
```bash
./deploy.sh production
```

## 🔐 Security Configuration

### 1. SSL Certificate (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo systemctl enable certbot.timer
```

### 2. Firewall Setup
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 3. Additional Security
```bash
# Fail2ban for brute force protection
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

## 📊 Monitoring & Logging

### 1. Application Logs
```bash
# View application logs
sudo journalctl -u diyetlenio.service -f

# Application-specific logs
tail -f /var/www/diyetlenio/logs/django.log
```

### 2. System Monitoring
```bash
# Service status
sudo systemctl status diyetlenio nginx postgresql redis

# Resource usage
htop
df -h
free -m
```

### 3. Health Checks
```bash
# API health check
curl https://yourdomain.com/health/

# Database connectivity
sudo -u diyetlenio bash -c "cd /var/www/diyetlenio && source venv/bin/activate && python manage.py shell -c 'from django.db import connection; connection.ensure_connection(); print(\"DB OK\")'"
```

## 🔄 Maintenance

### 1. Database Backup
```bash
# Manual backup
python manage.py backup_db --output-dir /var/backups/diyetlenio --compress

# Automated daily backup (crontab)
sudo crontab -e
# Add: 0 2 * * * /var/www/diyetlenio/venv/bin/python /var/www/diyetlenio/manage.py backup_db --output-dir /var/backups/diyetlenio --compress
```

### 2. Updates & Maintenance
```bash
# Application update
cd /var/www/diyetlenio
sudo git pull origin main
source venv/bin/activate
pip install -r requirements-production.txt
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl restart diyetlenio
```

### 3. Log Rotation
```bash
# Configure logrotate
sudo nano /etc/logrotate.d/diyetlenio

# Add configuration:
/var/www/diyetlenio/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 diyetlenio www-data
    postrotate
        systemctl reload diyetlenio
    endscript
}
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Permission Errors
```bash
# Fix file permissions
sudo chown -R diyetlenio:www-data /var/www/diyetlenio
sudo chmod -R 755 /var/www/diyetlenio
sudo chmod 600 /var/www/diyetlenio/.env
```

#### 2. Database Connection Issues
```bash
# Test database connection
sudo -u postgres psql -c "\\l"
# Check if user can connect
psql -h localhost -U diyetlenio_user -d diyetlenio_prod -c "SELECT version();"
```

#### 3. Static Files Not Loading
```bash
# Recollect static files
python manage.py collectstatic --clear --no-input
# Check nginx configuration
sudo nginx -t
```

#### 4. API Not Responding
```bash
# Check service status
sudo systemctl status diyetlenio
# Check logs
sudo journalctl -u diyetlenio.service --no-pager
# Restart service
sudo systemctl restart diyetlenio
```

## 📈 Performance Optimization

### 1. Database Optimization
```sql
-- Create indexes for frequently queried fields
CREATE INDEX idx_kullanici_email ON kullanicilar(e_posta);
CREATE INDEX idx_randevu_tarih ON randevular(randevu_tarih_saat);
CREATE INDEX idx_randevu_durum ON randevular(durum);
```

### 2. Caching
- Redis is configured for session storage and caching
- API responses are cached where appropriate
- Static files have long-term caching headers

### 3. Monitoring
```bash
# Setup performance monitoring
pip install django-debug-toolbar  # Development only
# Configure APM tools like New Relic or DataDog for production
```

## 🔗 API Endpoints

### Authentication
- `POST /api/v1/auth/login/` - User login
- `POST /api/v1/auth/register/danisan/` - Patient registration
- `POST /api/v1/auth/register/diyetisyen/` - Dietitian registration

### Core Features
- `GET /api/v1/users/dietitians/` - List dietitians
- `GET /api/v1/appointments/` - Appointments management
- `GET /api/v1/diet-plans/` - Diet plans
- `GET /api/v1/articles/public/` - Published articles
- `GET /api/v1/reviews/dietitian/{id}/` - Dietitian reviews

### Admin
- `GET /api/v1/admin/statistics/` - Platform statistics
- `GET /api/v1/analytics/platform/` - Advanced analytics

### Documentation
- `GET /api/docs/` - Swagger API documentation
- `GET /health/` - Health check endpoint

## 📞 Support

For deployment support or issues:
1. Check logs: `/var/www/diyetlenio/logs/django.log`
2. Review nginx logs: `/var/log/nginx/error.log`
3. System logs: `sudo journalctl -xe`

## 🎯 Production Checklist

- [ ] Environment variables configured
- [ ] Database created and migrated
- [ ] SSL certificate installed
- [ ] Firewall configured
- [ ] Backup system setup
- [ ] Monitoring enabled
- [ ] Domain name configured
- [ ] Admin user created
- [ ] API documentation accessible
- [ ] Health check responding
- [ ] Performance monitoring setup