# Kılıç Tedarikçi Yönetimi 1.4.1

Teklif becerileri 5.2.1. Güncelleyici becerisi ve motoru bu paketten çıkarılmıştır. Kılıç Satınalma Departmanı tarafından geliştirilmiştir.

Başlangıç: `& "<aktif-paket>/scripts/teklif.cmd" skill_startup --skill teklif-degerlendirme`. Python veya hesap motoru eksikse giriş sabit SHA-256 ile doğrulanan yayımlanmış kurulum paketini otomatik indirip çalıştırır. Kurulum ve aktif paket doğrulaması tamamlanınca aynı komut devam eder. Hazır ortam yeniden kurulmaz. Geliştiriciden kişisel izin veya elle indirme istenmez. Yönetici yetkisi, sistem PATH veya çalıştırma politikası değiştirilmez; kurumsal engel somut hatayla bildirilir.

Analiz: `& "$env:USERPROFILE\KilicPython\teklif-python.exe" "<aktif-paket>/scripts/runtime_launcher.py" workflow prepare --source "<kaynak>" --run "<koşu>" --profile standart`. Başlangıç kontrolünden sonra analiz ve devam komutları kayıtlı native Python girişinden çalışır; karmaşık argümanlar CMD üzerinden aktarılmaz. Kayıtlı yerel Python ve tam paket kilidi korunur. Ayrıntı: [kurulum ve çalışma ortamı](skills/teklif-degerlendirme/KURULUM.md).

Doğrulanmış teklif bedelleri ve kaynak kalemleri ayrı Excel senaryolarına aktarılır. Bilinmeyen vergi/kur/gider tamamlanmaz. Fiyat birimi, KDV dahil fiyat ve ardışık iskonto desteklenir. Çok kriterli puanlama, baz ve iki alternatif ağırlık senaryosu kullanıcı hesaplarıdır; resmî karar değişmez. Excel'den içe alma yeni Excel/PDF ön rapor revizyonu üretir.

ChatGPT Work web devamı için aynı uygun görevin yerel bilgisayar erişimi bulunmalıdır; bilgisayar ve masaüstü uygulaması bağlı olmalıdır. Web'de her yeni görev için kendiliğinden yerel erişim varsayılmaz. Yerel kancalara veya yeni bir sunucuya dayanılmaz.

1.4.1 değişikliği otomatik ortam hazırlama girişidir. Önceki 1.4.0 analiz/motor kabul kayıtları tarihsel kanıttır; yeni başlangıcın Windows kabulü ayrıca kaydedilir.

Dev.9 kaynak fiyat sayfasında yalnız parasal satırlar para birimi taşır. Miktar, iskonto/KDV yüzdesi, fiyat böleni ve KDV esası para değildir. Hesap, veri sözleşmesi, snapshot ve PDF fiyat hesabı değişmedi.

Web teslimi resmî Work/Library aracıyla yapılır. Üretilen yerel dosya yolu, web indirmesinin tamamlandığı anlamına gelmez. Teslim ayrıntısı ana becerinin `references/work-file-delivery.md` dosyasındadır.
