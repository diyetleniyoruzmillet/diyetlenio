from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta, time, date
from core.models import (
    Diyetisyen, DiyetisyenMusaitlikSablon, DiyetisyenIzin, 
    Randevu, Kullanici
)


class MusaitlikService:
    
    @staticmethod
    def get_diyetisyen_musaitlik_sablonu(diyetisyen):
        """Diyetisyenin haftalık çalışma saatlerini getir"""
        return DiyetisyenMusaitlikSablon.objects.filter(
            diyetisyen=diyetisyen,
            aktif=True
        ).order_by('gun', 'baslangic_saati')
    
    @staticmethod
    def set_diyetisyen_musaitlik_sablonu(diyetisyen, musaitlik_data):
        """Diyetisyenin haftalık çalışma saatlerini güncelle"""
        
        with transaction.atomic():
            # Mevcut şablonları pasifleştir
            DiyetisyenMusaitlikSablon.objects.filter(
                diyetisyen=diyetisyen
            ).update(aktif=False)
            
            # Yeni şablonları oluştur
            for data in musaitlik_data:
                try:
                    MusaitlikService._validate_time_range(
                        data['baslangic_saati'], 
                        data['bitis_saati']
                    )
                    
                    DiyetisyenMusaitlikSablon.objects.create(
                        diyetisyen=diyetisyen,
                        gun=data['gun'],
                        baslangic_saati=data['baslangic_saati'],
                        bitis_saati=data['bitis_saati'],
                        aktif=True
                    )
                except ValidationError as e:
                    raise ValidationError(f"Gün {data['gun']} için hata: {str(e)}")
    
    @staticmethod
    def get_available_slots(diyetisyen, start_date, end_date, slot_duration=30):
        """Belirli tarih aralığında müsait saatleri getir"""
        
        # Diyetisyenin çalışma saatlerini al
        sablon = MusaitlikService.get_diyetisyen_musaitlik_sablonu(diyetisyen)
        if not sablon.exists():
            return {}
        
        # İzin günlerini al
        izinler = DiyetisyenIzin.objects.filter(
            diyetisyen=diyetisyen,
            baslangic_tarihi__lte=end_date,
            bitis_tarihi__gte=start_date
        )
        
        # Mevcut randevuları al
        randevular = Randevu.objects.filter(
            diyetisyen=diyetisyen,
            randevu_tarih_saat__date__range=[start_date, end_date],
            durum__in=['BEKLEMEDE', 'ONAYLANDI']
        )
        
        available_slots = {}
        current_date = start_date
        
        while current_date <= end_date:
            # Sadece gelecek tarihleri işle
            if current_date >= date.today():
                day_slots = MusaitlikService._get_day_available_slots(
                    diyetisyen, current_date, sablon, izinler, randevular, slot_duration
                )
                if day_slots:
                    for slot in day_slots:
                        available_slots[slot] = True
            
            current_date += timedelta(days=1)
        
        return available_slots
    
    @staticmethod
    def _get_day_available_slots(diyetisyen, target_date, sablon, izinler, randevular, slot_duration):
        """Belirli bir gün için müsait saatleri hesapla"""
        
        # Gün numarasını al (Pazartesi=1, Pazar=7)
        weekday = target_date.isoweekday()
        
        # Bu gün için çalışma saatlerini al
        gun_sablonlari = sablon.filter(gun=weekday)
        if not gun_sablonlari.exists():
            return []
        
        # Bu gün izinli mi kontrol et
        if MusaitlikService._is_day_off(target_date, izinler):
            return []
        
        # Bu gün için randevuları al
        gun_randevulari = randevular.filter(randevu_tarih_saat__date=target_date)
        occupied_times = set()
        for randevu in gun_randevulari:
            occupied_times.add(randevu.randevu_tarih_saat.time())
        
        # Müsait slotları hesapla
        available_slots = []
        
        for sablon_item in gun_sablonlari:
            # Saatlik izin kontrolü
            if MusaitlikService._is_time_off(target_date, sablon_item.baslangic_saati, sablon_item.bitis_saati, izinler):
                continue
                
            current_time = sablon_item.baslangic_saati
            end_time = sablon_item.bitis_saati
            
            while current_time < end_time:
                # Randevu varmı kontrol et
                if current_time not in occupied_times:
                    # Geçmiş saat mi kontrol et
                    slot_datetime = datetime.combine(target_date, current_time)
                    if slot_datetime > timezone.now():
                        slot_str = f"{target_date}T{current_time.strftime('%H:%M')}"
                        available_slots.append(slot_str)
                
                # Sonraki slota geç
                current_datetime = datetime.combine(target_date, current_time)
                current_datetime += timedelta(minutes=slot_duration)
                current_time = current_datetime.time()
        
        return available_slots
    
    @staticmethod
    def _is_day_off(target_date, izinler):
        """Belirli gün tam gün izinli mi kontrol et"""
        for izin in izinler:
            if (izin.baslangic_tarihi <= target_date <= izin.bitis_tarihi and 
                izin.izin_tipi == 'TAM_GUN'):
                return True
        return False
    
    @staticmethod
    def _is_time_off(target_date, start_time, end_time, izinler):
        """Belirli saat aralığı izinli mi kontrol et"""
        for izin in izinler:
            if izin.baslangic_tarihi <= target_date <= izin.bitis_tarihi:
                if izin.izin_tipi == 'SAATLIK':
                    if (izin.baslangic_saati <= start_time < izin.bitis_saati or
                        izin.baslangic_saati < end_time <= izin.bitis_saati):
                        return True
        return False
    
    @staticmethod
    def create_izin(diyetisyen, izin_data):
        """Diyetisyen için izin oluştur"""
        
        # Geçerlilik kontrolü
        if izin_data['baslangic_tarihi'] > izin_data['bitis_tarihi']:
            raise ValidationError("Başlangıç tarihi bitiş tarihinden sonra olamaz.")
        
        if izin_data['izin_tipi'] == 'SAATLIK':
            if not (izin_data.get('baslangic_saati') and izin_data.get('bitis_saati')):
                raise ValidationError("Saatlik izin için başlangıç ve bitiş saati gereklidir.")
            
            MusaitlikService._validate_time_range(
                izin_data['baslangic_saati'], 
                izin_data['bitis_saati']
            )
        
        # Çakışan izin kontrolü
        existing_izinler = DiyetisyenIzin.objects.filter(
            diyetisyen=diyetisyen,
            baslangic_tarihi__lte=izin_data['bitis_tarihi'],
            bitis_tarihi__gte=izin_data['baslangic_tarihi']
        )
        
        if existing_izinler.exists():
            raise ValidationError("Bu tarih aralığında zaten izin bulunmaktadır.")
        
        # İzin oluştur
        return DiyetisyenIzin.objects.create(
            diyetisyen=diyetisyen,
            **izin_data
        )
    
    @staticmethod
    def delete_izin(izin_id, diyetisyen):
        """İzin sil"""
        try:
            izin = DiyetisyenIzin.objects.get(id=izin_id, diyetisyen=diyetisyen)
            izin.delete()
            return True
        except DiyetisyenIzin.DoesNotExist:
            raise ValidationError("İzin bulunamadı.")
    
    @staticmethod
    def get_diyetisyen_izinler(diyetisyen, start_date=None, end_date=None):
        """Diyetisyenin izinlerini getir"""
        queryset = DiyetisyenIzin.objects.filter(diyetisyen=diyetisyen)
        
        if start_date:
            queryset = queryset.filter(bitis_tarihi__gte=start_date)
        if end_date:
            queryset = queryset.filter(baslangic_tarihi__lte=end_date)
        
        return queryset.order_by('baslangic_tarihi')
    
    @staticmethod
    def _validate_time_range(start_time, end_time):
        """Saat aralığı geçerliliğini kontrol et"""
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, '%H:%M').time()
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, '%H:%M').time()
        
        if start_time >= end_time:
            raise ValidationError("Başlangıç saati bitiş saatinden önce olmalıdır.")
        
        # İş saatleri kontrolü (6:00 - 22:00)
        if start_time < time(6, 0) or end_time > time(22, 0):
            raise ValidationError("Çalışma saatleri 06:00-22:00 arasında olmalıdır.")
    
    @staticmethod
    def get_weekly_schedule(diyetisyen, week_start_date):
        """Haftalık çalışma programını getir"""
        week_end_date = week_start_date + timedelta(days=6)
        
        # Çalışma saatleri şablonu
        sablon = MusaitlikService.get_diyetisyen_musaitlik_sablonu(diyetisyen)
        
        # İzinler
        izinler = DiyetisyenIzin.objects.filter(
            diyetisyen=diyetisyen,
            baslangic_tarihi__lte=week_end_date,
            bitis_tarihi__gte=week_start_date
        )
        
        # Randevular
        randevular = Randevu.objects.filter(
            diyetisyen=diyetisyen,
            randevu_tarih_saat__date__range=[week_start_date, week_end_date],
            durum__in=['BEKLEMEDE', 'ONAYLANDI', 'TAMAMLANDI']
        ).select_related('danisan')
        
        schedule = {}
        for i in range(7):
            current_date = week_start_date + timedelta(days=i)
            weekday = current_date.isoweekday()
            
            day_schedule = {
                'date': current_date,
                'weekday': weekday,
                'working_hours': list(sablon.filter(gun=weekday)),
                'is_off': MusaitlikService._is_day_off(current_date, izinler),
                'appointments': list(randevular.filter(randevu_tarih_saat__date=current_date)),
                'time_offs': []
            }
            
            # Saatlik izinleri ekle
            for izin in izinler:
                if (izin.baslangic_tarihi <= current_date <= izin.bitis_tarihi and 
                    izin.izin_tipi == 'SAATLIK'):
                    day_schedule['time_offs'].append(izin)
            
            schedule[weekday] = day_schedule
        
        return schedule