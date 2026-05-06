# Atheris PC Control Bot

Telegram uzerinden Windows PC'yi uzaktan kontrol eden Python botu. Ekran goruntusu, mouse/klavye otomasyonu, sistem komutlari, uygulama yonetimi, ses kontrolu, webcam ve dosya transferi.

> Roadmap icin [TASK.md](TASK.md) dosyasina bak.

## Hizli baslangic

1. **Bot olustur:** Telegram'da [@BotFather](https://t.me/BotFather) ile yeni bot olustur, token'i al.
2. **Kendi User ID'ni ogren:** [@userinfobot](https://t.me/userinfobot)
3. **Repo'yu clone'la** ve venv kur:
   ```powershell
   git clone https://github.com/ethemdemirkaya/Atheris-PC-Control-Bot.git
   cd Atheris-PC-Control-Bot
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **`.env` dosyasi olustur** (`.env.example` baz alinabilir):
   ```env
   BOT_TOKEN=123456:ABCDEF
   ALLOWED_USER_IDS=123456789
   LOG_LEVEL=INFO
   ```
5. **Calistir:**
   ```powershell
   python main.py
   ```
6. Telegram'da botuna `/start` yaz.

## Komutlar

`/help` ile tam liste. Ozeti:

- **Ekran:** `/screenshot`, `/click X Y`, `/type METIN`, `/key TUS`, `/scroll N`, `/mouse_pos`
- **Sistem:** `/sysinfo`, `/uptime`, `/battery`, `/lock`, `/sleep`, `/shutdown`, `/restart` (onayli)
- **Uygulama:** `/run AD`, `/processes`, `/kill AD_veya_PID`, `/find ARAMA`
- **Medya:** `/volume`, `/mute`, `/playpause`, `/next_track`, `/webcam`
- **Dosya:** `/files YOL`, `/download YOL`, dosya gonderince Downloads'a kaydeder
- **Diger:** `/menu` interaktif inline menu

## Guvenlik

- **Whitelist + fail-closed:** `ALLOWED_USER_IDS` bossa hicbir kullanici cevap alamaz.
- **Rate limit:** Kullanici basina pencere icinde maksimum komut sayisi (`.env`).
- **Audit log:** Her komut `logs/bot.log`'a yazilir (kullanici, handler, mesaj).
- **Onay zorunlulugu:** `/shutdown`, `/restart`, `/logoff` icin inline button onayi.
- **Subprocess guvenligi:** `shell=False`, sabit argumanlar — komut injection yok.
- **Dosya sandbox:** Sadece `FILE_ALLOWED_ROOTS` altindaki yollar okunur/yazilir; path traversal `Path.resolve()` + prefix kontrolu ile engellenir.
- **Hata mesaji:** Public yanit sadece exception turu icerir, stack trace sahibe DM olarak gider.

> ⚠️ Token bir kez sizarsa biri PC'ne tam erisim alir. `.env`'i asla commit etme (gitignore'da). Token'i degistirmek icin BotFather → `/revoke`.

## Sinirlamalar

- Sadece **Windows** hedeflenmistir (ctypes/pycaw cagrilari).
- **UAC promptlarina** botla tiklanamaz; admin onayi gereken islemler dis hatta kalir.
- **Kilitli ekranda** `pyautogui` calismaz; `/lock` sonrasi otomasyon devre disidir.
- Telegram bot API dosya limiti: **50 MB**.

## Yapi

```
.
├── main.py                 # Giris + handler kayit + global error handler
├── config.py               # .env yukleyici
├── auth.py                 # @authorized decorator (whitelist + rate limit + audit)
├── handlers/
│   ├── start.py            # /start /help
│   ├── screen.py           # screenshot, click, type, key, scroll
│   ├── system.py           # sysinfo, uptime, battery, lock, sleep, shutdown (onayli)
│   ├── apps.py             # run, processes, kill, find
│   ├── media.py            # volume, mute, media keys, webcam
│   ├── files.py            # files, download, gelen dosya kaydet
│   └── interactive.py      # /menu inline keyboard
├── utils/
│   ├── logger.py           # Rotating dosya + konsol logger
│   └── helpers.py          # Bytes/duration formatters, reply
└── requirements.txt
```

## Lisans

MIT (eklenecek). Bu bot kendi PC'ni kontrol etmek icindir; baska birinin PC'sinde calistirmak izinsiz erisimdir.
