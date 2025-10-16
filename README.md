# Diyetlenio - Beslenme ve Diyet Platformu

## Render.com Deployment

### 1. Render.com'da Hesap Oluştur
- [Render.com](https://render.com) adresinden hesap oluşturun
- GitHub hesabınızla bağlantı kurun

### 2. Web Service Oluştur
- New → Web Service seçin
- GitHub repository'nizi bağlayın
- Aşağıdaki ayarları yapın:

**Build & Deploy:**
- Environment: `Python 3`
- Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- Start Command: `gunicorn diyetlenio_project.wsgi:application`

**Environment Variables:**
```
SECRET_KEY=[Render tarafından otomatik oluşturulacak]
DEBUG=False
ALLOWED_HOSTS=your-service-name.onrender.com,www.diyetlenio.com,diyetlenio.com
CORS_ALLOWED_ORIGINS=https://www.diyetlenio.com,https://diyetlenio.com
DATABASE_URL=[PostgreSQL database'inden otomatik gelecek]
```

### 3. PostgreSQL Database Oluştur
- New → PostgreSQL seçin
- Database Name: `diyetlenio`
- Oluşturulduktan sonra Internal Database URL'yi kopyalayın
- Web Service'inizin Environment Variables'a `DATABASE_URL` olarak ekleyin

### 4. Custom Domain (www.diyetlenio.com)
- Web Service Settings → Custom Domains
- `www.diyetlenio.com` ve `diyetlenio.com` ekleyin
- DNS kayıtlarını domain sağlayıcınızda güncelleyin:
  - `CNAME www your-service-name.onrender.com`
  - `A @ [Render IP adresi]`

### 5. İlk Deploy
- Render otomatik olarak deploy edecek
- Logları kontrol edin
- Database migration'lar otomatik çalışacak

### 6. Superuser Oluştur
Deploy tamamlandıktan sonra Render Dashboard'da:
- Web Service → Shell seç
- `python manage.py createsuperuser` komutunu çalıştır

## Yerel Geliştirme

```bash
# Sanal ortam oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Paketleri yükle
pip install -r requirements.txt

# Database migrate
python manage.py migrate

# Server başlat
python manage.py runserver
```

## Proje Yapısı
- `core/`: Ana uygulama (kullanıcılar, randevular, beslenme planları)
- `api/`: REST API endpoints
- `templates/`: HTML şablonları
- `static/`: CSS, JS, resim dosyaları
- `media/`: Kullanıcı yüklediği dosyalar