# 5.1.2 — profil koruma yaması ve yayın kabulü

1.3.2 paketi altı teklif becerisini 5.1.2 olarak yayımlar. Güncelleyici 2.3.0 korunur. Önceki ürün kapsamı [5.1.1 kabul sözleşmesinde](RELEASE_ACCEPTANCE_5.1.1.md) kayıtlıdır.

## Düzeltme

Ortam kontrolü veri deposu oluşturulmadan durursa güvenli rapor çifti varsayılan standart profil yerine istenen profili taşır. Profil, yalnız koşuya bağlı geçerli `teklif-resume/v1` kaydından okunur. Dosya aynı koşu dizini içinde olmalı, 64 KiB sınırını aşmamalı ve bilinen profillerden birini içermelidir. Bozuk veya başka koşuya bağlı kayıt profil doğrulaması üretmez; rapor UNKNOWN güvenli bildirim olarak kalır. Kaynak olgusu ve sıralama boş kalır.

## Kanıtın kapsamı

Bu sürümün tam SQLite/native DuckDB regresyonu, altı yeni test ve üç profilde ortam engeli XLSX/PDF teslimi yeni kaynak haritasına bağlı JSON/loglarla sunulur. Önceki 538 testi bu sürümün test sayısı değildir. Paket, yayımlanan Git ağacıyla bayt ve sürüm eşliği üzerinden doğrulanır.

Normal Excel hesaplama ve normal PDF üretim kodları bu yamada değişmez. 1.3.1'in gerçek Excel ve normal çift rapor kanıtı yalnız değişmeyen hesap/üretim yollarının geçmiş kanıtı olarak korunur; yeni bir Excel/host kabulü olarak sunulmaz. Yeni ortam engeli raporları güncel regresyonda fiziksel çift dosya olarak sınanır.

Business pazar eşitlemesi ve görünen sürüm ayrıca doğrulanır. ChatGPT Business hostunun gerçek model kullanım makbuzunu sağlamaması nedeniyle tam analitik kabul açık kalır. READY dosya teslimini gösterir; VERIFIED veya satınalma onayı değildir. Bu yama makbuz, doğrulama veya karar kapılarını gevşetmez.
