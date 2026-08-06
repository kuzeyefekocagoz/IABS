# IABS (İnsan Algılama ve Anlık Bildirim Sistemi)

IABS, gerçek zamanlı insan algılama yapan ve algılama gerçekleştiğinde fotoğraf kaydedip bildirim gönderebilen Python tabanlı bir güvenlik uygulamasıdır.

## Özellikler

- 🎥 Gerçek zamanlı kamera görüntüsü
- 🤖 YOLO11 ile insan algılama
- 📍 ByteTrack ile kişi takibi
- 📸 Otomatik fotoğraf kaydı
- 📊 Excel kayıt sistemi
- 📄 Log kayıtları
- 📧 E-posta bildirimi
- 💬 WhatsApp bildirimi
- 🔔 Sesli alarm
- 🖥️ Modern grafik arayüz (Tkinter / CustomTkinter)

---

## Kullanılan Teknolojiler

- Python 3.13+
- OpenCV
- Ultralytics YOLO11
- ByteTrack
- Tkinter
- CustomTkinter
- OpenPyXL
- Requests

---

## Kurulum

Projeyi klonlayın.

```bash
git clone https://github.com/KULLANICI_ADIN/IABS.git
cd IABS
```

Bağımlılıkları yükleyin.

```bash
pip install -r requirements.txt
```

YOLO modelini indirin.

```
yolo11s.pt
```

Dosyayı proje klasörüne yerleştirin.

---

## Çalıştırma

```bash
python main.py
```

---

## Proje Yapısı

```
IABS/
│
├── main.py
├── gui.py
├── camera.py
├── settings.py
├── mail_sender.py
├── whatsapp_sender.py
├── excel_logger.py
├── requirements.txt
├── config.example.json
├── README.md
├── LICENSE
├── tests/
├── photos/
├── logs/
└── excel/
```

---

## Yapılandırma

`config.example.json` dosyasını kopyalayın.

```
config.example.json
↓
config.json
```

Kendi bilgilerinizi girin.

- Gmail
- WhatsApp API
- Kamera ayarları
- Klasör yolları

---

## Ekran Görüntüleri

> Daha sonra eklenecektir.

---

## Lisans

Bu proje MIT Lisansı ile lisanslanmıştır.

---

## Geliştirici

**Kuzey**

GitHub: https://github.com/KULLANICI_ADIN
