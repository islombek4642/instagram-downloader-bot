# Instagram Video Downloader Bot

**Professional Instagram Media Downloader Telegram Bot**

## 📝 Loyihaning maqsadi

Bu bot Instagram post, reels va stories linkini qabul qilib, RapidAPI orqali media (video/rasm) fayllarini oladi va foydalanuvchiga yuboradi. Bot professional darajada yozilgan va production environmentda ishlatishga tayyor.

## 🚀 Texnologiyalar

- **Python 3.11+** - Asosiy dasturlash tili
- **python-telegram-bot** - Telegram Bot API uchun async library
- **httpx** - HTTP so'rovlar uchun (connection pooling bilan)
- **SQLite** - Ma'lumotlar bazasi (statistika va user tracking)
- **python-dotenv** - Environment variables boshqaruvi
- **RapidAPI** - Instagram downloader API integration

## ✨ Xususiyatlar

- **Caching System** - Tez javob olish uchun in-memory cache
- **Connection Pooling** - HTTP so'rovlar optimizatsiyasi
- **Progress Indicators** - Real-time yuklash holati
- **File Size Validation** - Katta fayllar uchun tekshiruv
- **Queue Management** - Ko'p foydalanuvchi uchun navbat tizimi
- **Detailed Analytics** - Bot statistikasi va monitoring
- **Error Handling** - Professional xato boshqaruvi
- **Admin Panel** - /stats, /health, /contact buyruqlari

## 📁 Loyiha tuzilmasi

```bash
.
├── bot/
│   ├── __init__.py
│   ├── main.py              # Bot entry point
│   ├── config.py            # Configuration management
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py      # SQLite database operations
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py         # /start command handler
│   │   ├── help.py          # /help command handler
│   │   ├── contact.py       # /contact command handler
│   │   ├── stats.py         # /stats command handler (admin)
│   │   ├── health.py        # /health command handler (admin)
│   │   └── download.py      # Instagram link processing
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── common.py        # Reply keyboards
│   └── services/
│       ├── __init__.py
│       ├── instagram_downloader.py  # RapidAPI integration
│       ├── cache.py         # In-memory caching system
│       └── queue_manager.py # Queue management system
├── .env.example             # Environment variables template
├── .env                     # Your environment variables (not in git)
├── .gitignore              # Git ignore rules
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## O'rnatish

1. **Virtual environment** (venv) yaratish (Windows):

```bash
python -m venv venv
venv\Scripts\activate
```

2. **Loyihani clone qilish**:

```bash
git clone <repository-url>
cd instagram-downloader-bot
```

3. **Kutubxonalarni o'rnatish**:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Environment faylini sozlash**:

`.env.example` dan `.env` yarating:

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

`.env` faylini taxrirlang:

```env
# Telegram bot token (BotFather'dan oling)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIjKlMnOpQrStUvWxYz

# Admin chat ID (ixtiyoriy, /stats va /health uchun)
ADMIN_CHAT_ID=123456789

# RapidAPI sozlamalari
RAPIDAPI_KEY=your_rapidapi_key_here
RAPIDAPI_HOST=instagram-downloader-api.p.rapidapi.com
RAPIDAPI_URL=https://instagram-downloader-api.p.rapidapi.com/v1/download
```

### API Keys olish:

1. **Telegram Bot Token**: [@BotFather](https://t.me/botfather) ga o'ting
2. **RapidAPI Key**: [RapidAPI](https://rapidapi.com/) dan Instagram downloader API subscribe qiling
3. **Admin Chat ID**: [@userinfobot](https://t.me/userinfobot) dan oling

## 🚀 Botni ishga tushirish

```bash
# Virtual environment faollashtirish
venv\Scripts\activate    # Windows
source venv/bin/activate # Linux/Mac

# Botni ishga tushirish
python -m bot.main
```

Bot ishga tushgach:
1. Telegram'da botingizni toping
2. `/start` buyrug'ini yuboring
3. Instagram link yuboring (masalan: `https://www.instagram.com/p/ABC123/`)

## 💷 Buyruqlar

- `/start` - Botni ishga tushirish
- `/help` - Yordam ma'lumotlari
- `/contact` - Admin bilan bog'lanish
- `/stats` - Statistika (faqat admin)
- `/health` - Bot holati (faqat admin)

## ⚙️ Konfiguratsiya

### RapidAPI integratsiyasi

Bot turli RapidAPI Instagram downloader servislarini qo'llab-quvvatlaydi. `bot/services/instagram_downloader.py` da quyidagi javob formatlarini qo'llab-quvvatlaydi:

```json
// Format 1: Media array
{
  "media": [
    {"url": "https://example.com/video.mp4"},
    {"url": "https://example.com/image.jpg"}
  ]
}

// Format 2: Single URL
{
  "url": "https://example.com/video.mp4"
}

// Format 3: Named fields
{
  "download_url": "https://example.com/video.mp4",
  "video_url": "https://example.com/video.mp4",
  "image_url": "https://example.com/image.jpg"
}
```

### Cache sozlamalari

`bot/services/cache.py` da cache sozlamalarini o'zgartirishingiz mumkin:

```python
_media_cache = SimpleCache(
    max_size=100,        # Maksimal cache size
    ttl_seconds=1800     # Cache TTL (30 daqiqa)
)
```

## 🔧 Development

### Kengaytirish

1. **Yangi komandalar** qo'shish uchun `bot/handlers/` da yangi fayllar yarating
2. **Klaviaturalar** uchun `bot/keyboards/` dan foydalaning
3. **Database schema** o'zgartirishlari uchun `bot/db/database.py` ni tahrirlang
4. **Cache strategiyasi** uchun `bot/services/cache.py` ni sozlang

### Testing

```bash
# Bot holatini tekshirish
curl -X GET "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"

# Loglarni kuzatish
tail -f bot.log
```

### Deployment

1. **Docker** uchun `Dockerfile` yarating
2. **Systemd service** uchun `.service` fayl yarating
3. **Process manager** (PM2, Supervisor) ishlatib prod-da ishga tushiring

## 📊 Monitoring

- SQLite database da user va download statistikasi saqlanadi
- `/health` buyrug'i bilan tizim holatini tekshiring
- `/stats` buyrug'i bilan batafsil analytics ko'ring

## 🔒 Security

- API keys `.env` faylida saqlaning
- `.env` faylini git'ga commit qilmang
- Admin buyruqlar faqat `ADMIN_CHAT_ID` ga ruxsat beriladi
- File size validation orqali spam oldini oladi

## 📝 License

MIT License - batafsil ma'lumot uchun `LICENSE` faylini ko'ring.

---

**Muallif:** Anonymous Developer  
**Versiya:** 2.0  
**Sana:** 2025  
