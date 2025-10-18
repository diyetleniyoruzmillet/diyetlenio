"""
Management command to reset database and create initial data
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from core.models import Rol, Kullanici


class Command(BaseCommand):
    help = 'Reset database and create initial admin user'

    def handle(self, *args, **options):
        self.stdout.write('Starting database reset...')
        
        # Drop all tables if they exist
        with connection.cursor() as cursor:
            # Get all table names
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            if tables:
                # Disable foreign key checks
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                # Drop all tables
                for table in tables:
                    table_name = table[0]
                    self.stdout.write(f'Dropping table: {table_name}')
                    cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                
                # Re-enable foreign key checks
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                
                self.stdout.write('All tables dropped.')
            else:
                self.stdout.write('No tables found.')
        
        # Run migrations
        self.stdout.write('Running migrations...')
        call_command('migrate', verbosity=0)
        
        # Create admin role
        self.stdout.write('Creating admin role...')
        admin_rol, created = Rol.objects.get_or_create(rol_adi='admin')
        if created:
            self.stdout.write('Admin role created.')
        else:
            self.stdout.write('Admin role already exists.')
        
        # Create admin user
        self.stdout.write('Creating admin user...')
        try:
            admin_user = Kullanici.objects.create_superuser(
                e_posta='admin@diyetlenio.com',
                ad='Admin',
                soyad='User',
                rol=admin_rol,
                password='admin123'
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Admin user created successfully!\n'
                    f'Email: admin@diyetlenio.com\n'
                    f'Password: admin123'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating admin user: {e}')
            )
        
        self.stdout.write(self.style.SUCCESS('Database reset completed!'))