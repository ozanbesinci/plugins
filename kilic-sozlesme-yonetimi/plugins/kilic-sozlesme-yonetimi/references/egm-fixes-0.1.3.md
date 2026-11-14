# EGM düzeltmeleri — yerel 0.1.3-dev.1

Bu aday kaynak kod ve sentetik teknik test içindir. Normal DOCX çıktısı hâlâ TEKNIK_ENGEL; P4/P5 sentetik izni üretim izni değildir. E-posta gönderimi/mailbox taslağı yok. Yeni yayın veya şirket/uzman kabulü değildir.

1. HTML hücre başlangıçları ve tablo sınırları korunur; aktif içerik çalıştırılmaz.
2. Doğrudan strike/dstrike aralıkları RAW/BEFORE/AFTER içinde konumlu JSON metadata olarak taşınır. Bu işaret hukuki iptal kararı değildir.
3. Muğlak tek noktalı sayı/yüzde biçimi kaynaklı dayanak olmadan reddedilir. Biçim dayanağı aynı sürümde olmalı; kullanıcı biçim teyidi açık değer düğümüne bağlanır.
4. Test kaydı tüm 13 sabit bağımlılığı, Python sürümünü/ABI/mimarisini, kilit ve profil hash'lerini taşır; sürüm aracı hedef profille karşılaştırır.
5. Migration 007 içerik hash tekilliğini sürüm olayından ayırır. DuckDB kısıtı kaldıramadığı için tarihsel DDL ve tüm veriler mevcut kilit/işlem içinde korunarak tablolar yeniden kurulur. Önceki migration dosyaları değiştirilmez. Veri farkında/hatada rollback olur; eski çekirdek yeni şemayı SEMA_DRIFT ile reddeder.
6. K04 iki sürümü salt referans/güncel hedef olarak okur; metin farkını ve konumlarını döndürür. Desteklenmeyen veya metinsiz görünüm eşit sayılmaz. Anlamsal/hukuki karşılaştırma ve genel görsel sadakat kabulü yoktur.
7. Para eş adları ve Türkçe İ dönüşümü desteklenir. Ayrı hücreli tutar/birim aynı sürüm ve sayfada, açık satır veya sütun başlığı ilişkisiyle bağlanır. İlişkinin iş anlamı doğrulanmış sayılmaz.
8. DATE_TR gün.ay.yıl ve Türkçe ay adlı tam tarihleri standart tarihe çevirir; geçersiz/belirsiz tarihi tahmin etmez.
9. Açık partial_review seçimi yalnız eksik bağımlılıkta ve mevcut bütün düğümler güncelse sınırlı kanıt görünümü sağlar. Normal tam kapanım alanı boş ve registered_closure_complete=false kalır; eksik ek görünürdür. Bütçe/eski kaynak kapısı korunur.
10. Okuma uyarıları işlem kaydında korunur; her kaynak düğümü yerel uyarı ve ortak uyarı hash referansı taşır. Bağlamda ortak uyarılar bir kez sayılır ve bütçelenir.
11. PDF açıklama dizisinin dolaylı referansı çözülür; yanlış tür açıkça reddedilir.
12. OOXML ana parça türü önce Override, yoksa Default kaydıyla çözülür; yanlış, muğlak veya yinelenmiş kayıt kabul edilmez.
13. Gerçek staging yordamı hassas adları ve bağlantılı kaynakları kopyalamadan önce reddeder. T53 gerçek yordamı sahte kimlik dosyalarıyla sınar; OS kullanıcı izolasyonu veya gerçek sır sızıntısı kabulü değildir.
14. PDF görüntüsü genel DB kilidi dışında üretilir. Kayıttan önce case revision, kaynak/snapshot, okuma/profil, renderer ve geçersizleştirme kontrolleri yeniden yapılır.

Sabit yayımlanmış Windows kurucu pini değiştirilmedi. Kurucuya dayanan testler yalnız izole geçici kullanıcı profilinde yürütülür; kullanıcının mevcut kurulumu değiştirilmez. Yeni adayın tam test sonucu ayrı kanıt kaydından okunmalıdır; bu belge PASS beyanı değildir.
