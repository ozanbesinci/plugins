# Ekipman Kontrol Listesi — Elektrik Panosu, MCC, PLC/SCADA, Enstrümantasyon

Bu grupta fiyat farkı neredeyse tamamen **kullanılan komponent markası ve pano donanım
sınıfından** kaynaklanır. Marka listesi karşılaştırılmadan yapılan fiyat kıyası anlamsızdır.

## Pano ve komponent

- Standart: EN/IEC 61439-1/-2 uygunluğu, tip test (TTA) veya tasarım doğrulaması, koruma
  sınıfı (IP/IK), gövde malzemesi (sac kalınlığı, boya, paslanmaz gerekiyorsa kalite)
- **Komponent marka listesi kalem kalem:** şalter, kontaktör, sürücü, PLC, röle, klemens,
  sigorta, güç kaynağı. **"Muadili" ifadesi kabul edilmez** — marka-model istenir
- Kısa devre dayanımı (Icu/Icw), seçicilik (selektivite) çalışması yapılmış mı,
  koordinasyon tablosu
- Baraların akım taşıma kapasitesi ve malzemesi (bakır/alüminyum), izolasyon mesafeleri
- Isı hesabı ve iklimlendirme (fan/klima/eşanjör) — panonun ortam sıcaklığında derating
  durumu
- Ark koruma, **iç ayırma formu (Form 1-4b)** — bakım güvenliği açısından önemli ve fiyatı
  doğrudan etkiler
- Kablo giriş yönü, kablo tavası/kanal kapsamı, etiketleme standardı
- **Rezerv:** boş modül/klemens/giriş-çıkış yüzdesi (şartname %20 istiyorsa kim veriyor)
- Kompanzasyon (varsa): reaktif güç, harmonik filtre gereksinimi, reaktör tipi, sürücü
  sayısına göre harmonik analizi yapılmış mı (THD limiti)

## PLC / SCADA / yazılım

- **PLC ve HMI marka/model** — mevcut tesis standardıyla uyum en yüksek ağırlıklı
  kriterlerden biri (bakım ekibi yetkinliği, yedek parça ortaklığı, mühendislik lisansı)
- I/O sayısı, tipi ve rezerv oranı; uzak I/O ve haberleşme protokolü
  (Profinet/Profibus/EtherCAT/Modbus)
- Emniyet PLC'si ve emniyet fonksiyonlarının PL/SIL seviyesi
- **Yazılım teslimi:** kaynak kod, proje dosyası, şifre, dokümante edilmiş program.
  Verilmeyecekse bu bir bağımlılıktır ve **kırmızı çizgi** olarak öne çıkarılır
- Mühendislik yazılımı lisansı kimde, alıcıya devrediliyor mu
- SCADA: lisans tipi ve tag sayısı sınırı, istemci sayısı, tarihçe (historian) veri saklama
  süresi, rapor sayısı, sonraki yıllar için **lisans yenileme/bakım bedeli** (gizli sürekli
  maliyet)
- Kullanıcı yetkilendirme, alarm yönetimi, olay kaydı, veri yedekleme
- **ERP/SAP entegrasyon arayüzü:** hangi protokol, veri seti, kimin geliştireceği ve test
  edeceği
- Uzaktan erişim yöntemi ve kurumsal siber güvenlik politikasına uygunluk (VPN, ağ ayrımı,
  port talepleri)

## Enstrümantasyon

- Ölçüm noktası listesi: tip, ölçüm aralığı, doğruluk sınıfı, proses bağlantısı, malzeme
  uyumluluğu
- Marka/model, kalibrasyon sertifikası (izlenebilir kalibrasyon), yeniden kalibrasyon
  periyodu
- ATEX gereksinimi olan bölgeler ve kategori uygunluğu
- Gıda temaslı sensörlerde hijyenik bağlantı ve uygunluk belgesi

## Test, dokümantasyon, kabul

- Fabrika testi: fonksiyon testi, dielektrik/yalıtım direnci testi, kablolama kontrolü,
  tanıklı FAT
- Saha testi: I/O kontrol (loop check), fonksiyon senaryoları, emniyet devresi doğrulaması
- Dokümantasyon: tek hat şeması, pano yerleşimi, kablolama şeması, I/O listesi, klemens
  planı, as-built teslim şartı, parametre yedekleri
- Devreye alma ve eğitim: operatör + bakım + mühendislik seviyesinde, Türkçe

## Kapsam boşluğu riskleri (mutlaka sorulur)

- Saha kablolaması ve kablo tavası kimde
- Pano nakliyesi, sahaya taşıma ve yerleştirme (dar kapı/asansör sorunu)
- Topraklama ve enerji besleme bağlantısı kimde
- Eski pano demontajı ve **elektrik kesinti planı** (mevcut hat yenilemesinde duruş süresi
  maliyeti)
- Elektrik projesi/onayı ve varsa ilgili kurum onayları

## TCO girdileri

- Sürücü kullanımıyla elde edilen enerji tasarrufu (varsa) yıllık kazanç olarak yazılır
- SCADA/PLC lisans yenileme ve yazılım bakım bedeli (yıllık, N yıl için NBD'ye girer)
- Komponent ömrü ve yedek stok maliyeti; marka değiştiğinde tesiste **ikinci bir yedek
  stok** tutma zorunluluğu doğar — bu, standardizasyon kriterinin parasal karşılığıdır
