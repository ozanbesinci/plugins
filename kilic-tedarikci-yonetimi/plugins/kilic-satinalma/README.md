# Kılıç Tedarikçi Yönetimi 1.4.0

Teklif becerileri 5.2.0. Güncelleyici becerisi ve motoru bu paketten çıkarılmıştır. Kılıç Satınalma Departmanı tarafından geliştirilmiştir.

Python kurulumu eklenti dışındaki `kurulum/Kur.cmd` ile kullanıcı profiline yapılır. Kurucu yönetici yetkisi, sistem PATH değişikliği veya başka bir eklenti kurulumu gerektirmez. Eklenti yalnız hazır ortamı doğrular ve kullanır. Çalıştırma ilkeleri engellenirse politika atlatılmaz; engel açıkça bildirilir.

Başlatıcı: `& "$env:USERPROFILE\KilicPython\teklif-python.exe" "<aktif-paket>/scripts/runtime_launcher.py" workflow prepare --source "<kaynak>" --run "<koşu>" --profile standart`. Diğer Python betik adları aynı başlatıcıyla çağrılır. Ortam kimliği, kilit ve Python yolu korunur; genel python/PATH seçimi yapılmaz.

Doğrulanmış teklif bedelleri ve kaynak kalemleri ayrı Excel senaryolarına aktarılır. Bilinmeyen vergi/kur/gider tamamlanmaz. Fiyat birimi, KDV dahil fiyat ve ardışık iskonto desteklenir. Çok kriterli puanlama, baz ve iki alternatif ağırlık senaryosu kullanıcı hesaplarıdır; resmî karar değişmez. Excel'den içe alma yeni Excel/PDF ön rapor revizyonu üretir.

ChatGPT Work web devamı için aynı uygun görevin yerel bilgisayar erişimi bulunmalıdır; bilgisayar ve masaüstü uygulaması bağlı olmalıdır. Web'de her yeni görev için kendiliğinden yerel erişim varsayılmaz. Yerel kancalara veya yeni bir sunucuya dayanılmaz.

Bu kaynak 1.4.0 kararlı sürümüdür. Gerçek Work analizi, otomatik hesap, Microsoft Excel referansı, aynı sohbet web devamı ve tarayıcıdan özgün rapor ZIP teslimi doğrulandı. GitHub dağıtımı ve ChatGPT Business çalışma alanı için hazırlanmıştır. Kullanıcı bilgisayarındaki Python ve hesap motoru ayrı kurulum paketiyle hazırlanır. Güncel test/kabul durumu `skills/teklif-degerlendirme/references/RELEASE_ACCEPTANCE_5.2.0.md` dosyasındadır. Tarihsel sürüm kabul kayıtları yeni sürüm kanıtı değildir.

Dev.9 kaynak fiyat sayfasında yalnız parasal satırlar para birimi taşır. Miktar, iskonto/KDV yüzdesi, fiyat böleni ve KDV esası para değildir. Hesap, veri sözleşmesi, snapshot ve PDF fiyat hesabı değişmedi.

Web teslimi resmî Work/Library aracıyla yapılır. Üretilen yerel dosya yolu, web indirmesinin tamamlandığı anlamına gelmez. Teslim ayrıntısı ana becerinin `references/work-file-delivery.md` dosyasındadır.
