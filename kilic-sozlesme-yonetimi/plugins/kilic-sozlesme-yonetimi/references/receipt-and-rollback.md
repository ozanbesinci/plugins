# İşlem makbuzu ve geri dönüş sınırı

İstek önce `CreateNew` ile tüketilir. Claim değişmez; son makbuz ayrı dosyada, aynı dizindeki geçici dosyanın üzerine yazmayan atomik taşımasıyla yayımlanır. Boş/yarım claim veya STARTED-only kayıt yeniden çalıştırma izni değildir. İşlem başladıktan sonra belirsiz sonuç otomatik tekrar edilmez.

Native kesinti matrisi gerçek dosyalar/süreç çıkışı kullanır; write/flush/move hata enjeksiyonları kendi kategorisinde kayıtlıdır. Claim öncesi seri hale getirme hatası dosya üretmez. Claim sonrası write/flush hatası veya süreç ölümü tüketilmiş kayıt bırakır. Final öncesi hata son kaydı yok bırakır; süreç çökmesinde geçici dosya kalabilir. Final taşımasından sonra çökme, parse edilebilir finali korur. Her durumda ikinci yan etki engellenir; yabancı dosyalar korunur.

`Get-ContractRequestReceiptState` yalnız `-LibraryOnly` geliştirici teşhisinde kullanılır. Runtime `requests` dizini, request UUID, beklenen SHA-256 ve beceri kimliği açık verilir. Eski tek dosyalı STARTED/COMPLETED/FAILED kayıt ve yeni claim/final ayrı okunur. Bozuk, eksik, farklı hash veya karışık format RECOVERY_REQUIRED; finali olmayan claim tüketilmiş kalır. Terminal kayıt iş kabulü veya teslim doğrulaması değildir. Helper dosya değiştirmez, izin/kimlik/HMAC/QA doğrulamaz ve otomatik resume önermez.

## Veritabanı uyumu

001–006 migration dosyaları değiştirilmedi. Native testler 001–005 fixture'ından006 yükseltme, tekrar açılış, digest drift, gelecekteki007 ret ve006 DDL kesintisinde atomik rollback'i kapsar. Üretimde otomatik destructive downgrade yoktur.

Denetim commit'i `f5f739d867a0de701ee4adf20854941a7d3c331c`, paket tree kimliği `daa04a6867242ea558fe2847335e9daaab1fb4ed` ile ayrı Temp referansına alınır. Referans gerçek kodu yeni Python sürecinde yükler; ürün test sürecinde eski koda sessiz import yapılmaz. Denetim kodu güncel006 DB'yi kayıpsız okuyabilir ve007 DB'yi değiştirmeden reddeder. Ancak ortak sonuç şeması hatası nedeniyle iş değerlendirmesi bloklanır; bu sürüm tam iş akışı için kararlı geri dönüş paketi değildir.

Geri dönüş planı: etkilenen yeni yazıcı/özelliği kapat, tüketilmiş claim/izin/audit ve kaynak kayıtlarını koru, kod+DB çiftini aynı hash/şema ile doğrula. Önceki teknik aday da gerçek host/ekip kabulü olmadan kararlı fallback sayılmaz. Normal üretim Word ve K29 gönderim/mailbox yasağı bütün seçeneklerde kapalıdır.

## Test koşusu kesilirse

Test envanteri ve fsync edilmiş STARTED/terminal olaylar ayrı kaydedilir. Çocuk süreç terminal makbuzu üretmeden ölürse yalnız dayanıklı terminali bulunan testler kaydedilir; başlayan ama bitmeyen ve hiç başlamayan testler NOT_RUN. Parçalı olay kuyruğu/discovery eksikliği açık hata olur; tüm koşu PASS'a yükseltilmez. Referans Git nesnesi bulunamıyorsa uyum kanıtı üretilemez. CI bu yüzden tam Git geçmişini okur; CI'nin çalıştırılması ayrıca NOT_RUN olabilir.
