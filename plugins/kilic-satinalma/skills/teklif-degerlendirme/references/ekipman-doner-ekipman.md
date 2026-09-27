# Ekipman Kontrol Listesi — Pompa, Kompresör, Fan/Blower, Karıştırıcı, Separatör

Ana `SKILL.md`'deki genel çerçeveye ek olarak bu grupta karşılaştırılacak kalemler.
Döner ekipmanda satın alma fiyatı toplam maliyetin küçük bir kısmıdır — **enerji ve bakım
baskındır**, bu yüzden TCO modülü burada zorunludur.

## Performans ve seçim doğruluğu

- **Çalışma noktası:** debi × basma yüksekliği/basınç. Firmanın seçtiği model, istenen
  çalışma noktasında verim eğrisinin neresinde çalışıyor? En yüksek verim noktasının (BEP)
  uzağında seçilmiş bir pompa hem enerji yakar hem erken bozulur
- Verim (%) **çalışma noktasında** — nominal verim değil
- NPSHr ve tesisin NPSHa değeriyle karşılaştırma (kavitasyon riski); **yetersiz marj
  kırmızı çizgi**
- Kapama basıncı, minimum sürekli debi, çalışma aralığı
- **Kompresörde:** serbest hava debisi (FAD), **özgül güç (kW/(m³/min))** — asıl kıyas
  metriği bu, kurulu güç değil; basınç kademeleri, kurutucu/filtre dahil mi
- Fan/blower: statik/toplam basınç, çalışma eğrisinde stall bölgesine yakınlık, ses seviyesi
- Karıştırıcı: devir, kanat tipi, güç yoğunluğu (kW/m³), karışma süresi
- **Frekans konvertörü (VSD/sürücü) dahil mi** — kısmi yükte çalışan uygulamada TCO'yu
  belirleyen kalem
- Kapasite toleransı: standarda göre kabul toleransı (ör. ISO 9906 sınıfı) hangi seviyede
  taahhüt ediliyor

## Motor ve elektrik

- Motor gücü, verim sınıfı (IE3/IE4/IE5), koruma sınıfı (IP), yalıtım sınıfı,
  gerilim/frekans, ATEX gereksinimi
- Motor markası ve menşei — mevcut tesis parkıyla uyum (standardizasyon kriteri)
- Marş/yol verme yöntemi, motor koruma, termistör/PTC
- Sürücü markası ve programlama erişimi (şifre/yazılım teslimi)

## Mekanik detaylar

- Gövde/çark/mil malzemesi (dökme demir, bronz, paslanmaz, dubleks) ve akışkan
  uyumluluğu — aşındırıcı/tuzlu su uygulamasında belirleyici
- **Salmastra tipi:** mekanik salmastra (tek/çift, API 682 kategorisi, üretici markası)
  veya gland paketi; salmastra su/bariyer sıvısı sistemi dahil mi. Salmastra en sık
  arızalanan parçadır, marka farkı TCO'ya doğrudan girer
- Yataklama tipi, yağlama yöntemi, hesaplanan yatak ömrü (L10h)
- Kaplin tipi, kaplin koruması, kaide (baseplate) ve grout gereksinimi
- Titreşim limiti (ISO 10816/20816 sınıfı) ve ölçüm taahhüdü, denge sınıfı
  (ISO 1940 G kalitesi)
- Ses basınç seviyesi (dB(A), ölçüm mesafesi) ve varsa yasal/işletme limiti
- Sökülebilirlik: bakım için üst kapak sökümü (back pull-out), yerinden çıkarma gereksinimi

## Test ve kabul

- Fabrika performans testi: tanıklı mı, hangi standart (ISO 9906 / ISO 1217 / AMCA), test
  debisi-basınç-güç-verim ölçümleri
- NPSH testi, titreşim ve gürültü ölçümü, sızdırmazlık testi
- Motor + ekipman string testi mi, ayrı ayrı mı
- Saha kabul (SAT) koşulları ve garanti edilen değerlerin sahada nasıl ölçüleceği

## TCO girdileri (bu grup için kritik)

- Aynı çalışma noktasında elektrik giriş gücü = mil gücü / motor verimi
  (sürücü kaybı varsa ayrıca). Faydalı hidrolik güçten başlanıyorsa pompa verimi de
  paydada olur; ölçülmüş giriş gücüne tekrar verim düzeltmesi yapılmaz.
- Yıllık enerji farkı (kWh) = `(P_giriş_A − P_giriş_B) × çalışma saati`;
  maliyet farkı = kWh farkı × birim enerji fiyatı. **Verim yüzdesi farkı × saat
  enerji değildir.** Ek yatırım varsa basit ve iskontolu geri ödeme hesaplanır.
- Aşınma parçaları (salmastra, rulman, aşınma plakası, kayış, filtre, yağ) yıllık maliyeti
  ve firmalar arası parça fiyat farkı
- Beklenen revizyon periyodu ve revizyon maliyeti
- Muadil parça kullanılabilirliği ↔ üreticiye bağımlılık
- Arıza hâlinde duruş etkisi: yedek (stand-by) ünite var mı; tek üniteli sistemde duruş
  maliyeti yüksektir
