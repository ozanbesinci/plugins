# E-posta kaynaklarının okunması

EML, aynı kaynak sürümü/hash/okuyucu önbelleği üzerinden `document-read --format EML` ile okunur.
Kaynağa yazılmaz; her başlık, metin satırı ve ek ayrı MIME konumuna bağlıdır.

- Tarih, Message-ID, gönderen ve alıcı belge verisidir; kimlik veya şirket onayı değildir.
- `quote_marker=OBSERVED` yalnız açık `>` veya iletilen ileti ayracı gösterir. Eski teklif bugünkü kabul sayılmaz. `NOT_DETERMINED` yeni teklif veya kabul kanıtı değildir.
- Düz metin ve HTML alternatifleri ayrı kalır. HTML kodu/bağlantıları çalıştırılmaz veya indirilmez; görsel sadakat ayrı kontroldür.
- Ek dosyanın adı yalnız metadatadır. Dosya adı kullanılarak diske çıkarma yapılmaz; payload hash/boyutu envanterde bulunur. İlgili ek kullanıcı tarafından seçilen güvenli kaynaktan ayrı belge/sürüm olarak alınır, kaynak ilişkisi bağlanır.
- Ek e-posta ayrı kaynak gerektirir. Otomatik güncel gövdeye birleştirilmez.
- Gönderen doğrulaması, dijital imza, e-posta gönderimi ve iş kararı bu okuyucunun yeteneği değildir.

Sınırlar: 64 MiB ham kaynak, 8 MiB MIME parçası, 128 parça, 16 seviye, 30 saniyelik ayrı okuyucu süreci. Kodlama/MIME belirsizliği engelleyici görünür. Tam kaynak görüntüsü ve uzman değerlendirmesi yerine yalnız metin eşleşmesiyle kritik inceleme tamamlandı denmez.
