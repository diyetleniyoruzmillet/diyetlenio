#!/bin/bash

# Diyetlenio Production Deployment Script
# Usage: ./deploy.sh [production|staging]

set -e  # Exit on any error

ENVIRONMENT=${1:-production}
PROJECT_DIR="$(pwd)"
VENV_DIR="$PROJECT_DIR/venv"

echo "🚀 Starting Diyetlenio deployment for $ENVIRONMENT..."

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    log_error ".env file not found! Copy .env.example to .env and configure it."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Update pip
log_info "Updating pip..."
pip install --upgrade pip

# Install/update dependencies
log_info "Installing Python dependencies..."
pip install -r requirements.txt

# Install additional production dependencies
if [ "$ENVIRONMENT" = "production" ]; then
    log_info "Installing production dependencies..."
    pip install gunicorn psycopg2-binary redis django-redis sentry-sdk
fi

# Set Django settings module
if [ "$ENVIRONMENT" = "production" ]; then
    export DJANGO_SETTINGS_MODULE=diyetlenio_project.settings_production
else
    export DJANGO_SETTINGS_MODULE=diyetlenio_project.settings
fi

# Database migrations
log_info "Running database migrations..."
python manage.py makemigrations --no-input
python manage.py migrate --no-input

# Collect static files
log_info "Collecting static files..."
python manage.py collectstatic --no-input --clear

# Setup production data (if needed)
if [ "$ENVIRONMENT" = "production" ]; then
    log_info "Setting up production environment..."
    echo "Enter admin password for production setup:"
    read -s ADMIN_PASSWORD
    python manage.py setup_production --admin-password "$ADMIN_PASSWORD"
fi

# Create backup
if [ "$ENVIRONMENT" = "production" ]; then
    log_info "Creating database backup..."
    mkdir -p backups
    python manage.py backup_db --output-dir backups --compress
fi

# Check deployment
log_info "Running deployment checks..."
python manage.py check --deploy

# Test database connection
log_info "Testing database connection..."
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('Database connection: OK')"

# Create systemd service file (production only)
if [ "$ENVIRONMENT" = "production" ]; then
    log_info "Creating systemd service files..."
    
    # Gunicorn service
    sudo tee /etc/systemd/system/diyetlenio.service > /dev/null <<EOF
[Unit]
Description=Diyetlenio Django Application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=$PROJECT_DIR
Environment=DJANGO_SETTINGS_MODULE=diyetlenio_project.settings_production
ExecStart=$VENV_DIR/bin/gunicorn --workers 3 --bind unix:$PROJECT_DIR/diyetlenio.sock diyetlenio_project.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    # Celery service (if using background tasks)
    sudo tee /etc/systemd/system/diyetlenio-celery.service > /dev/null <<EOF
[Unit]
Description=Diyetlenio Celery Worker
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=$PROJECT_DIR
Environment=DJANGO_SETTINGS_MODULE=diyetlenio_project.settings_production
ExecStart=$VENV_DIR/bin/celery -A diyetlenio_project worker -D
ExecStop=$VENV_DIR/bin/celery -A diyetlenio_project control shutdown
ExecReload=$VENV_DIR/bin/celery -A diyetlenio_project control reload
PIDFile=/var/run/celery/diyetlenio.pid
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and start services
    sudo systemctl daemon-reload
    sudo systemctl enable diyetlenio.service
    sudo systemctl restart diyetlenio.service
    
    log_info "Systemd services configured and started"
fi

# Create nginx configuration (production only)
if [ "$ENVIRONMENT" = "production" ]; then
    log_info "Creating nginx configuration..."
    sudo tee /etc/nginx/sites-available/diyetlenio > /dev/null <<EOF
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration (update paths to your certificates)
    ssl_certificate /etc/ssl/certs/diyetlenio.crt;
    ssl_certificate_key /etc/ssl/private/diyetlenio.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root $PROJECT_DIR;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    location /media/ {
        root $PROJECT_DIR;
        expires 1y;
        add_header Cache-Control "public";
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/diyetlenio.sock;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Port 443;
    }

    # Health check endpoint
    location /health/ {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    client_max_body_size 10M;
}
EOF

    # Enable site
    sudo ln -sf /etc/nginx/sites-available/diyetlenio /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    
    log_info "Nginx configuration created and reloaded"
fi

# Final status check
log_info "Running final health checks..."

# Check if services are running (production)
if [ "$ENVIRONMENT" = "production" ]; then
    if systemctl is-active --quiet diyetlenio.service; then
        log_info "✅ Diyetlenio service is running"
    else
        log_error "❌ Diyetlenio service is not running"
        sudo systemctl status diyetlenio.service
    fi
    
    if systemctl is-active --quiet nginx; then
        log_info "✅ Nginx is running"
    else
        log_warn "⚠️ Nginx is not running"
    fi
fi

# Display deployment summary
echo ""
echo "🎉 Deployment completed for $ENVIRONMENT!"
echo ""
echo "📋 Summary:"
echo "  - Environment: $ENVIRONMENT"
echo "  - Project directory: $PROJECT_DIR"
echo "  - Virtual environment: $VENV_DIR"
echo "  - Django settings: $DJANGO_SETTINGS_MODULE"
echo ""

if [ "$ENVIRONMENT" = "production" ]; then
    echo "🔗 Production URLs:"
    echo "  - API Documentation: https://yourdomain.com/api/docs/"
    echo "  - Admin Panel: https://yourdomain.com/admin/"
    echo "  - Health Check: https://yourdomain.com/health/"
    echo ""
    echo "📝 Next steps:"
    echo "  1. Update domain names in nginx config"
    echo "  2. Install SSL certificates"
    echo "  3. Configure firewall (ufw)"
    echo "  4. Setup monitoring (optional)"
    echo "  5. Configure automated backups"
fi

echo ""
log_info "Deployment script completed successfully! 🚀"