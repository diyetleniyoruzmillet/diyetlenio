"""
Admin-specific API endpoints.
"""
from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, serializers
from datetime import datetime, timedelta
from collections import defaultdict
from drf_spectacular.utils import extend_schema

from core.services.auth_service import AuthService
from core.services.user_service import UserService
from core.services.randevu_service import RandevuService
from core.models import (
    Kullanici, Diyetisyen, Randevu, OdemeHareketi,
    Bildirim, Sikayet, AnalitikVeri
)
from core.monitoring import metrics_collector

# Placeholder serializers - these need to be created
class DiyetisyenApprovalSerializer(serializers.Serializer):
    pass

class DiyetisyenRejectionSerializer(serializers.Serializer):
    pass

class RandevuReassignSerializer(serializers.Serializer):
    yeni_diyetisyen_id = serializers.IntegerField()

class UserDeactivationSerializer(serializers.Serializer):
    neden = serializers.CharField()

class AdminStatsSerializer(serializers.Serializer):
    pass

class DiyetisyenDetailWithApplicationSerializer(serializers.Serializer):
    pass


@extend_schema(
    summary="Admin Dashboard İstatistikleri",
    description="Admin dashboard için genel istatistikleri döner"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_stats(request):
    """Get admin dashboard statistics."""
    if not AuthService.is_admin(request.user):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        # Date ranges
        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = this_month_start - timedelta(days=1)

        # Basic counts
        total_users = Kullanici.objects.filter(aktif_mi=True).count()
        total_dietitians = Diyetisyen.objects.filter(
            kullanici__aktif_mi=True
        ).count()
        
        # Monthly appointments
        total_appointments = Randevu.objects.filter(
            randevu_tarih_saat__date__gte=this_month_start,
            durum__in=['TAMAMLANDI', 'ONAYLANDI']
        ).count()
        
        # Monthly revenue
        total_revenue = OdemeHareketi.objects.filter(
            odeme_tarihi__date__gte=this_month_start,
            odeme_durumu='TAMAMLANDI'
        ).aggregate(total=Sum('toplam_ucret'))['total'] or 0

        # Get user timeline data (last 30 days)
        timeline_data = []
        timeline_labels = []
        
        for i in range(30):
            date = today - timedelta(days=29-i)
            user_count = Kullanici.objects.filter(
                kayit_tarihi__date=date
            ).count()
            timeline_data.append(user_count)
            timeline_labels.append(date.strftime('%d/%m'))

        # API metrics from monitoring
        api_metrics_data = metrics_collector.get_metrics_summary(60)  # Last hour
        
        response_data = {
            'total_users': total_users,
            'total_dietitians': total_dietitians,
            'total_appointments': total_appointments,
            'total_revenue': float(total_revenue),
            
            # Timeline data
            'users_timeline': {
                'labels': timeline_labels,
                'data': timeline_data
            },
            
            # API metrics
            'api_metrics': [
                api_metrics_data.get('average_response_time', 0) * 1000,  # Convert to ms
                250, 180, 90  # Mock data for POST, PUT, DELETE
            ]
        }

        return Response({
            'success': True,
            'data': response_data
        })

    except Exception as e:
        return Response({
            'error': f'Error getting admin stats: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Son Aktiviteler",
    description="Admin dashboard için son kullanıcı aktivitelerini döner"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_activity(request):
    """Get recent user activities."""
    if not AuthService.is_admin(request.user):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        # Get recent users (last 7 days)
        recent_users = Kullanici.objects.filter(
            kayit_tarihi__gte=timezone.now() - timedelta(days=7)
        ).select_related('rol').order_by('-kayit_tarihi')[:10]

        activities = []
        for user in recent_users:
            # Check if user is a dietitian
            is_dietitian = hasattr(user, 'diyetisyen')
            
            activities.append({
                'user': {
                    'id': user.id,
                    'name': f"{user.ad} {user.soyad}",
                    'email': user.e_posta
                },
                'type': 'diyetisyen' if is_dietitian else 'danisan',
                'date': user.kayit_tarihi.isoformat(),
                'active': user.aktif_mi
            })

        return Response({
            'success': True,
            'data': activities
        })

    except Exception as e:
        return Response({
            'error': f'Error getting recent activity: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Sistem Uyarıları",
    description="Sistem uyarılarını ve bildirimlerini döner"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_alerts(request):
    """Get system alerts and notifications."""
    if not AuthService.is_admin(request.user):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        alerts = []
        
        # Check pending complaints
        pending_complaints = Sikayet.objects.filter(
            cozum_durumu='ACIK'
        ).count()
        
        if pending_complaints > 0:
            alerts.append({
                'type': 'warning',
                'title': 'Bekleyen Şikayetler',
                'message': f'{pending_complaints} adet çözülmemiş şikayet var',
                'count': pending_complaints,
                'action_url': '/admin/complaints/'
            })
        
        # Check system metrics
        metrics = metrics_collector.get_metrics_summary(60)
        
        if metrics.get('error_rate', 0) > 5:
            alerts.append({
                'type': 'danger',
                'title': 'Yüksek Hata Oranı',
                'message': f'Son 1 saatte %{metrics["error_rate"]:.1f} hata oranı',
                'count': int(metrics.get('error_rate', 0)),
                'action_url': '/admin/api-monitoring/'
            })
        
        if metrics.get('average_response_time', 0) > 2:
            alerts.append({
                'type': 'warning',
                'title': 'Yavaş Yanıt Süresi',
                'message': f'Ortalama yanıt süresi {metrics["average_response_time"]:.1f}s',
                'count': int(metrics.get('average_response_time', 0)),
                'action_url': '/admin/api-monitoring/'
            })
        
        # Check for users needing approval
        pending_approvals = Diyetisyen.objects.filter(
            onay_durumu='BEKLEMEDE'
        ).count()
        
        if pending_approvals > 0:
            alerts.append({
                'type': 'info',
                'title': 'Onay Bekleyen Diyetisyenler',
                'message': f'{pending_approvals} diyetisyen onay bekliyor',
                'count': pending_approvals,
                'action_url': '/admin/dietitians/pending/'
            })

        return Response({
            'success': True,
            'data': {
                'alerts': alerts,
                'total_count': len(alerts)
            }
        })

    except Exception as e:
        return Response({
            'error': f'Error getting system alerts: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Diyetisyen Başvurusu Onayla",
    description="Admin tarafından diyetisyen başvurusunu onaylama",
    request=DiyetisyenApprovalSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_diyetisyen(request, pk):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    diyetisyen = get_object_or_404(Diyetisyen, kullanici__pk=pk)
    
    if diyetisyen.kullanici.is_active:
        return Response({'error': 'Bu diyetisyen zaten onaylanmış.'}, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = DiyetisyenApprovalSerializer(
        data=request.data,
        context={'diyetisyen': diyetisyen}
    )
    
    if serializer.is_valid():
        try:
            # Diyetisyeni onayla
            diyetisyen.kullanici.is_active = True
            diyetisyen.kullanici.save()
            
            return Response({
                'message': 'Diyetisyen başvurusu başarıyla onaylandı.',
                'diyetisyen': DiyetisyenDetailWithApplicationSerializer(diyetisyen).data
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Diyetisyen Başvurusu Reddet",
    description="Admin tarafından diyetisyen başvurusunu reddetme",
    request=DiyetisyenRejectionSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_diyetisyen(request, pk):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    diyetisyen = get_object_or_404(Diyetisyen, kullanici__pk=pk)
    
    if diyetisyen.kullanici.is_active:
        return Response({'error': 'Bu diyetisyen zaten onaylanmış.'}, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = DiyetisyenRejectionSerializer(
        data=request.data,
        context={'diyetisyen': diyetisyen}
    )
    
    if serializer.is_valid():
        try:
            # Başvuruyu reddet - kullanıcıyı sil
            user = diyetisyen.kullanici
            user.delete()  # Cascade ile diyetisyen kaydı da silinir
            
            return Response({
                'message': 'Diyetisyen başvurusu reddedildi ve kayıt silindi.'
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Randevu Yeniden Ata",
    description="Admin tarafından randevuyu farklı diyetisyene atama",
    request=RandevuReassignSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reassign_randevu(request, pk):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    randevu = get_object_or_404(Randevu, pk=pk)
    
    serializer = RandevuReassignSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            yeni_diyetisyen = Kullanici.objects.get(id=serializer.validated_data['yeni_diyetisyen_id'])
            
            RandevuService.reassign_randevu(
                randevu=randevu,
                new_diyetisyen=yeni_diyetisyen,
                admin_user=request.user
            )
            
            return Response({
                'message': 'Randevu başarıyla yeniden atandı.',
                'randevu_id': randevu.id,
                'yeni_diyetisyen': yeni_diyetisyen.ad + ' ' + yeni_diyetisyen.soyad
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Kullanıcı Deaktif Et",
    description="Admin tarafından kullanıcı hesabını deaktif etme",
    request=UserDeactivationSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_user(request, pk):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    user = get_object_or_404(Kullanici, pk=pk)
    
    serializer = UserDeactivationSerializer(
        data=request.data,
        context={'user': user}
    )
    
    if serializer.is_valid():
        try:
            UserService.deactivate_user(
                user_id=user.id,
                admin_user=request.user,
                reason=serializer.validated_data['neden']
            )
            
            return Response({
                'message': f'Kullanıcı {user.ad} {user.soyad} başarıyla deaktif edildi.'
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Admin İstatistikleri",
    description="Platform genel istatistiklerini görüntüleme",
    responses={200: AdminStatsSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_statistics(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Kullanıcı istatistikleri
        user_stats = UserService.get_user_statistics()
        
        # Randevu istatistikleri
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        bugun_randevu = Randevu.objects.filter(tarih=today).count()
        bu_hafta_randevu = Randevu.objects.filter(tarih__gte=week_start).count()
        bu_ay_randevu = Randevu.objects.filter(tarih__gte=month_start).count()
        
        # İptal oranı
        toplam_randevu = Randevu.objects.count()
        iptal_randevu = Randevu.objects.filter(durum='IPTAL').count()
        iptal_orani = (iptal_randevu / toplam_randevu * 100) if toplam_randevu > 0 else 0
        
        stats = {
            'toplam_kullanici': user_stats['total_users'],
            'aktif_kullanici': user_stats['active_users'],
            'danisan_sayisi': user_stats['danisan_count'],
            'diyetisyen_sayisi': user_stats['diyetisyen_count'],
            'onay_bekleyen_diyetisyen': Diyetisyen.objects.filter(onay_durumu='BEKLEMEDE').count(),
            'onaylanan_diyetisyen': Diyetisyen.objects.filter(onay_durumu='ONAYLANDI').count(),
            'bugun_randevu': bugun_randevu,
            'bu_hafta_randevu': bu_hafta_randevu,
            'bu_ay_randevu': bu_ay_randevu,
            'iptal_orani': round(iptal_orani, 2)
        }
        
        return Response(stats)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Randevu Detayları",
    description="Admin tarafından randevu detaylarını görüntüleme"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_detail(request, pk):
    """Get appointment details for admin."""
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        randevu = get_object_or_404(
            Randevu.objects.select_related('diyetisyen__kullanici', 'danisan'),
            pk=pk
        )
        
        appointment_data = {
            'id': randevu.id,
            'randevu_tarih_saat': randevu.randevu_tarih_saat.strftime('%Y-%m-%dT%H:%M'),
            'durum': randevu.durum,
            'notlar': randevu.notlar,
            'diyetisyen_id': randevu.diyetisyen.id,
            'diyetisyen': {
                'kullanici': {
                    'ad': randevu.diyetisyen.kullanici.ad,
                    'soyad': randevu.diyetisyen.kullanici.soyad,
                    'e_posta': randevu.diyetisyen.kullanici.e_posta,
                    'telefon': randevu.diyetisyen.kullanici.telefon,
                },
                'hizmet_ucreti': randevu.diyetisyen.hizmet_ucreti
            },
            'danisan': {
                'ad': randevu.danisan.ad,
                'soyad': randevu.danisan.soyad,
                'e_posta': randevu.danisan.e_posta,
                'telefon': randevu.danisan.telefon,
            }
        }
        
        return Response({
            'success': True,
            'appointment': appointment_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Randevu Güncelle",
    description="Admin tarafından randevu bilgilerini güncelleme"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_appointment(request, pk):
    """Update appointment details by admin."""
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        randevu = get_object_or_404(Randevu, pk=pk)
        
        # Get form data
        randevu_tarih_saat = request.data.get('randevu_tarih_saat')
        durum = request.data.get('durum')
        diyetisyen_id = request.data.get('diyetisyen_id')
        notlar = request.data.get('notlar', '')
        
        if randevu_tarih_saat:
            randevu.randevu_tarih_saat = datetime.fromisoformat(randevu_tarih_saat)
        
        if durum:
            randevu.durum = durum
            
        if diyetisyen_id:
            yeni_diyetisyen = get_object_or_404(Diyetisyen, pk=diyetisyen_id)
            randevu.diyetisyen = yeni_diyetisyen
            
        randevu.notlar = notlar
        randevu.save()
        
        # Create notification for patient and dietitian about the change
        from core.models import Bildirim
        
        # Notify patient
        Bildirim.objects.create(
            kullanici=randevu.danisan,
            baslik="Randevu Güncellendi",
            mesaj=f"Randevunuz admin tarafından güncellendi. Yeni tarih: {randevu.randevu_tarih_saat.strftime('%d.%m.%Y %H:%M')}",
            bildirim_turu="RANDEVU_GUNCELLEME"
        )
        
        # Notify dietitian
        Bildirim.objects.create(
            kullanici=randevu.diyetisyen.kullanici,
            baslik="Randevu Güncellendi",
            mesaj=f"Randevunuz admin tarafından güncellendi. Yeni tarih: {randevu.randevu_tarih_saat.strftime('%d.%m.%Y %H:%M')}",
            bildirim_turu="RANDEVU_GUNCELLEME"
        )
        
        return Response({
            'success': True,
            'message': 'Randevu başarıyla güncellendi.'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Randevu Onayla",
    description="Admin tarafından randevuyu onaylama"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_appointment(request, pk):
    """Approve appointment by admin."""
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        randevu = get_object_or_404(Randevu, pk=pk)
        
        if randevu.durum != 'BEKLEMEDE':
            return Response({
                'success': False,
                'error': 'Sadece beklemede olan randevular onaylanabilir.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        randevu.durum = 'ONAYLANDI'
        randevu.save()
        
        # Create notifications
        from core.models import Bildirim
        
        # Notify patient
        Bildirim.objects.create(
            kullanici=randevu.danisan,
            baslik="Randevu Onaylandı",
            mesaj=f"Randevunuz onaylandı. Tarih: {randevu.randevu_tarih_saat.strftime('%d.%m.%Y %H:%M')}",
            bildirim_turu="RANDEVU_ONAY"
        )
        
        # Notify dietitian
        Bildirim.objects.create(
            kullanici=randevu.diyetisyen.kullanici,
            baslik="Randevu Onaylandı",
            mesaj=f"Randevunuz onaylandı. Tarih: {randevu.randevu_tarih_saat.strftime('%d.%m.%Y %H:%M')}",
            bildirim_turu="RANDEVU_ONAY"
        )
        
        return Response({
            'success': True,
            'message': 'Randevu başarıyla onaylandı.'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Randevu İptal Et",
    description="Admin tarafından randevuyu iptal etme"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_appointment(request, pk):
    """Cancel appointment by admin."""
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        randevu = get_object_or_404(Randevu, pk=pk)
        reason = request.data.get('reason', 'Admin tarafından iptal edildi')
        
        if randevu.durum == 'IPTAL':
            return Response({
                'success': False,
                'error': 'Bu randevu zaten iptal edilmiş.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        randevu.durum = 'IPTAL'
        randevu.iptal_nedeni = reason
        randevu.save()
        
        # Create notifications
        from core.models import Bildirim
        
        # Notify patient
        Bildirim.objects.create(
            kullanici=randevu.danisan,
            baslik="Randevu İptal Edildi",
            mesaj=f"Randevunuz iptal edildi. Neden: {reason}",
            bildirim_turu="RANDEVU_IPTAL"
        )
        
        # Notify dietitian
        Bildirim.objects.create(
            kullanici=randevu.diyetisyen.kullanici,
            baslik="Randevu İptal Edildi",
            mesaj=f"Randevunuz iptal edildi. Neden: {reason}",
            bildirim_turu="RANDEVU_IPTAL"
        )
        
        return Response({
            'success': True,
            'message': 'Randevu başarıyla iptal edildi.'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)