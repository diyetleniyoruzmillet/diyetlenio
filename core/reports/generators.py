"""
Report generation classes for different types of reports.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek

from core.models import (
    Kullanici, Diyetisyen, Randevu, OdemeHareketi,
    Bildirim, Sikayet, AnalitikVeri
)


class BaseReportGenerator(ABC):
    """Base class for all report generators."""
    
    def __init__(self, start_date: datetime = None, end_date: datetime = None):
        self.start_date = start_date or (timezone.now() - timedelta(days=30))
        self.end_date = end_date or timezone.now()
        
    @abstractmethod
    def generate_data(self) -> Dict[str, Any]:
        """Generate report data."""
        pass
    
    def get_date_range_filter(self, date_field: str = 'created_at') -> Q:
        """Get date range filter for queries."""
        return Q(**{
            f'{date_field}__gte': self.start_date,
            f'{date_field}__lte': self.end_date
        })


class UserReportGenerator(BaseReportGenerator):
    """Generate user-related reports."""
    
    def generate_data(self) -> Dict[str, Any]:
        """Generate user report data."""
        # Basic user statistics
        total_users = Kullanici.objects.filter(aktif_mi=True).count()
        new_users = Kullanici.objects.filter(
            self.get_date_range_filter('kayit_tarihi')
        ).count()
        
        # User breakdown by role
        user_by_role = Kullanici.objects.filter(
            aktif_mi=True
        ).values('rol__rol_adi').annotate(count=Count('id'))
        
        # New users by day
        new_users_timeline = Kullanici.objects.filter(
            self.get_date_range_filter('kayit_tarihi')
        ).annotate(
            date=TruncDate('kayit_tarihi')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # User activity metrics
        active_users_last_week = Kullanici.objects.filter(
            son_giris_tarihi__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Top referring sources (mock data for now)
        referral_sources = [
            {'source': 'Organik Arama', 'count': 45, 'percentage': 42.1},
            {'source': 'Sosyal Medya', 'count': 32, 'percentage': 29.9},
            {'source': 'Direkt Erişim', 'count': 18, 'percentage': 16.8},
            {'source': 'Referans', 'count': 12, 'percentage': 11.2}
        ]
        
        return {
            'summary': {
                'total_users': total_users,
                'new_users': new_users,
                'active_users_last_week': active_users_last_week,
                'growth_rate': self._calculate_growth_rate('user')
            },
            'user_by_role': list(user_by_role),
            'new_users_timeline': list(new_users_timeline),
            'referral_sources': referral_sources,
            'date_range': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat()
            }
        }
    
    def _calculate_growth_rate(self, metric_type: str) -> float:
        """Calculate growth rate compared to previous period."""
        period_length = (self.end_date - self.start_date).days
        previous_start = self.start_date - timedelta(days=period_length)
        
        current_count = Kullanici.objects.filter(
            kayit_tarihi__gte=self.start_date,
            kayit_tarihi__lte=self.end_date
        ).count()
        
        previous_count = Kullanici.objects.filter(
            kayit_tarihi__gte=previous_start,
            kayit_tarihi__lt=self.start_date
        ).count()
        
        if previous_count == 0:
            return 100.0 if current_count > 0 else 0.0
        
        return round(((current_count - previous_count) / previous_count) * 100, 1)


class AppointmentReportGenerator(BaseReportGenerator):
    """Generate appointment-related reports."""
    
    def generate_data(self) -> Dict[str, Any]:
        """Generate appointment report data."""
        # Basic appointment statistics
        total_appointments = Randevu.objects.filter(
            self.get_date_range_filter('randevu_tarih_saat')
        ).count()
        
        completed_appointments = Randevu.objects.filter(
            self.get_date_range_filter('randevu_tarih_saat'),
            durum='TAMAMLANDI'
        ).count()
        
        cancelled_appointments = Randevu.objects.filter(
            self.get_date_range_filter('randevu_tarih_saat'),
            durum='IPTAL_EDILDI'
        ).count()
        
        # Success rate
        success_rate = 0
        if total_appointments > 0:
            success_rate = round((completed_appointments / total_appointments) * 100, 1)
        
        # Appointments by status
        appointments_by_status = Randevu.objects.filter(
            self.get_date_range_filter('randevu_tarih_saat')
        ).values('durum').annotate(count=Count('id'))
        
        # Appointments by type
        appointments_by_type = Randevu.objects.filter(
            self.get_date_range_filter('randevu_tarih_saat')
        ).values('tip').annotate(count=Count('id'))
        
        # Daily appointment trend
        daily_appointments = Randevu.objects.filter(
            self.get_date_range_filter('randevu_tarih_saat')
        ).annotate(
            date=TruncDate('randevu_tarih_saat')
        ).values('date').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(durum='TAMAMLANDI')),
            cancelled=Count('id', filter=Q(durum='IPTAL_EDILDI'))
        ).order_by('date')
        
        # Top performing dietitians
        top_dietitians = Randevu.objects.filter(
            self.get_date_range_filter('randevu_tarih_saat'),
            durum='TAMAMLANDI'
        ).values(
            'diyetisyen__kullanici__ad',
            'diyetisyen__kullanici__soyad'
        ).annotate(
            total_appointments=Count('id'),
            avg_rating=Avg('yorum__puan')
        ).order_by('-total_appointments')[:10]
        
        # Peak hours analysis
        peak_hours = Randevu.objects.filter(
            self.get_date_range_filter('randevu_tarih_saat')
        ).extra(
            select={'hour': 'EXTRACT(hour FROM randevu_tarih_saat)'}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        return {
            'summary': {
                'total_appointments': total_appointments,
                'completed_appointments': completed_appointments,
                'cancelled_appointments': cancelled_appointments,
                'success_rate': success_rate,
                'growth_rate': self._calculate_appointment_growth_rate()
            },
            'appointments_by_status': list(appointments_by_status),
            'appointments_by_type': list(appointments_by_type),
            'daily_trend': list(daily_appointments),
            'top_dietitians': list(top_dietitians),
            'peak_hours': list(peak_hours),
            'date_range': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat()
            }
        }
    
    def _calculate_appointment_growth_rate(self) -> float:
        """Calculate appointment growth rate."""
        period_length = (self.end_date - self.start_date).days
        previous_start = self.start_date - timedelta(days=period_length)
        
        current_count = Randevu.objects.filter(
            randevu_tarih_saat__gte=self.start_date,
            randevu_tarih_saat__lte=self.end_date
        ).count()
        
        previous_count = Randevu.objects.filter(
            randevu_tarih_saat__gte=previous_start,
            randevu_tarih_saat__lt=self.start_date
        ).count()
        
        if previous_count == 0:
            return 100.0 if current_count > 0 else 0.0
        
        return round(((current_count - previous_count) / previous_count) * 100, 1)


class RevenueReportGenerator(BaseReportGenerator):
    """Generate revenue and financial reports."""
    
    def generate_data(self) -> Dict[str, Any]:
        """Generate revenue report data."""
        # Basic revenue statistics
        total_revenue = OdemeHareketi.objects.filter(
            self.get_date_range_filter('odeme_tarihi'),
            odeme_durumu='TAMAMLANDI'
        ).aggregate(total=Sum('toplam_ucret'))['total'] or 0
        
        total_commission = OdemeHareketi.objects.filter(
            self.get_date_range_filter('odeme_tarihi'),
            odeme_durumu='TAMAMLANDI'
        ).aggregate(total=Sum('komisyon_miktari'))['total'] or 0
        
        total_transactions = OdemeHareketi.objects.filter(
            self.get_date_range_filter('odeme_tarihi'),
            odeme_durumu='TAMAMLANDI'
        ).count()
        
        # Average transaction value
        avg_transaction = 0
        if total_transactions > 0:
            avg_transaction = float(total_revenue) / total_transactions
        
        # Revenue by day
        daily_revenue = OdemeHareketi.objects.filter(
            self.get_date_range_filter('odeme_tarihi'),
            odeme_durumu='TAMAMLANDI'
        ).annotate(
            date=TruncDate('odeme_tarihi')
        ).values('date').annotate(
            revenue=Sum('toplam_ucret'),
            transactions=Count('id')
        ).order_by('date')
        
        # Revenue by payment status
        revenue_by_status = OdemeHareketi.objects.filter(
            self.get_date_range_filter('odeme_tarihi')
        ).values('odeme_durumu').annotate(
            revenue=Sum('toplam_ucret'),
            count=Count('id')
        )
        
        # Top earning dietitians
        top_earners = OdemeHareketi.objects.filter(
            self.get_date_range_filter('odeme_tarihi'),
            odeme_durumu='TAMAMLANDI'
        ).values(
            'diyetisyen__kullanici__ad',
            'diyetisyen__kullanici__soyad'
        ).annotate(
            total_earnings=Sum('diyetisyen_kazanci'),
            transaction_count=Count('id')
        ).order_by('-total_earnings')[:10]
        
        # Monthly revenue trend
        monthly_revenue = OdemeHareketi.objects.filter(
            odeme_tarihi__gte=self.start_date - timedelta(days=365),
            odeme_durumu='TAMAMLANDI'
        ).annotate(
            month=TruncMonth('odeme_tarihi')
        ).values('month').annotate(
            revenue=Sum('toplam_ucret'),
            transactions=Count('id')
        ).order_by('month')
        
        return {
            'summary': {
                'total_revenue': float(total_revenue),
                'total_commission': float(total_commission),
                'total_transactions': total_transactions,
                'avg_transaction': round(avg_transaction, 2),
                'growth_rate': self._calculate_revenue_growth_rate()
            },
            'daily_revenue': list(daily_revenue),
            'revenue_by_status': list(revenue_by_status),
            'top_earners': list(top_earners),
            'monthly_trend': list(monthly_revenue),
            'commission_analysis': {
                'total_commission': float(total_commission),
                'commission_rate': round((float(total_commission) / float(total_revenue)) * 100, 2) if total_revenue > 0 else 0,
                'avg_commission_per_transaction': round(float(total_commission) / total_transactions, 2) if total_transactions > 0 else 0
            },
            'date_range': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat()
            }
        }
    
    def _calculate_revenue_growth_rate(self) -> float:
        """Calculate revenue growth rate."""
        period_length = (self.end_date - self.start_date).days
        previous_start = self.start_date - timedelta(days=period_length)
        
        current_revenue = OdemeHareketi.objects.filter(
            odeme_tarihi__gte=self.start_date,
            odeme_tarihi__lte=self.end_date,
            odeme_durumu='TAMAMLANDI'
        ).aggregate(total=Sum('toplam_ucret'))['total'] or 0
        
        previous_revenue = OdemeHareketi.objects.filter(
            odeme_tarihi__gte=previous_start,
            odeme_tarihi__lt=self.start_date,
            odeme_durumu='TAMAMLANDI'
        ).aggregate(total=Sum('toplam_ucret'))['total'] or 0
        
        if previous_revenue == 0:
            return 100.0 if current_revenue > 0 else 0.0
        
        return round(((float(current_revenue) - float(previous_revenue)) / float(previous_revenue)) * 100, 1)


class SystemReportGenerator(BaseReportGenerator):
    """Generate system performance and health reports."""
    
    def generate_data(self) -> Dict[str, Any]:
        """Generate system report data."""
        # System health metrics
        from core.monitoring import metrics_collector
        system_health = metrics_collector.get_health_metrics()
        
        # API performance metrics
        api_metrics = metrics_collector.get_metrics_summary(1440)  # Last 24 hours
        
        # Error analysis
        error_analysis = self._get_error_analysis()
        
        # System utilization trends (mock data)
        utilization_trends = self._get_utilization_trends()
        
        return {
            'system_health': system_health,
            'api_performance': {
                'total_requests': api_metrics.get('total_requests', 0),
                'error_rate': api_metrics.get('error_rate', 0),
                'average_response_time': api_metrics.get('average_response_time', 0),
                'requests_per_minute': api_metrics.get('requests_per_minute', 0)
            },
            'error_analysis': error_analysis,
            'utilization_trends': utilization_trends,
            'alerts_summary': self._get_alerts_summary(),
            'date_range': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat()
            }
        }
    
    def _get_error_analysis(self) -> Dict[str, Any]:
        """Get error analysis data."""
        # This would typically integrate with your logging system
        return {
            'total_errors': 45,
            'error_types': [
                {'type': '500_errors', 'count': 20, 'percentage': 44.4},
                {'type': '404_errors', 'count': 15, 'percentage': 33.3},
                {'type': '403_errors', 'count': 10, 'percentage': 22.2}
            ],
            'error_trend': [
                {'date': '2024-01-01', 'count': 5},
                {'date': '2024-01-02', 'count': 3},
                {'date': '2024-01-03', 'count': 8},
            ]
        }
    
    def _get_utilization_trends(self) -> Dict[str, List]:
        """Get system utilization trends."""
        return {
            'cpu_usage': [45, 52, 38, 61, 49, 55, 42],
            'memory_usage': [72, 68, 75, 71, 69, 73, 70],
            'disk_usage': [35, 35, 36, 36, 37, 37, 38],
            'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        }
    
    def _get_alerts_summary(self) -> Dict[str, Any]:
        """Get alerts summary."""
        return {
            'total_alerts': 12,
            'critical_alerts': 2,
            'warning_alerts': 7,
            'info_alerts': 3,
            'resolved_alerts': 8
        }


class ComprehensiveReportGenerator:
    """Generate comprehensive reports combining multiple report types."""
    
    def __init__(self, start_date: datetime = None, end_date: datetime = None):
        self.start_date = start_date or (timezone.now() - timedelta(days=30))
        self.end_date = end_date or timezone.now()
    
    def generate_executive_summary(self) -> Dict[str, Any]:
        """Generate executive summary report."""
        user_generator = UserReportGenerator(self.start_date, self.end_date)
        appointment_generator = AppointmentReportGenerator(self.start_date, self.end_date)
        revenue_generator = RevenueReportGenerator(self.start_date, self.end_date)
        system_generator = SystemReportGenerator(self.start_date, self.end_date)
        
        user_data = user_generator.generate_data()
        appointment_data = appointment_generator.generate_data()
        revenue_data = revenue_generator.generate_data()
        system_data = system_generator.generate_data()
        
        return {
            'report_type': 'executive_summary',
            'generated_at': timezone.now().isoformat(),
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'days': (self.end_date - self.start_date).days
            },
            'key_metrics': {
                'users': user_data['summary'],
                'appointments': appointment_data['summary'],
                'revenue': revenue_data['summary'],
                'system_health': system_data['system_health']
            },
            'detailed_data': {
                'users': user_data,
                'appointments': appointment_data,
                'revenue': revenue_data,
                'system': system_data
            }
        }
    
    def generate_custom_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate custom report based on configuration."""
        report_data = {
            'report_type': 'custom',
            'config': report_config,
            'generated_at': timezone.now().isoformat()
        }
        
        if report_config.get('include_users', True):
            user_generator = UserReportGenerator(self.start_date, self.end_date)
            report_data['users'] = user_generator.generate_data()
        
        if report_config.get('include_appointments', True):
            appointment_generator = AppointmentReportGenerator(self.start_date, self.end_date)
            report_data['appointments'] = appointment_generator.generate_data()
        
        if report_config.get('include_revenue', True):
            revenue_generator = RevenueReportGenerator(self.start_date, self.end_date)
            report_data['revenue'] = revenue_generator.generate_data()
        
        if report_config.get('include_system', False):
            system_generator = SystemReportGenerator(self.start_date, self.end_date)
            report_data['system'] = system_generator.generate_data()
        
        return report_data