# 🔓 Gercek Unlock Servisi Kurulumu

`/unlock` komutunun lock ekranindan **sifreyi gercekten girebilmesi** icin
LocalSystem yetkisinde calisan kucuk bir Windows servisi gerekir. Bu servis
bot'tan gelen istekle Winlogon desktop'a gecip `SendInput` cagirir — normal
kullanici modunda calisan bot'un yapamadigi sey.

## Mimari

```
Telefon (Telegram)
   │
   ▼
Bot (kullanici modunda, python main.py)
   │  named pipe + paylasilan secret
   ▼
unlock_service.py  (LocalSystem servisi, NSSM araciligi ile)
   │  SetThreadDesktop("Winlogon") + SendInput
   ▼
Lock ekrani — sifre alani
```

## Kurulum

### 1. `.env`'i guncelle

```env
# Mevcut bot ayarlarinin altina:
UNLOCK_PASSWORD=senin-windows-sifren
UNLOCK_SERVICE_SECRET=cok-uzun-rastgele-bir-string-mesela-32-karakter
```

`UNLOCK_SERVICE_SECRET` istemci-sunucu kimlik dogrulamasi icin kullanilir;
ayni dosyayi hem bot hem servis okudugu icin senkron olur.

### 2. PowerShell'i **yonetici** olarak ac

`Start` → `PowerShell` → sag tik → `Run as Administrator`.

### 3. Script'i calistir

```powershell
cd "D:\Github\Atheris-PC-Control-Bot"
Set-ExecutionPolicy -Scope Process Bypass
.\install_unlock_service.ps1
```

Script:

- NSSM'i `tools\nssm\` altina indirir (yoksa)
- `AtherisUnlock` servisini `LocalSystem` hesabiyla kayit eder
- Otomatik baslama ayarlar
- Servisi baslatir
- Servis loglarini `logs/unlock_service.log` ve stdout/stderr dosyalarina yazdirir

### 4. Test

Bot'u baslat (`python main.py`), Telegram'da:

1. `/lock` → PC kilitlenir
2. `/unlock` → 2-3 saniye icinde unlock olmali

## Beklenen davranis

- Servis acik **ve** `UNLOCK_PASSWORD` + `UNLOCK_SERVICE_SECRET` dolu →
  bot pipe ile servisi cagirir, servis Winlogon'a sifreyi girer, **gercek unlock**.
- Servis kapali / kurulu degil → bot fallback'e duser; sadece monitoru
  uyandiran wake jiggle gonderir, sifreyi kullanici elle girmek zorunda kalir.
- Servis yanit veriyor ama sifreyi reddediyor → Windows lock ekrani sifreyi
  yazdi ama dogrulamadi (yanlis sifre veya hesap PIN'e gecmis olabilir).
  PIN destegi icin `UNLOCK_PASSWORD` yerine PIN'i koy.

## Kaldirma

```powershell
.\install_unlock_service.ps1 -Uninstall
```

## Guvenlik notlari

- **`.env` repo'da yok** (gitignore). Sifre ve secret sadece kendi makinende durur.
- Pipe sadece localhost — uzaktan erisilemez.
- Yine de `UNLOCK_SERVICE_SECRET` dolu olmali; bos ise ayni makinede calisan
  baska bir process pipe'a istek atip unlock tetikleyebilir.
- Servis loglari hassas bilgi yazmaz (sifreyi loglamiyoruz, sadece OK/ERR).

## Olasi sorunlar

| Belirti | Cozum |
|---------|-------|
| `unlock servisi calismiyor` | `services.msc` → `AtherisUnlock` baslatilmis mi? Yoksa script'i tekrar calistir. |
| `auth fail` | `.env`'deki `UNLOCK_SERVICE_SECRET` ile servisin gordugu farkli. Servisi yeniden baslat (`nssm restart AtherisUnlock`). |
| `Winlogon desktop'a gecilemedi` | Servis LocalSystem hesabi yerine kullaniciyla calisiyor. NSSM'de `Log On` sekmesini `Local System Account` yap. |
| Sifre yaziliyor ama unlock olmuyor | Hesap PIN/Hello istiyor olabilir. `UNLOCK_PASSWORD`'a PIN koy, ya da Settings → Sign-in options → PIN'i kapat. |

## Disable

Calismadigi durumda asla bota mahkum kalmazsin:

- `/screen_off` ile soft-lock kullan (PC kilitlenmez ama monitor kapanir, bot tam erisimde)
- Microsoft Remote Desktop ile telefondan baglan (zaten Windows resmi olarak yapiyor bu isi)
