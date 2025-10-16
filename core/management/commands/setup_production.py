"""
Django management command to setup production environment.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from core.models import Rol, UzmanlikAlani, SistemAyari
import os


class Command(BaseCommand):
    help = 'Setup production environment with initial data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-email',
            type=str,
            help='Admin user email',
            default='admin@diyetlenio.com'
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            help='Admin user password',
            required=True
        )
        parser.add_argument(
            '--skip-superuser',
            action='store_true',
            help='Skip superuser creation'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('🚀 Setting up production environment...')
        
        # 1. Create roles if they don't exist
        self.setup_roles()
        
        # 2. Create specialty areas
        self.setup_specialties()
        
        # 3. Create admin user if requested
        if not options['skip_superuser']:
            self.create_admin_user(options['admin_email'], options['admin_password'])
        
        # 4. Setup system settings
        self.setup_system_settings()
        
        # 5. Security checks
        self.run_security_checks()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Production setup completed successfully!')
        )
    
    def setup_roles(self):
        """Create user roles."""
        roles = ['admin', 'diyetisyen', 'danisan']
        
        for role_name in roles:
            role, created = Rol.objects.get_or_create(
                rol_adi=role_name,
                defaults={'aciklama': f'{role_name} rolü'}
            )
            if created:
                self.stdout.write(f'Created role: {role_name}')
            else:
                self.stdout.write(f'Role already exists: {role_name}')
    
    def setup_specialties(self):
        """Create specialty areas."""
        specialties = [
            'Genel Beslenme',
            'Spor Beslenmesi',
            'Klinik Beslenme',
            'Pediatrik Beslenme',
            'Geriatrik Beslenme',
            'Diyabet Beslenmesi',
            'Kalp Sağlığı Beslenmesi',
            'Vegan/Vejetaryen Beslenme',
            'Obezite ve Kilo Yönetimi'
        ]
        
        for specialty in specialties:
            obj, created = UzmanlikAlani.objects.get_or_create(
                alan_adi=specialty
            )
            if created:
                self.stdout.write(f'Created specialty: {specialty}')
    
    def create_admin_user(self, email, password):
        """Create admin user."""
        User = get_user_model()
        
        if User.objects.filter(e_posta=email).exists():
            self.stdout.write(f'Admin user {email} already exists')
            return
        
        # Get admin role
        try:
            admin_role = Rol.objects.get(rol_adi='admin')
        except Rol.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Admin role not found. Run setup_roles first.')
            )
            return
        
        # Create admin user
        admin_user = User.objects.create_user(
            e_posta=email,
            password=password,
            ad='System',
            soyad='Administrator',
            rol=admin_role,
            is_superuser=True,
            is_staff=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Created admin user: {email}')
        )
    
    def setup_system_settings(self):
        """Setup default system settings."""
        default_settings = {
            'site_name': 'Diyetlenio',
            'site_description': 'Online Diyetisyen Platformu',
            'maintenance_mode': False,
            'registration_enabled': True,
            'email_verification_required': True,
            'max_file_upload_size': 10485760,  # 10MB
            'allowed_file_extensions': 'pdf,doc,docx,jpg,jpeg,png,gif',
            'session_timeout_minutes': 60,
            'password_reset_timeout_minutes': 30,
        }
        
        for key, value in default_settings.items():
            setting, created = SistemAyari.objects.get_or_create(
                anahtar=key,
                defaults={'deger': str(value)}
            )
            if created:
                self.stdout.write(f'Created system setting: {key} = {value}')
    
    def run_security_checks(self):
        """Run basic security checks."""
        checks = []
        
        # Check SECRET_KEY
        if settings.SECRET_KEY == 'your-super-secret-key-here-change-this-in-production':
            checks.append('❌ SECRET_KEY is still default value!')
        else:
            checks.append('✅ SECRET_KEY is configured')
        
        # Check DEBUG
        if settings.DEBUG:
            checks.append('❌ DEBUG is True in production!')
        else:
            checks.append('✅ DEBUG is False')
        
        # Check ALLOWED_HOSTS
        if not settings.ALLOWED_HOSTS or settings.ALLOWED_HOSTS == ['*']:
            checks.append('❌ ALLOWED_HOSTS is not properly configured!')
        else:
            checks.append('✅ ALLOWED_HOSTS is configured')
        
        # Check database password
        db_password = settings.DATABASES['default'].get('PASSWORD')
        if not db_password or db_password == 'your-secure-database-password':
            checks.append('❌ Database password is not secure!')
        else:
            checks.append('✅ Database password is configured')
        
        self.stdout.write('\n🔐 Security Check Results:')
        for check in checks:
            if '❌' in check:
                self.stdout.write(self.style.ERROR(check))
            else:
                self.stdout.write(self.style.SUCCESS(check))
        
        # Check if any critical issues
        critical_issues = [c for c in checks if '❌' in c]
        if critical_issues:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  Found {len(critical_issues)} security issues. '
                    'Please fix them before deploying to production!'
                )
            )