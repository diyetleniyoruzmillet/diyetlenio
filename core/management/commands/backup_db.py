"""
Django management command to backup database.
"""
import os
import subprocess
import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Create database backup'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            help='Output directory for backup files',
            default='./backups'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress backup file'
        )
    
    def handle(self, *args, **options):
        # Get database settings
        db_settings = settings.DATABASES['default']
        
        if db_settings['ENGINE'] != 'django.db.backends.postgresql':
            self.stdout.write(
                self.style.ERROR('This command only supports PostgreSQL databases')
            )
            return
        
        # Create backup directory
        backup_dir = options['output_dir']
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"diyetlenio_backup_{timestamp}.sql"
        
        if options['compress']:
            filename += '.gz'
        
        backup_path = os.path.join(backup_dir, filename)
        
        # Prepare pg_dump command
        cmd = [
            'pg_dump',
            '--host', db_settings.get('HOST', 'localhost'),
            '--port', str(db_settings.get('PORT', 5432)),
            '--username', db_settings['USER'],
            '--dbname', db_settings['NAME'],
            '--no-password',
            '--verbose',
        ]
        
        if options['compress']:
            cmd.extend(['--compress', '9'])
        
        # Set environment variables
        env = os.environ.copy()
        env['PGPASSWORD'] = db_settings['PASSWORD']
        
        self.stdout.write(f'Creating backup: {backup_path}')
        
        try:
            with open(backup_path, 'wb') as backup_file:
                process = subprocess.run(
                    cmd,
                    env=env,
                    stdout=backup_file,
                    stderr=subprocess.PIPE,
                    check=True
                )
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            size_mb = file_size / (1024 * 1024)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Backup created successfully: {backup_path} ({size_mb:.2f} MB)'
                )
            )
            
        except subprocess.CalledProcessError as e:
            self.stdout.write(
                self.style.ERROR(f'Backup failed: {e.stderr.decode()}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Backup failed: {str(e)}')
            )