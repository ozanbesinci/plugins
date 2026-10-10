# Yerel hata kaydı

Hata ve açık teknik engeller `%LOCALAPPDATA%\KilicSatinalma\logs\errors_<UTCgün>_<pid>_<oturum>.jsonl` altında UTF-8 JSONL olarak tutulur. Başarılar ve normal `PRELIMINARY`, `PRELIMINARY_ONLY`, `UNVERIFIED`, `NEEDS_LLM_RESPONSE` sonuçları hata değildir; eksik şartname/finans bilgisi bu nedenle hata kaydı üretmez. Açık FAIL/BLOCKED/ortam engeli ve Python sınırlarında yakalanan istisnalar kaydedilir.

Kayıt yalnız zaman, bileşen/plugin sürümü, sabit işlem adı, durum, işlem/oturum kimliği ve istisna türü ile en fazla beş kod dosyası adı/fonksiyon/satır taşır. Belge, sohbet, fiyat/kişi/firma adı, argümanlar, ham istisna metni, tam dosya yolları ve yerel değişkenler yazılmaz. Uzak aktarım, yeni bağımlılık veya model çağrısı yoktur.

Süreç/oturum dosyaları ayrıdır. Süreç başına 100 olay ve dosya başına 1 MiB sınırı vardır; eski dosyalar silinmez. Kilit meşgulse beklenmez, olay düşürülür. LOCALAPPDATA yoksa kayıt kapalıdır. Sürüm okunamazsa UNKNOWN kullanılır. Yazma başarısızlığı asıl sonucu, istisnayı, JSON çıktısını veya çıkış kodunu değiştirmez.

Kapsam: workflow prepare/advance, model sonucunu kaydetme, ortam kontrolü, bağımsız yeniden hesap ve validate_run Python sınırları; ayrıca yakalanan ikincil kontrol istisnası. Erken import/argüman hatalarının tamamı, zorla kapatılma ve modelin her anlamsal yanlışı kapsanmaz. Bu kayıt kabul kanıtı ve model makbuzunun yerine geçmez. Bu skill'in PowerShell çalışma giriş noktası bulunmadığından yeni bir giriş/kurulum katmanı eklenmez.

Tasarım kaynağı: [Kılıç Sözleşme Yönetimi PR 1](https://github.com/ozanbesinci/kilic-sozlesme-yonetimi-plugin/pull/1), incelenen commit `5b2f7524f773482d7673d63455d5a31a41c56db1` (2026-10-06). Aynı hata odaklı ve yazma arızasına dayanıklı yaklaşım teklif motorunun mevcut Python sınırlarına uyarlanmıştır.
