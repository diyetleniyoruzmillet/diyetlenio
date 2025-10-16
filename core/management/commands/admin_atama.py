from django.core.management.base import BaseCommand, CommandError
from core.utils import AdminUtils
from core.models import Kullanici, Randevu, Diyetisyen


class Command(BaseCommand):
    help = 'Admin randevu yeniden atama (equivalent to admin_randevu_yeniden_atama function)'

    def add_arguments(self, parser):
        parser.add_argument('admin_id', type=int, help='Admin kullanıcı ID')
        parser.add_argument('randevu_id', type=int, help='Randevu ID')
        parser.add_argument('hedef_diyetisyen_id', type=int, help='Hedef diyetisyen kullanıcı ID')
        parser.add_argument('--neden', type=str, help='Atama nedeni', default='Manuel admin ataması')

    def handle(self, *args, **options):
        admin_id = options['admin_id']
        randevu_id = options['randevu_id']
        hedef_diyetisyen_id = options['hedef_diyetisyen_id']
        neden = options['neden']
        
        try:
            # Kullanıcıları kontrol et
            admin = Kullanici.objects.get(id=admin_id)
            randevu = Randevu.objects.get(id=randevu_id)
            hedef_diyetisyen = Diyetisyen.objects.get(kullanici_id=hedef_diyetisyen_id)
            
            self.stdout.write(f'Admin: {admin.ad} {admin.soyad}')
            self.stdout.write(f'Randevu: #{randevu_id} - {randevu.danisan.ad} {randevu.danisan.soyad}')
            self.stdout.write(f'Mevcut Diyetisyen: {randevu.diyetisyen.kullanici.ad} {randevu.diyetisyen.kullanici.soyad}')
            self.stdout.write(f'Hedef Diyetisyen: {hedef_diyetisyen.kullanici.ad} {hedef_diyetisyen.kullanici.soyad}')
            self.stdout.write(f'Neden: {neden}')
            
            # Onay al
            confirm = input('Randevu ataması yapılsın mı? (yes/no): ')
            if confirm.lower() not in ['yes', 'y']:
                self.stdout.write('İşlem iptal edildi.')
                return
            
            # Atama işlemini gerçekleştir
            result = AdminUtils.admin_randevu_yeniden_atama(
                admin_id, randevu_id, hedef_diyetisyen_id, neden
            )
            
            if result:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Randevu #{randevu_id} başarıyla '
                        f'{hedef_diyetisyen.kullanici.ad} {hedef_diyetisyen.kullanici.soyad} '
                        f'diyetisyenine atandı!'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Atama işlemi başarısız!')
                )
                
        except Kullanici.DoesNotExist:
            raise CommandError(f'Admin kullanıcı bulunamadı (ID: {admin_id})')
        except Randevu.DoesNotExist:
            raise CommandError(f'Randevu bulunamadı (ID: {randevu_id})')
        except Diyetisyen.DoesNotExist:
            raise CommandError(f'Hedef diyetisyen bulunamadı (ID: {hedef_diyetisyen_id})')
        except Exception as e:
            raise CommandError(f'Atama hatası: {str(e)}')