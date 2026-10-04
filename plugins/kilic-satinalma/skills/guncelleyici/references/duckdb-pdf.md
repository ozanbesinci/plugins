# İsteğe bağlı DuckDB PDF desteği

## İş akışı

PDF, mevcut yedi bileşenden ayrı sekizinci satırdır; varsayılan seçim kapalıdır.
`sohbet.ps1 -Action scan -IncludePdf` sırasında kurulu DuckDB'nin sürümü, platformu,
yorumlayıcısı ve eklenti dizini gözlenir. PDF yüklenmez. İlgili `windows_amd64`
Community ikilisi HTTPS üzerinden sınırlandırılmış indirmeyle önbelleğe alınır;
plan ham açılmış ikilinin SHA-256 değerine bağlanır.

O platform/sürüm için paket yoksa "kontrol edilemedi/uyumlu yayın yok" bildir.
DuckDB sürümünü otomatik düşürme veya farklı Python ortamı kullanma. Python/DuckDB
önceden kurulmamışsa önce bunların planını tamamlayıp yeniden tara. DuckDB aynı
uygulamada güncellenirse PDF'nin eski motor eşleşmesi geçersizdir; ikinci PDF planı gerekir.

Açık uygulama onayından sonra aynı ikili yeni süreçte ayrı eklenti dizinine yerel
`INSTALL` ile kurulur, imza kontrolleri açıkken `LOAD pdf` çalıştırılır. Yalnız başarılı
hazırlıktan sonra eski ikili yedeklenir; dosyalar yerel hedefe alınır ve yeni süreçte
tekrar yüklenip test edilir. `allow_unsigned_extensions` açılmaz, toplu `UPDATE
EXTENSIONS` çalıştırılmaz. Üçüncü taraf kodunun gerçekten çalışması yalnız bu açık
kurulum veya kontrol isteği kapsamında gerçekleşir.

## Testin kapsamı ve sınırı

Otomatik yerel smoke test: tek sayfalık bilinen metni/sayfayı okuma, `read_pdf`,
`read_pdf_tables`, `pdf_info` işlevlerinin varlığı ve kaynak dosyanın değişmemesi.
Bu, Türkçe OCR veya gerçek teklif tablosu doğruluğu sertifikası değildir. Windows
kabulünde ayrıca Türkçe karakterli metin, ondalık virgül, çok sayfa/çok dosya,
birleşik hücre, taranmış sayfa, şifreli/bozuk PDF, timeout ve belge atlanması sınanmalı.
OCR dil modeli ayrıca doğrulanır; yalnız İngilizce modelin varlığı Türkçe için yeterli değildir.

## Güvenlik, saklama ve lisans

Community kodunun imzası CI'dan geldiğini doğrular; güvenlik denetimi garantisi değildir.
Eklenti kullanıcıyla aynı yetkilerde çalışır; bu aday OS sandbox sağlamaz. Bu pakete
PDF eklentisi ikilisi dahil edilmemiştir; lisans, kaynak ve sürüm/platform eşleşmesi
uygulama planında görünür. Katalog lisansı GPL-2.0-or-later olarak belirtir; kurumsal
paketleme/dağıtım biçiminin lisans değerlendirmesi BT/hukuk sürecidir.

Varsayılan eklenti dizini kullanıcı başına paylaşılır. Venv kullanmak otomatik olarak
bu dizini izole etmez. Eklenti güncellendikten sonra mevcut DuckDB süreçleri yeniden
başlatılmalıdır. Bu aday eski Python PDF araçlarını kaldırmaz, kullanıcının PDF'lerini
uzak servise yüklemez ve mevcut teklif analizinin veri çıkarım yöntemini değiştirmez.

Kaynaklar: [teknik kaynaklar](kaynaklar.md). Bu geliştirme oturumunda native DuckDB
PDF ikilisi çalıştırılmamıştır; `BUILD.json` ve test raporundaki NOT_RUN kaydı korunur.
