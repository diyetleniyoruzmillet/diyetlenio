"""
Custom validators for business logic validation
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q

from .models import Randevu, Diyetisyen, Kullanici, Musaitlik


class AppointmentValidator:
    """Validator for appointment-related business rules"""
    
    @staticmethod
    def validate_appointment_time(randevu_tarih_saat: datetime, diyetisyen: Diyetisyen) -> Tuple[bool, str]:
        """
        Validate appointment time against business rules
        Returns: (is_valid, error_message)
        """
        try:
            # 1. Check if appointment is in the future
            if randevu_tarih_saat <= timezone.now():
                return False, "Randevu tarihi gelecekte olmalıdır"
            
            # 2. Check if appointment is not too far in the future (max 3 months)
            max_future_date = timezone.now() + timedelta(days=90)
            if randevu_tarih_saat > max_future_date:
                return False, "Randevu tarihi en fazla 3 ay sonrası olabilir"
            
            # 3. Check business hours (09:00 - 20:00)
            appointment_hour = randevu_tarih_saat.hour
            if appointment_hour < 9 or appointment_hour >= 20:
                return False, "Randevular 09:00-20:00 saatleri arasında alınabilir"
            
            # 4. Check if it's a working day (Monday-Saturday)
            appointment_weekday = randevu_tarih_saat.weekday()
            if appointment_weekday == 6:  # Sunday
                return False, "Pazar günü randevu alınamaz"
            
            # 5. Check dietitian availability
            day_of_week = randevu_tarih_saat.weekday() + 1  # Django uses 1-7
            appointment_time = randevu_tarih_saat.time()
            
            # Check if dietitian has availability for this day and time
            availability_exists = Musaitlik.objects.filter(
                diyetisyen=diyetisyen,
                gun=day_of_week,
                aktif=True,
                baslangic_saati__lte=appointment_time,
                bitis_saati__gt=appointment_time
            ).exists()
            
            if not availability_exists:
                return False, "Diyetisyen bu tarih ve saatte müsait değil"
            
            return True, ""
            
        except Exception as e:
            return False, f"Tarih validasyonu sırasında hata: {str(e)}"
    
    @staticmethod
    def check_appointment_conflicts(randevu_tarih_saat: datetime, diyetisyen: Diyetisyen, 
                                  danisan: Kullanici, exclude_randevu_id: int = None) -> Tuple[bool, str]:
        """
        Check for appointment conflicts
        Returns: (has_conflict, conflict_description)
        """
        try:
            # Calculate appointment time window (1 hour duration)
            appointment_start = randevu_tarih_saat
            appointment_end = randevu_tarih_saat + timedelta(hours=1)
            
            # Base query for conflicting appointments
            conflict_query = Q(
                randevu_tarih_saat__lt=appointment_end,
                randevu_tarih_saat__gte=appointment_start - timedelta(hours=1),
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            )
            
            # Exclude current appointment if updating
            if exclude_randevu_id:
                conflict_query &= ~Q(id=exclude_randevu_id)
            
            # 1. Check dietitian conflicts
            dietitian_conflicts = Randevu.objects.filter(
                conflict_query,
                diyetisyen=diyetisyen
            ).exists()
            
            if dietitian_conflicts:
                return True, "Diyetisyen bu saatte başka bir randevuya sahip"
            
            # 2. Check patient conflicts
            patient_conflicts = Randevu.objects.filter(
                conflict_query,
                danisan=danisan
            ).exists()
            
            if patient_conflicts:
                return True, "Bu saatte başka bir randevunuz bulunmakta"
            
            # 3. Check minimum time between appointments (30 minutes)
            buffer_start = appointment_start - timedelta(minutes=30)
            buffer_end = appointment_end + timedelta(minutes=30)
            
            nearby_appointments = Randevu.objects.filter(
                Q(diyetisyen=diyetisyen) | Q(danisan=danisan),
                randevu_tarih_saat__gte=buffer_start,
                randevu_tarih_saat__lt=buffer_end,
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            )
            
            if exclude_randevu_id:
                nearby_appointments = nearby_appointments.exclude(id=exclude_randevu_id)
            
            if nearby_appointments.exists():
                return True, "Randevular arasında en az 30 dakika boşluk olmalıdır"
            
            return False, ""
            
        except Exception as e:
            return True, f"Çakışma kontrolü sırasında hata: {str(e)}"
    
    @staticmethod
    def validate_appointment_cancellation(randevu: Randevu, cancelling_user: Kullanici) -> Tuple[bool, str]:
        """
        Validate appointment cancellation rules
        Returns: (can_cancel, error_message)
        """
        try:
            # 1. Check if appointment can be cancelled
            if randevu.durum not in ['BEKLEMEDE', 'ONAYLANDI']:
                return False, "Bu randevu iptal edilemez"
            
            # 2. Check cancellation timing (at least 2 hours before appointment)
            time_until_appointment = randevu.randevu_tarih_saat - timezone.now()
            min_cancellation_time = timedelta(hours=2)
            
            if time_until_appointment < min_cancellation_time:
                return False, "Randevu iptal edilmesi için en az 2 saat önceden bildirim gereklidir"
            
            # 3. Check user permissions
            can_cancel = (
                cancelling_user == randevu.danisan or
                cancelling_user == randevu.diyetisyen.kullanici or
                cancelling_user.is_superuser or
                (hasattr(cancelling_user, 'rol') and cancelling_user.rol.rol_adi == 'admin')
            )
            
            if not can_cancel:
                return False, "Bu randevuyu iptal etme yetkiniz yok"
            
            return True, ""
            
        except Exception as e:
            return False, f"İptal validasyonu sırasında hata: {str(e)}"
    
    @staticmethod
    def validate_appointment_modification(randevu: Randevu, new_datetime: datetime, 
                                       modifying_user: Kullanici) -> Tuple[bool, str]:
        """
        Validate appointment modification rules
        Returns: (can_modify, error_message)
        """
        try:
            # 1. Check if appointment can be modified
            if randevu.durum not in ['BEKLEMEDE', 'ONAYLANDI']:
                return False, "Bu randevu değiştirilemez"
            
            # 2. Check modification timing (at least 4 hours before appointment)
            time_until_appointment = randevu.randevu_tarih_saat - timezone.now()
            min_modification_time = timedelta(hours=4)
            
            if time_until_appointment < min_modification_time:
                return False, "Randevu değişikliği için en az 4 saat önceden bildirim gereklidir"
            
            # 3. Check user permissions
            can_modify = (
                modifying_user == randevu.diyetisyen.kullanici or
                modifying_user.is_superuser or
                (hasattr(modifying_user, 'rol') and modifying_user.rol.rol_adi == 'admin')
            )
            
            if not can_modify:
                return False, "Bu randevuyu değiştirme yetkiniz yok"
            
            # 4. Validate new time
            time_valid, time_error = AppointmentValidator.validate_appointment_time(
                new_datetime, randevu.diyetisyen
            )
            if not time_valid:
                return False, f"Yeni randevu saati geçersiz: {time_error}"
            
            # 5. Check for conflicts with new time
            has_conflict, conflict_error = AppointmentValidator.check_appointment_conflicts(
                new_datetime, randevu.diyetisyen, randevu.danisan, randevu.id
            )
            if has_conflict:
                return False, f"Yeni randevu saatinde çakışma: {conflict_error}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Değişiklik validasyonu sırasında hata: {str(e)}"


class BusinessRuleValidator:
    """General business rule validator"""
    
    @staticmethod
    def validate_user_registration(user_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate user registration data
        Returns: (is_valid, error_list)
        """
        errors = []
        
        try:
            # 1. Check email uniqueness
            if Kullanici.objects.filter(e_posta=user_data.get('e_posta')).exists():
                errors.append("Bu e-posta adresi zaten kullanımda")
            
            # 2. Check phone number format (if provided)
            telefon = user_data.get('telefon')
            if telefon and not telefon.isdigit():
                errors.append("Telefon numarası sadece rakam içermelidir")
            
            # 3. Check age requirement (18+)
            # This would require a birth_date field in user_data
            
            # 4. Check name validity
            ad = user_data.get('ad', '').strip()
            soyad = user_data.get('soyad', '').strip()
            
            if len(ad) < 2:
                errors.append("İsim en az 2 karakter olmalıdır")
            if len(soyad) < 2:
                errors.append("Soyisim en az 2 karakter olmalıdır")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            return False, [f"Kayıt validasyonu sırasında hata: {str(e)}"]
    
    @staticmethod
    def validate_dietitian_application(diyetisyen_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate dietitian application data
        Returns: (is_valid, error_list)
        """
        errors = []
        
        try:
            # 1. Check required fields
            required_fields = ['universite', 'hakkinda_bilgi']
            for field in required_fields:
                if not diyetisyen_data.get(field, '').strip():
                    errors.append(f"{field} alanı zorunludur")
            
            # 2. Check university name validity
            universite = diyetisyen_data.get('universite', '').strip()
            if len(universite) < 5:
                errors.append("Üniversite adı en az 5 karakter olmalıdır")
            
            # 3. Check about text length
            hakkinda = diyetisyen_data.get('hakkinda_bilgi', '').strip()
            if len(hakkinda) < 50:
                errors.append("Hakkında bilgisi en az 50 karakter olmalıdır")
            if len(hakkinda) > 1000:
                errors.append("Hakkında bilgisi en fazla 1000 karakter olabilir")
            
            # 4. Check service fee
            hizmet_ucreti = diyetisyen_data.get('hizmet_ucreti', 0)
            if hizmet_ucreti < 0:
                errors.append("Hizmet ücreti negatif olamaz")
            if hizmet_ucreti > 10000:
                errors.append("Hizmet ücreti çok yüksek")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            return False, [f"Diyetisyen başvuru validasyonu sırasında hata: {str(e)}"]
    
    @staticmethod
    def validate_payment_amount(amount: float, expected_amount: float, tolerance: float = 0.01) -> Tuple[bool, str]:
        """
        Validate payment amount
        Returns: (is_valid, error_message)
        """
        try:
            if amount < 0:
                return False, "Ödeme tutarı negatif olamaz"
            
            if abs(amount - expected_amount) > tolerance:
                return False, f"Ödeme tutarı beklenen tutarla eşleşmiyor (Beklenen: {expected_amount}, Alınan: {amount})"
            
            if amount > 50000:  # Maximum payment limit
                return False, "Tek seferde yapılabilecek maksimum ödeme tutarı 50.000 TL'dir"
            
            return True, ""
            
        except Exception as e:
            return False, f"Ödeme validasyonu sırasında hata: {str(e)}"


class ScheduleValidator:
    """Validator for schedule and availability rules"""
    
    @staticmethod
    def validate_availability_schedule(musaitlik_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate dietitian availability schedule
        Returns: (is_valid, error_list)
        """
        errors = []
        
        try:
            gun = musaitlik_data.get('gun')
            baslangic_saati = musaitlik_data.get('baslangic_saati')
            bitis_saati = musaitlik_data.get('bitis_saati')
            
            # 1. Check day validity
            if gun not in range(1, 8):
                errors.append("Geçersiz gün seçimi")
            
            # 2. Check time validity
            if baslangic_saati >= bitis_saati:
                errors.append("Başlangıç saati bitiş saatinden önce olmalıdır")
            
            # 3. Check business hours
            if baslangic_saati.hour < 8 or bitis_saati.hour > 21:
                errors.append("Müsaitlik saatleri 08:00-21:00 arasında olmalıdır")
            
            # 4. Check minimum session duration (30 minutes)
            time_diff = datetime.combine(datetime.today(), bitis_saati) - datetime.combine(datetime.today(), baslangic_saati)
            if time_diff.total_seconds() < 1800:  # 30 minutes
                errors.append("Minimum müsaitlik süresi 30 dakika olmalıdır")
            
            # 5. Check maximum daily hours (12 hours)
            if time_diff.total_seconds() > 43200:  # 12 hours
                errors.append("Günlük maksimum çalışma süresi 12 saat olabilir")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            return False, [f"Müsaitlik validasyonu sırasında hata: {str(e)}"]