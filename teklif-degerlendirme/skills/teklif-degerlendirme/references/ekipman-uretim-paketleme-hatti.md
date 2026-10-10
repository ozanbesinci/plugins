# Ekipman Kontrol Listesi — Üretim / Paketleme Hattı, Dolum, Tasnif, Konveyör Sistemi

Bu grupta teklif farkları tek bir makinede değil, **hattın bütününde ve garanti edilen
çıktıda** ortaya çıkar. **Kapsam boşluğu riski en yüksek ekipman grubudur.**

## Kapasite ve verim garantisi

- **Nominal kapasite ↔ garanti edilen kapasite ↔ sürdürülebilir kapasite** ayrımı:
  "1.500 adet/saat" mekanik hız mı, gerçek çıktı mı
- Kapasite hangi ürün/format/ağırlıkta geçerli? Ürün değiştiğinde kapasite düşüşü tabloya
  alınır (su ürünlerinde boy/ağırlık dağılımı kapasiteyi doğrudan etkiler)
- OEE / verimlilik garantisi (%) ve ölçüm yöntemi; hangi duruşlar hesaba katılmıyor
- **Fire/hurda oranı garantisi (%)** — ambalaj ve ürün firesi; yüksek fire oranı yıllık
  maliyette kapasite farkından büyük olabilir
- Dolum/tartım hassasiyeti ve yasal metroloji uygunluğu (ortalama içerik kuralı, onaylı
  tartı), doğrulama/kalibrasyon yükümlülüğü
- **Format değişim süresi (change-over)** ve alet gerektirip gerektirmediği; günde birden
  çok format değişimi olan tesiste kapasite kadar önemlidir
- Darboğaz analizi: hattaki en yavaş istasyon hangisi, tampon (buffer) kapasitesi ve hat
  dengesi
- Ürün besleme/çıkış yüksekliği ve mevcut hatla arayüz uyumu

## Kapsam sınırları (kalem kalem sorulmalı)

- Hangi istasyonlar dahil: besleme, tasnif, tartım, dolum, kapatma/mühürleme, etiketleme,
  kodlama, metal dedektörü/X-ray, kontrol kantarı, kutulama, paletleme, streçleme
- Konveyörler, aktarma üniteleri, ürün ret (reject) istasyonları, toplama kapları
- Hat üstü yardımcı sistemler: basınçlı hava hazırlama, vakum, soğutma, buhar, azot, CIP
- Elektrik dağıtımı ve pano besleme kablolaması nereye kadar firmada
- Platform, koruma kafesi, güvenlik bariyeri, kapı kilitleri
- **Ambalaj malzemesi spesifikasyonu:** makine hangi film/kutu/kap kalınlığıyla çalışıyor,
  mevcut tedarikçinin malzemesiyle uyumlu mu (**gizli sürekli maliyet** — makineye özel
  ambalaj bağımlılığı)

## Emniyet ve mevzuat

- CE beyanı ve 2006/42/EC uygunluğu, risk analizi dosyası, **hat bütünü için "makine
  grubu" CE'si kimin sorumluluğunda** — en sık atlanan nokta
- Emniyet fonksiyonlarının PL (ISO 13849) / SIL seviyesi, emniyet rölesi/PLC, acil stop
  mimarisi
- Koruyucu, ışık bariyeri, kapı emniyet şalterleri, LOTO uygunluğu
- Gürültü seviyesi (dB(A)) ve İSG limiti
- **Gıda/su ürünleri:** hijyenik tasarım (EHEDG ilkeleri), gıda temaslı malzeme uygunluğu
  (EC 1935/2004), yıkanabilirlik ve IP koruma sınıfı (yüksek basınçlı yıkama yapılıyorsa
  IP65/IP69K), ölü bölge ve drenaj, temizlik süresi (vardiya başına kaybedilen süre
  kapasiteyi düşürür)

## Otomasyon ve veri

- PLC/HMI markası ve modeli — **mevcut tesis standardıyla uyum** (bakım ekibinin bildiği
  marka, yedek parça ortaklığı)
- **Yazılım/PLC şifresi ve kaynak kod teslimi** — verilmezse her modifikasyon ve arıza tek
  firmaya bağımlı hâle gelir; kırmızı çizgi adayı (bkz. `sozlesme-maddeleri.md` madde 11)
- Uzaktan erişim/teletanı imkânı ve siber güvenlik gereksinimleri, kurumsal ağ politikasına
  uyum
- Veri çıkışı: üretim raporu, izlenebilirlik (lot/parti takibi), OPC-UA/MQTT desteği,
  ERP/SAP entegrasyon arayüzü **ve kimin geliştireceği**
- Reçete/parametre yönetimi, kullanıcı yetkilendirme, alarm geçmişi
- HMI dili (Türkçe) ve operatör arayüzü

## Devreye alma, eğitim, kabul

- Montaj süresi ve **hattın duruş süresi** (mevcut üretimin kaç gün duracağı — parasal
  etkisi TCO'ya girer)
- Devreye alma: kaç kişi × kaç gün, kim ödüyor, hangi koşullarda ek gün ücreti doğuyor
- Eğitim: operatör + bakım, kaç saat, Türkçe, dokümantasyon
- **FAT** (fabrikada, gerçek ürünle mi simülasyonla mı) ve **SAT** (sahada, gerçek üretim
  koşullarında) protokolleri; kapasite ve fire garantisinin hangi testte doğrulanacağı
- Performans testinin başarısız olması hâlinde süreç: düzeltme, tekrar test, ceza, red hakkı
- Ramp-up desteği: kabul sonrası ilk hafta/ay yerinde destek var mı

## TCO girdileri

- Kurulu güç ve gerçek tüketim (hat toplamı), basınçlı hava tüketimi (Nm³/h — genelde
  hesaba katılmaz ama pahalıdır)
- Aşınma ve sarf parçaları: bıçak, kayış, conta, çene, ısıtıcı rezistans, filtre — yıllık
  liste ve fiyat
- **Ambalaj malzemesi tüketim farkı** (film kalınlığı/uzunluğu) — yıllık tonaj × fiyat,
  çoğu zaman makine fiyat farkından büyük
- Fire oranı farkının yıllık ürün kaybı olarak parasallaştırılması
- Temizlik ve format değişim sürelerinin yıllık kapasite kaybı
- Öngörülen duruş × duruş maliyeti; servis müdahale süresi taahhüdü bu kalemi belirler
