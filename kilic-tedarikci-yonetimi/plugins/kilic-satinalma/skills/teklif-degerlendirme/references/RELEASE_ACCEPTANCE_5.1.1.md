# 5.1.1 — yayın kapsamı ve kabul sözleşmesi

Bu sürüm deterministik 5.x çekirdeğini korur. Her profilde bir çok sekmeli formüllü XLSX ve bir çok sayfalı PDF; iş verisi yetersizliğinde güvenli ön rapor; kaynak bütünlüğü bozuksa doğrulanmamış bedelleri göstermeyen bildirim üretir. İki fiziksel dosya doğrulanmadan READY verilmez. READY, VERIFIED ve satınalma onayı ayrı statülerdir.

## Yeni davranış

- SQLite/native DuckDB ayrı süreçlerde gerçek bağlantı sınıfıyla doğrulanır; koşu kimliği, kaynak hash'i ve gerçek sayaçlar kaydedilir.
- Resmî ve ön raporlar immutable revizyondur. Fiziksel dosya doğrulaması ve metadata transaction'ı sonrasında aktif çift kaydedilir; arızada önceki çift korunur.
- Şartname matrisi uygunsuz, belirtilmemiş, teyit bekleyen, çelişkili ve okunamayan maddeleri ayırır.
- Kaynak ve kullanıcı varsayımları ayrılır. Miktar/iskonto/kur/vergi/ithalat, ödeme/NBD, TCO, puan/duyarlılık ve senaryo farkları konum/ifade bağlı izinli Excel formülleridir.
- 12 ödeme, KDV geri kazanımı, sabit veya 100 yıla kadar yıl bazlı giderler ve kalıntı NBD'si desteklenir. Eksik maliyet sıfır olmaz.
- Bağımsız tarihli nakit defteri 48 tekil maliyet kaydında para birimi, nakit tarihi ve aynı tarihli açık kullanıcı kur projeksiyonunu kullanır. Satınalma/navlun/sigorta/gümrük/KDV/enerji/bakım/sarf/yenileme/diğer/kalıntı türleri beyan edilmeden tam toplam verilmez. Diğer otomatik hesap toplamları bu deftere eklenmez. Kur/NBD yöntemi hedef paranın nakit tarihinde projekte edilen tutarını hedef para efektif oranıyla indirger; spot ve vadeli kur sessizce karıştırılmaz.
- Gregoryen YYYY-MM-DD tarihleri Python ve Excel'de ortak doğrulanır; Excel'in hayalî 1900-02-29 günü gerçek süreye eklenmez.
- Excel kullanıcı girdileri kaynak/formül mühürü kontrolünden sonra yeni ön rapor çiftine alınır; kapalı koşu ve kaynaklar değiştirilmez.
- Modelin XLSX adres alias'ı kayıt/miktar/maliyet boyunca aynı yorumlanır; çelişen veya mevcut olmayan kaynak adresi kabul edilmez. Açık miktar/geçerlilik düzeltmesi yalnız aktif, kaynak hash'i korunmuş teklif/alan sorusuna bağlanır; kaynak olgusu değiştirilmez ve kapanmış koşu açılmaz.
- Karar beklerken ön rapor da hash bağlı kullanıcı tarih/miktar/ödeme/garanti beyanlarını ayrı gösterir. Miktar esasıyla kaynak satırlarından çıkan ara tutar tam TCO veya sıralama değildir; yanıt/kaynak tahrifinde bu değerler güvenli bildirime taşınmaz. İki PDF motoru ve korunan Excel sekmeleri aynı beyanları taşır.
- Gerçek Excel işi izole kopya/ayrı süreç/süre sınırıyla yürür. Sahipliği kanıtlanmayan Excel süreçleri sonlandırılmaz. Yapısal formül kontrolü native hesap kabulü değildir.
- İkincil DuckDB PDF okuyucusu yoksa açık uyarı verilir; ana motor ve birincil PDF okuma/rapor bağımlılıkları zorunludur. Özel kabul --require-pdf-extension ile ayrı sınanır; otomatik kurulum yoktur.

## Zorunlu yayın kanıtı

Son sürümlü kaynak üzerinde tam SQLite ve native DuckDB regresyonu; gerçek Windows/Excel cached değerleri; her profil ve olumsuz iş durumunda çift dosya; PDF firma/tutar/alan bağı ve görsel kontrol; temiz açılım, sürüm, manifest ve dosya hash eşliği gerekir. Gerçek host/model kabulü, sentetik/mock testten ayrı kaydedilir. SKIP/NOT_RUN veya eski 399/438/474/486 PASS yeni kabul sayılmaz. Sayılar ve mevcut kaynak haritası yayınla birlikte verilen kabul JSON/loglarında bulunur; bu sözleşme test sonucu yerine geçmez.

## Açık ürün sınırları

Kur, vergi, iskonto ve puan ağırlıkları kaynaklı veya açık kullanıcı girdisidir; onaylı şirket politikası uydurulmaz. Puan senaryosu rekabetçi firma sıralaması değildir. Normalize edilemeyen kapsam, tek firma veya eksik maliyet kesin sıralamayı engeller; raporu engellemez. Tarihli defterin tamlığı beyan edilen tür/kayıt kümesi içindir; şirket kapsam onayı değildir. ERP/SAP sipariş ve harcama onayı verilmez. Bütün 45 tarihsel denetim işi bu sürümle kapatılmış sayılmaz.

Güncelleyici 2.3.0 kaynak/motoru ve production_approved=false alanı korunur. Bu yayın bilgisayardaki üretim kurulumu veya güncelleyici çalıştırması değildir. Önceki 5.0.29 kabul belgesi tarihsel sürümün kanıtı olarak saklanır.


5.1.1 ek kabulü: teyitli eleme sonrası tek uygun tedarikçi, tek firmanın çoklu alternatifleri ve teyitsiz elemenin uygun kümeyi daraltmaması; üç profilde doğru karşılaştırma durumu ve tek XLSX/PDF çifti. Kaynak envanteri değişmeden korunur. Eski 530 PASS bu yeni sürümün koşusu değildir.
