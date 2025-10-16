#!/usr/bin/env python3
"""
Simple health check script for production deployment verification.
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'diyetlenio_project.settings')
django.setup()

def check_health():
    """Run basic health checks."""
    checks = []
    
    # Check Django
    try:
        from django.conf import settings
        checks.append("✅ Django configured")
    except Exception as e:
        checks.append(f"❌ Django error: {e}")
        return False, checks
    
    # Check database
    try:
        from django.db import connection
        connection.ensure_connection()
        checks.append("✅ Database connection OK")
    except Exception as e:
        checks.append(f"❌ Database error: {e}")
        return False, checks
    
    # Check models
    try:
        from core.models import Kullanici, Rol
        role_count = Rol.objects.count()
        user_count = Kullanici.objects.count()
        checks.append(f"✅ Models accessible (Roles: {role_count}, Users: {user_count})")
    except Exception as e:
        checks.append(f"❌ Model error: {e}")
        return False, checks
    
    # Check APIs
    try:
        from django.urls import reverse
        from django.test import Client
        client = Client()
        response = client.get('/health/')
        if response.status_code == 200:
            checks.append("✅ Health endpoint responding")
        else:
            checks.append(f"⚠️ Health endpoint status: {response.status_code}")
    except Exception as e:
        checks.append(f"❌ API error: {e}")
    
    return True, checks

if __name__ == "__main__":
    print("🏥 Running Diyetlenio Health Check...")
    success, checks = check_health()
    
    for check in checks:
        print(check)
    
    if success:
        print("\n🎉 Health check passed!")
        sys.exit(0)
    else:
        print("\n💥 Health check failed!")
        sys.exit(1)