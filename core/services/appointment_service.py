"""
Appointment business logic service.
"""
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .base_service import BaseService, ServiceResult
from core.models import Randevu, Diyetisyen, Kullanici, Musaitlik, DanisanDiyetisyenEslesme


class AppointmentService(BaseService):
    """Service for appointment-related business operations."""
    
    def create_appointment(self, data: Dict) -> ServiceResult:
        """Create a new appointment."""
        required_fields = ['diyetisyen_id', 'danisan_id', 'randevu_tarih_saat', 'tip']
        validation = self.validate_input(data, required_fields)
        
        if not validation:
            return validation
        
        try:
            # Check if dietitian exists and is active
            diyetisyen = Diyetisyen.objects.select_related('kullanici').get(
                id=data['diyetisyen_id'],
                kullanici__aktif_mi=True
            )
            
            # Check if client exists and is active
            danisan = Kullanici.objects.get(
                id=data['danisan_id'],
                aktif_mi=True,
                rol__rol_adi='danisan'
            )
            
            # Check availability
            availability_check = self.check_availability(
                diyetisyen, 
                data['randevu_tarih_saat']
            )
            
            if not availability_check:
                return availability_check
            
            # Create appointment
            randevu = self.execute_with_transaction(
                self._create_appointment_transaction,
                diyetisyen, danisan, data
            )
            
            self.log_operation("Appointment created", 
                             randevu_id=randevu.id,
                             diyetisyen_id=diyetisyen.id,
                             danisan_id=danisan.id)
            
            return ServiceResult.success_result(randevu)
            
        except Diyetisyen.DoesNotExist:
            return ServiceResult.error_result("Diyetisyen bulunamadı veya aktif değil")
        except Kullanici.DoesNotExist:
            return ServiceResult.error_result("Danışan bulunamadı veya aktif değil")
        except Exception as e:
            self.log_error("Create appointment", e)
            return ServiceResult.error_result(f"Randevu oluşturulurken hata oluştu: {str(e)}")
    
    def _create_appointment_transaction(self, diyetisyen, danisan, data):
        """Create appointment within transaction."""
        randevu = Randevu.objects.create(
            diyetisyen=diyetisyen,
            danisan=danisan,
            randevu_tarih_saat=data['randevu_tarih_saat'],
            durum='BEKLEMEDE',
            tip=data['tip'],
            ucret_tutar=data.get('ucret_tutar', diyetisyen.hizmet_ucreti)
        )
        
        # Create client-dietitian matching if it's first appointment
        if data['tip'] == 'ON_GORUSME':
            DanisanDiyetisyenEslesme.objects.get_or_create(
                diyetisyen=diyetisyen,
                danisan=danisan,
                defaults={'on_gorusme_yapildi_mi': False}
            )
        
        return randevu
    
    def check_availability(self, diyetisyen: Diyetisyen, appointment_datetime: datetime) -> ServiceResult:
        """Check if dietitian is available at given time."""
        try:
            # Check if time slot is already booked
            existing_appointment = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                randevu_tarih_saat=appointment_datetime,
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            ).exists()
            
            if existing_appointment:
                return ServiceResult.error_result("Bu saat dilimine başka randevu var")
            
            # Check dietitian's availability schedule
            weekday = appointment_datetime.weekday() + 1  # Django uses 1-7
            appointment_time = appointment_datetime.time()
            
            availability = Musaitlik.objects.filter(
                diyetisyen=diyetisyen,
                gun=weekday,
                baslangic_saati__lte=appointment_time,
                bitis_saati__gt=appointment_time
            ).exists()
            
            if not availability:
                return ServiceResult.error_result("Diyetisyen bu saatte müsait değil")
            
            return ServiceResult.success_result()
            
        except Exception as e:
            self.log_error("Check availability", e)
            return ServiceResult.error_result("Müsaitlik kontrolü yapılırken hata oluştu")
    
    def cancel_appointment(self, randevu_id: int, cancelled_by: Kullanici, reason: str) -> ServiceResult:
        """Cancel an existing appointment."""
        try:
            randevu = Randevu.objects.select_related(
                'diyetisyen__kullanici', 'danisan'
            ).get(id=randevu_id)
            
            # Check if appointment can be cancelled
            if randevu.durum not in ['BEKLEMEDE', 'ONAYLANDI']:
                return ServiceResult.error_result("Bu randevu iptal edilemez")
            
            # Determine who is cancelling
            if cancelled_by == randevu.danisan:
                iptal_eden_tur = 'danisan'
            elif cancelled_by == randevu.diyetisyen.kullanici:
                iptal_eden_tur = 'diyetisyen'
            else:
                iptal_eden_tur = 'admin'
            
            # Cancel appointment
            randevu.durum = 'IPTAL_EDILDI'
            randevu.iptal_eden_tur = iptal_eden_tur
            randevu.iptal_edilme_tarihi = timezone.now()
            randevu.iptal_nedeni = reason
            randevu.save()
            
            self.log_operation("Appointment cancelled", 
                             randevu_id=randevu.id,
                             cancelled_by=cancelled_by.id,
                             reason=reason)
            
            return ServiceResult.success_result(randevu)
            
        except Randevu.DoesNotExist:
            return ServiceResult.error_result("Randevu bulunamadı")
        except Exception as e:
            self.log_error("Cancel appointment", e)
            return ServiceResult.error_result(f"Randevu iptal edilirken hata oluştu: {str(e)}")
    
    def get_available_slots(self, diyetisyen_id: int, date_from: datetime, date_to: datetime) -> ServiceResult:
        """Get available appointment slots for a dietitian."""
        try:
            diyetisyen = Diyetisyen.objects.get(kullanici_id=diyetisyen_id)
            
            # Get dietitian's availability
            availabilities = Musaitlik.objects.filter(
                diyetisyen=diyetisyen
            ).values('gun', 'baslangic_saati', 'bitis_saati')
            
            # Get existing appointments
            existing_appointments = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                randevu_tarih_saat__date__range=[date_from.date(), date_to.date()],
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            ).values_list('randevu_tarih_saat', flat=True)
            
            available_slots = []
            current_date = date_from.date()
            
            while current_date <= date_to.date():
                weekday = current_date.weekday() + 1
                
                # Find availability for this weekday
                day_availabilities = [av for av in availabilities if av['gun'] == weekday]
                
                for availability in day_availabilities:
                    # Generate hourly slots
                    current_time = datetime.combine(current_date, availability['baslangic_saati'])
                    end_time = datetime.combine(current_date, availability['bitis_saati'])
                    
                    while current_time < end_time:
                        if current_time not in existing_appointments and current_time > timezone.now():
                            available_slots.append(current_time)
                        current_time += timedelta(hours=1)
                
                current_date += timedelta(days=1)
            
            return ServiceResult.success_result(available_slots)
            
        except Diyetisyen.DoesNotExist:
            return ServiceResult.error_result("Diyetisyen bulunamadı")
        except Exception as e:
            self.log_error("Get available slots", e)
            return ServiceResult.error_result("Müsait saatler alınırken hata oluştu")