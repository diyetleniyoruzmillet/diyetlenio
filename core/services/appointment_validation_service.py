"""
Appointment validation service with comprehensive business rules
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache

from .base_service import BaseService, ServiceResult
from ..models import Randevu, Diyetisyen, Kullanici, Musaitlik, DiyetisyenIzin
from ..validators import AppointmentValidator


class AppointmentValidationService(BaseService):
    """Service for comprehensive appointment validation"""
    
    def validate_new_appointment(self, data: Dict) -> ServiceResult:
        """
        Comprehensive validation for new appointment
        """
        try:
            # Extract data
            diyetisyen_id = data.get('diyetisyen_id')
            danisan_id = data.get('danisan_id')
            randevu_tarih_saat = data.get('randevu_tarih_saat')
            
            # Get objects
            try:
                diyetisyen = Diyetisyen.objects.select_related('kullanici').get(
                    id=diyetisyen_id, 
                    kullanici__aktif_mi=True
                )
                danisan = Kullanici.objects.get(id=danisan_id, aktif_mi=True)
            except (Diyetisyen.DoesNotExist, Kullanici.DoesNotExist):
                return ServiceResult.error_result("Diyetisyen veya danışan bulunamadı")
            
            # Parse datetime if string
            if isinstance(randevu_tarih_saat, str):
                try:
                    randevu_tarih_saat = datetime.fromisoformat(randevu_tarih_saat.replace('Z', '+00:00'))
                except ValueError:
                    return ServiceResult.error_result("Geçersiz tarih formatı")
            
            # Validation chain
            validation_results = []
            
            # 1. Basic time validation
            time_valid, time_error = AppointmentValidator.validate_appointment_time(
                randevu_tarih_saat, diyetisyen
            )
            if not time_valid:
                validation_results.append(time_error)
            
            # 2. Conflict check
            has_conflict, conflict_error = AppointmentValidator.check_appointment_conflicts(
                randevu_tarih_saat, diyetisyen, danisan
            )
            if has_conflict:
                validation_results.append(conflict_error)
            
            # 3. Check dietitian vacation/leave
            is_on_leave, leave_error = self._check_dietitian_leave(
                diyetisyen, randevu_tarih_saat
            )
            if is_on_leave:
                validation_results.append(leave_error)
            
            # 4. Check appointment frequency limits
            freq_valid, freq_error = self._check_appointment_frequency(
                danisan, randevu_tarih_saat
            )
            if not freq_valid:
                validation_results.append(freq_error)
            
            # 5. Check dietitian capacity
            capacity_valid, capacity_error = self._check_dietitian_capacity(
                diyetisyen, randevu_tarih_saat
            )
            if not capacity_valid:
                validation_results.append(capacity_error)
            
            if validation_results:
                return ServiceResult.error_result({
                    'errors': validation_results,
                    'is_valid': False
                })
            
            # All validations passed
            self.log_operation("Appointment validation passed",
                             diyetisyen_id=diyetisyen_id,
                             danisan_id=danisan_id,
                             appointment_time=randevu_tarih_saat.isoformat())
            
            return ServiceResult.success_result({
                'is_valid': True,
                'validated_data': {
                    'diyetisyen': diyetisyen,
                    'danisan': danisan,
                    'randevu_tarih_saat': randevu_tarih_saat
                }
            })
            
        except Exception as e:
            self.log_error("Appointment validation", e)
            return ServiceResult.error_result(f"Randevu validasyonu sırasında hata: {str(e)}")
    
    def validate_appointment_modification(self, randevu_id: int, new_data: Dict) -> ServiceResult:
        """
        Validate appointment modification request
        """
        try:
            # Get existing appointment
            try:
                randevu = Randevu.objects.select_related('diyetisyen__kullanici', 'danisan').get(
                    id=randevu_id
                )
            except Randevu.DoesNotExist:
                return ServiceResult.error_result("Randevu bulunamadı")
            
            new_datetime = new_data.get('randevu_tarih_saat')
            modifying_user_id = new_data.get('modifying_user_id')
            
            try:
                modifying_user = Kullanici.objects.get(id=modifying_user_id)
            except Kullanici.DoesNotExist:
                return ServiceResult.error_result("Değiştiren kullanıcı bulunamadı")
            
            # Parse datetime if string
            if isinstance(new_datetime, str):
                try:
                    new_datetime = datetime.fromisoformat(new_datetime.replace('Z', '+00:00'))
                except ValueError:
                    return ServiceResult.error_result("Geçersiz tarih formatı")
            
            # Validate modification
            can_modify, modify_error = AppointmentValidator.validate_appointment_modification(
                randevu, new_datetime, modifying_user
            )
            
            if not can_modify:
                return ServiceResult.error_result(modify_error)
            
            # Additional validations for new time
            validation_errors = []
            
            # Check dietitian leave for new time
            is_on_leave, leave_error = self._check_dietitian_leave(
                randevu.diyetisyen, new_datetime
            )
            if is_on_leave:
                validation_errors.append(leave_error)
            
            # Check capacity for new time
            capacity_valid, capacity_error = self._check_dietitian_capacity(
                randevu.diyetisyen, new_datetime, exclude_randevu_id=randevu_id
            )
            if not capacity_valid:
                validation_errors.append(capacity_error)
            
            if validation_errors:
                return ServiceResult.error_result({
                    'errors': validation_errors,
                    'is_valid': False
                })
            
            self.log_operation("Appointment modification validation passed",
                             randevu_id=randevu_id,
                             old_time=randevu.randevu_tarih_saat.isoformat(),
                             new_time=new_datetime.isoformat())
            
            return ServiceResult.success_result({
                'is_valid': True,
                'randevu': randevu,
                'new_datetime': new_datetime
            })
            
        except Exception as e:
            self.log_error("Appointment modification validation", e)
            return ServiceResult.error_result(f"Randevu değişiklik validasyonu sırasında hata: {str(e)}")
    
    def validate_appointment_cancellation(self, randevu_id: int, cancelling_user_id: int, 
                                        reason: str = None) -> ServiceResult:
        """
        Validate appointment cancellation request
        """
        try:
            # Get appointment and user
            try:
                randevu = Randevu.objects.select_related('diyetisyen__kullanici', 'danisan').get(
                    id=randevu_id
                )
                cancelling_user = Kullanici.objects.get(id=cancelling_user_id)
            except (Randevu.DoesNotExist, Kullanici.DoesNotExist):
                return ServiceResult.error_result("Randevu veya kullanıcı bulunamadı")
            
            # Validate cancellation
            can_cancel, cancel_error = AppointmentValidator.validate_appointment_cancellation(
                randevu, cancelling_user
            )
            
            if not can_cancel:
                return ServiceResult.error_result(cancel_error)
            
            # Check cancellation frequency (prevent abuse)
            freq_valid, freq_error = self._check_cancellation_frequency(
                cancelling_user, randevu
            )
            if not freq_valid:
                return ServiceResult.error_result(freq_error)
            
            self.log_operation("Appointment cancellation validation passed",
                             randevu_id=randevu_id,
                             cancelling_user_id=cancelling_user_id,
                             reason=reason)
            
            return ServiceResult.success_result({
                'is_valid': True,
                'randevu': randevu,
                'cancelling_user': cancelling_user,
                'reason': reason
            })
            
        except Exception as e:
            self.log_error("Appointment cancellation validation", e)
            return ServiceResult.error_result(f"Randevu iptal validasyonu sırasında hata: {str(e)}")
    
    def get_available_slots(self, diyetisyen_id: int, date: datetime.date) -> ServiceResult:
        """
        Get available appointment slots for a specific dietitian and date
        """
        try:
            # Get dietitian
            try:
                diyetisyen = Diyetisyen.objects.select_related('kullanici').get(
                    id=diyetisyen_id, 
                    kullanici__aktif_mi=True
                )
            except Diyetisyen.DoesNotExist:
                return ServiceResult.error_result("Diyetisyen bulunamadı")
            
            # Check if date is valid
            if date <= timezone.now().date():
                return ServiceResult.error_result("Geçmiş tarih için randevu alınamaz")
            
            # Get day of week (Django uses 1-7, Monday-Sunday)
            day_of_week = date.weekday() + 1
            
            # Get dietitian's availability for this day
            availabilities = Musaitlik.objects.filter(
                diyetisyen=diyetisyen,
                gun=day_of_week,
                aktif=True
            ).order_by('baslangic_saati')
            
            if not availabilities.exists():
                return ServiceResult.success_result({
                    'available_slots': [],
                    'message': 'Diyetisyen bu gün müsait değil'
                })
            
            # Check if dietitian is on leave
            is_on_leave = DiyetisyenIzin.objects.filter(
                diyetisyen=diyetisyen,
                baslangic_tarihi__lte=date,
                bitis_tarihi__gte=date
            ).exists()
            
            if is_on_leave:
                return ServiceResult.success_result({
                    'available_slots': [],
                    'message': 'Diyetisyen bu tarihte izinli'
                })
            
            # Get existing appointments for this date
            existing_appointments = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                randevu_tarih_saat__date=date,
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            ).values_list('randevu_tarih_saat__time', flat=True)
            
            # Generate available slots
            available_slots = []
            for availability in availabilities:
                current_time = availability.baslangic_saati
                end_time = availability.bitis_saati
                
                while current_time < end_time:
                    # Check if this slot is available
                    if current_time not in existing_appointments:
                        slot_datetime = timezone.make_aware(
                            datetime.combine(date, current_time)
                        )
                        
                        # Additional validation for the slot
                        time_valid, _ = AppointmentValidator.validate_appointment_time(
                            slot_datetime, diyetisyen
                        )
                        
                        if time_valid:
                            available_slots.append({
                                'time': current_time.strftime('%H:%M'),
                                'datetime': slot_datetime.isoformat(),
                                'available': True
                            })
                    
                    # Move to next 30-minute slot
                    current_time = (
                        datetime.combine(datetime.today(), current_time) + 
                        timedelta(minutes=30)
                    ).time()
            
            self.log_operation("Available slots retrieved",
                             diyetisyen_id=diyetisyen_id,
                             date=date.isoformat(),
                             slots_count=len(available_slots))
            
            return ServiceResult.success_result({
                'available_slots': available_slots,
                'date': date.isoformat(),
                'diyetisyen': {
                    'id': diyetisyen.id,
                    'name': f"{diyetisyen.kullanici.ad} {diyetisyen.kullanici.soyad}"
                }
            })
            
        except Exception as e:
            self.log_error("Get available slots", e)
            return ServiceResult.error_result(f"Müsait saatler alınırken hata: {str(e)}")
    
    def _check_dietitian_leave(self, diyetisyen: Diyetisyen, appointment_datetime: datetime) -> Tuple[bool, str]:
        """Check if dietitian is on leave during appointment time"""
        try:
            appointment_date = appointment_datetime.date()
            appointment_time = appointment_datetime.time()
            
            # Check for any leave that covers this date
            leaves = DiyetisyenIzin.objects.filter(
                diyetisyen=diyetisyen,
                baslangic_tarihi__lte=appointment_date,
                bitis_tarihi__gte=appointment_date
            )
            
            for leave in leaves:
                if leave.izin_tipi == 'TAM_GUN':
                    return True, f"Diyetisyen {appointment_date} tarihinde tam gün izinli"
                elif leave.izin_tipi == 'SAATLIK':
                    if (leave.baslangic_saati and leave.bitis_saati and
                        leave.baslangic_saati <= appointment_time <= leave.bitis_saati):
                        return True, f"Diyetisyen {appointment_time} saatinde izinli"
            
            return False, ""
            
        except Exception:
            return True, "İzin kontrolü sırasında hata oluştu"
    
    def _check_appointment_frequency(self, danisan: Kullanici, appointment_datetime: datetime) -> Tuple[bool, str]:
        """Check appointment frequency limits for patient"""
        try:
            # Check daily limit (max 3 appointments per day)
            appointment_date = appointment_datetime.date()
            daily_count = Randevu.objects.filter(
                danisan=danisan,
                randevu_tarih_saat__date=appointment_date,
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            ).count()
            
            if daily_count >= 3:
                return False, "Günde en fazla 3 randevu alabilirsiniz"
            
            # Check weekly limit (max 7 appointments per week)
            week_start = appointment_date - timedelta(days=appointment_date.weekday())
            week_end = week_start + timedelta(days=6)
            
            weekly_count = Randevu.objects.filter(
                danisan=danisan,
                randevu_tarih_saat__date__gte=week_start,
                randevu_tarih_saat__date__lte=week_end,
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            ).count()
            
            if weekly_count >= 7:
                return False, "Haftada en fazla 7 randevu alabilirsiniz"
            
            return True, ""
            
        except Exception:
            return False, "Randevu sıklığı kontrolü sırasında hata oluştu"
    
    def _check_dietitian_capacity(self, diyetisyen: Diyetisyen, appointment_datetime: datetime, 
                                 exclude_randevu_id: int = None) -> Tuple[bool, str]:
        """Check dietitian's daily capacity"""
        try:
            appointment_date = appointment_datetime.date()
            
            # Get daily appointment count
            daily_appointments = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                randevu_tarih_saat__date=appointment_date,
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            )
            
            if exclude_randevu_id:
                daily_appointments = daily_appointments.exclude(id=exclude_randevu_id)
            
            daily_count = daily_appointments.count()
            
            # Check daily limit (max 12 appointments per day)
            if daily_count >= 12:
                return False, "Diyetisyen günlük kapasite limitine ulaştı"
            
            return True, ""
            
        except Exception:
            return False, "Kapasite kontrolü sırasında hata oluştu"
    
    def _check_cancellation_frequency(self, user: Kullanici, randevu: Randevu) -> Tuple[bool, str]:
        """Check cancellation frequency to prevent abuse"""
        try:
            # Check cancellations in last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)
            
            recent_cancellations = Randevu.objects.filter(
                Q(danisan=user) | Q(diyetisyen__kullanici=user),
                durum='IPTAL_EDILDI',
                iptal_edilme_tarihi__gte=thirty_days_ago
            ).count()
            
            # Allow max 5 cancellations per month
            if recent_cancellations >= 5:
                return False, "Son 30 günde çok fazla randevu iptal ettiniz"
            
            return True, ""
            
        except Exception:
            return False, "İptal sıklığı kontrolü sırasında hata oluştu"