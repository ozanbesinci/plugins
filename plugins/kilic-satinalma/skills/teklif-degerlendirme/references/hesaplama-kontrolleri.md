# Hesaplama Kontrolleri — net fiyat, ödeme mutabakatı ve karar sınırları

Adım 3, 5 ve 11'de okunur. Amaç farklı referanslardaki hesapların aynı bedeli,
miktarı ve zamanı kullanmasını sağlamaktır. Aşağıdaki sayılar **sentetik kontrol
örnekleridir**, güncel kur/faiz/vergi/rayiç önerisi değildir.

## 1. Net fiyat ve ortak ihtiyaç

- Fiyatın birimi kaydedilir: TL/adet, TL/100 adet, TL/ton, TL/koli gibi.
  `satır brüt = miktar × birim fiyat / fiyatın kapsadığı birim sayısı`.
- Ardışık iskontolar toplanmaz: `net = brüt × (1−d1) × (1−d2)`.
  1.000 TL'ye %10 + %5 iskonto = **855 TL**, 850 TL değildir.
- Satır iskontosu ile genel iskonto farklı matrahlarda uygulanır; genel iskonto
  yalnız sözleşmede kapsadığı satırlara dağıtılır. Net verilmiş fiyata yeniden iskonto
  yapılmaz. Nakit ödeme indirimi yalnız o ödeme planının senaryosunda kullanılır.
- Opsiyonlar, zorunlu ilaveler, bedelsiz ürün, depozito ve ambalaj ayrı satırlardır.
  Koşullu yıl sonu primi/ciro indirimi gerçekleşmiş tasarruf kabul edilmez.
- Ortak miktar bütün birim fiyat tekliflerine uygulanır; %5 fark eşiği muafiyet
  değildir. A: 100 adet × 100 = 10.000; B: 96 × 103 = 9.888. İhtiyaç 100 ise
  B **10.300** olur; daha küçük toplam yanlış kazanan üretmemelidir.
- Sabit kurulum/nakliye kalemi miktarla ölçeklenmez. Götürü fiyatın toplam/miktar
  oranı yalnız gösterge birim maliyetidir, revize teklif yerine geçmez.
- Kademeli fiyat için **tüm miktara uygulanan kademe** ile **yalnız aşan miktara
  uygulanan kademe** ayrılır. Bölünmüş sipariş paket indirimini kaybettirebilir.
- Miktar × fiyat, iskonto, vergi ve toplam kaynak beyanla ayrı ayrı mutabık olmalı.
  Kuruş yuvarlama satır/genel toplam esasına göre yapılır; fark otomatik düzeltilmez.
  Farkın yönü, tutarı ve açıklaması yazılır. Puanlar sıralamadan önce yuvarlanmaz.

## 2. Kullanılabilir miktar, minimum sipariş ve bölünmüş alım

`sipariş miktarı = paket katına yukarı yuvarla(MAX(MOQ, net ihtiyaç / (1−fire)))`.
Fire oranı satın alınan miktarın kayıp payı olarak tanımlıdır; ihtiyaç üzerine ek
pay tarif ediliyorsa bunun formülü farklıdır. Fire < 1, miktar/paket > 0 olmalıdır.

- 950 sağlam adet, %5 kayıp, MOQ 1.100, paket 100 ise sipariş **1.100 adet**,
  beklenen kullanılabilir miktar **1.045**, ihtiyaç fazlası **95** olur.
- Fazla stok bedeli nakit bütçesinde tam yer alır. Tüketileceği/iadeye uygun olduğu
  kanıtlanmadan bedelden düşülmez. Dönem sonu stok değeri düşülürse aynı stok ayrıca
  fire/atıl stok gideri yapılmaz. Depolama/bozulma gideri ayrıca, finansman etkisi
  ödeme modelinde tek kez hesaplanır.
- Kimyasal: `aktif kg = net ürün kg × aktif madde payı`; ambalaj darası hariç.
  20 kg bidon, %25 aktif, 500 TL ise **100 TL/kg aktif madde**.
  Aynı aktif madde miktarı aynı kullanım performansını garanti etmez; doz/numune
  uygunluğu gereklidir. Konsantrasyon 0 ise bölme yapılmaz.
- Birim başına net maliyet = ilgili toplam maliyet / **aynı ihtiyacı karşılayan
  kullanılabilir çıktı**. Malzeme firesi ile OEE'nin kalite kaybı aynı kaybı iki kez
  saymamalıdır. OEE = kullanılabilirlik × performans × kalite; üretim çıktısına
  uygulandıktan sonra aynı kalite oranı yeniden çarpılmaz.
- Çok kalemli alımda: tek tedarikçi, kalem bazında en ucuz ve uygun bölünmüş alım
  senaryolarını değerlendir. Bölünmüş alımda her tedarikçinin MOQ, kapasite, sabit
  nakliye, paket indirimi, teknik arayüz ve garanti sorumluluğunu yeniden hesapla.
  Her satırın en ucuzunu toplamak tek başına uygulanabilir sipariş değildir.

## 3. Tek maliyet kaydı ve NBD mutabakatı

Her giderin tek kimliği olur: kaynak → maliyet kalemi → sorumlu taraf → nominal tutar
→ para birimi → ödeme tarihi → iskonto oranı → bugünkü değer → KTM basamağı.
Kaynakta dahil, eklenen, uygulanmayan, tahmini ve fiyatlanmamış durumları ayrıdır.
**Bilinmeyen ≠ sıfır.** Bilinen ara toplam ile fiyatlanmamış kalemler birlikte sunulur.

Alıcının çıkışı pozitif, iadesi/alacağı negatiftir. Ortak değerleme tarihinde:

```
N = eşit kapsamlı alımın nominal maliyeti (basamak 1–6, tek para biriminde)
P = bu alımın ödeme akışlarının NBD'si (TCO ve eskalasyon ilavesi hariç)
F = P − N + henüz N/P'ye girmemiş alıcı banka giderlerinin NBD'si
          + indirilebilir KDV'nin ödeme/mahsup NBD farkı
KTM = N + F + işletme/ömür sonu net giderlerinin NBD'si + eskalasyon farkının NBD'si
```

Her gider tek yerdeyse KTM, bütün ilgili nakit akışlarının doğrudan NBD toplamına
eşit olmalıdır. Finansman oranı borçlanmayı temsil ediyorsa aynı tutar/dönemin kredi
faizi ayrıca eklenmez; gerçek kredi akışı kullanılacaksa tutarlı ayrı model kurulur.

- 100.000 TL, tamamı bir yıl sonra, %20 oran: P=**83.333,33**, F=**−16.666,67**;
  KTM=83.333,33. N + P = 183.333,33 hatadır.
- 100 sözleşme, 20 avans; iki eşit 50 brüt hakediş, her birinden 10 avans mahsubu
  ve 5 teminat kesintisi: ödemeler **20 + 35 + 35 + 10 iade = 100**.
  Avans anaparası ve teminat mektubu anaparası ek satınalma maliyeti değildir.
- 20.000 indirilebilir KDV bugün ödenip bir yıl sonra %20 oranla mahsup ediliyorsa
  finansman etkisi **3.333,33**: 20.000 − 20.000/1,20. Mahsup bir nakit girişi
  olmak zorunda değildir; vergi ödemesindeki azalma olarak modellenir.
- 10.000 depozito bugün çıkıp bir yıl sonra iade edilirse %20 ile maliyeti
  **1.666,67**; anaparanın tamamı ayrıca gider değildir. Nakit bütçesinde görünür.
- 100.000 baz bedelin %60'ı endeksli, endeks +%20, bir yıl sonra ödenecekse
  nominal fark 12.000, %20 ile eskalasyon NBD farkı **10.000**.
  Ödeme akışı zaten 112.000 kurulduysa 10.000 ayrıca tekrar eklenmez.
- Olasılık verilmemiş düşük/baz/yüksek değerler **senaryo**dur, beklenen değer
  değildir. Beklenen değer yalnız toplamı 1 olan gerekçeli olasılıklarla hesaplanır.

## 4. Kur, vergi ve oran birimleri

- TCMB dönüşümü: `TL = yabancı tutar × ForexSelling / Unit`.
  Örnek: 100 JPY için 30 TL kur verilmişse 10.000 JPY = **3.000 TL**.
  Başka kıyas para birimi için normalize edilmiş TL kurları üzerinden çapraz kur kur.
  Unit, kur tarihi, kur türü ve kaynak görünür olur; kur boş/0 ise hesap durur.
- KDV dahil 120, oran %20: net **100**, KDV **20**; indirim hakkı %50 ise KTM'de
  net + indirilemeyen KDV = **110**, nominal ödeme bütçesi 120.
- Oran hücresinde %20 = 0,20; %5 = 0,05, binde 5 = 0,005.
  Oran, gün/ay/yıl, kW/kWh ve kg/ton birimleri kontrol edilir.
- NBD oranı > −1 olmalı; negatif reel oran geçerli olabilir, otomatik sıfırlanmaz.
  Sıfır oran: NBD = nominal akışların toplamı. Varsayım olarak %0 kullanılmaz.

## 5. Kararın ne zaman değiştiği

- Tahmini giderler için dayanaklı alt/baz/üst aralık kur; bilinmeyen fiyata keyfi %10
  ekleyip kesin teklif gibi davranma. Aralık kurulamıyorsa fiyatlanmadı olarak bırak.
- **Başabaş kur:** aynı tarih/yöntemde doğrusal KTM_A=a+b×kur,
  KTM_B=c+d×kur ise `kur*=(c−a)/(b−d)`. b=d ise tek başabaş kur yoktur;
  kur*≤0 ise pozitif kur aralığında geçiş yoktur. Endeks eşiği/tavanı ve çoklu döviz
  varsa formül zorlanmaz, bütün model senaryolarla çözülür.
- **Pazarlık hedefi:** eşit kapsamlı KTM farkını kapatacak indirim; satıcı bedelinin
  dışındaki sabit giderlerden indirim beklenmez. İndirimin vergi, kademe ve ödeme
  etkisi yeniden hesaplanır. Fark hem TL hem uygun matraha göre % olarak gösterilir.
- **Tasarruf:** `(aynı kapsam/tarih/miktardaki referans maliyet − yeni maliyet)`.
  Bütçe farkı, son alıma göre fark ve pazarlık indirimi ayrı isimle sunulur;
  gerçekleşmemiş alım tasarrufu gerçekleşmiş diye yazılmaz.
- En ucuz maliyet, toplam puan ve teknik uygunluk ayrı sonuçlardır. Eksik veriye
  bağlı kazanan **koşullu öneri** olur; yakın puan bilimsel eşdeğerlik sayılmaz.

## 6. Doğrulama ve kaynak

Üretilen Excel'in formülleri ile bağımsız hesap aynı sonucu vermeli. Miktar/kur/vade/
iskonto girdisini değiştirince ilgili bütün toplam ve sıralamalar yenilenmeli. Oranı
sıfırlama, aynı maliyetler, elenmiş en ucuz teklif, boş fiyat, sıfır gün teslim,
tek tedarikçinin alternatifleri ve paket indirimi kaybı sınırları kontrol edilir.

Sayısal örneklerin kontrolü: `python scripts/hesaplama_ornekleri_test.py` (skill klasöründen).
Bu kontrol örnek matematiğini sınar; üretilen Excel'i veya gerçek teklifin doğruluğunu
kendi başına onaylamaz. Excel ayrıca yeniden hesaplanıp sonuçları karşılaştırılır.

[TCMB kur serileri](https://evds3.tcmb.gov.tr/tumSeriler/2501/bie_dkefkytl)
100 JPY birim ayrımını gösterir (kontrol: 2026-09-05). Vergi, komisyon ve Incoterms
kaynakları ilgili finans/ithalat referanslarında yer alır.

## 7. Koşullu ilave hesaplar

`nakit-kalite-stok.md`: ödeme takviminde en yüksek nakit ihtiyacı; kalite kaybı
anlamlıysa kalite/ilave kontrol maliyeti; düzenli tüketim veya toplu alımda sipariş
ve stok senaryoları. Yeni giderin tek kimliği hem KTM hem nominal nakit takvimine
bağlanır. Tepe nakit tutarı ek maliyet değildir; stok sermaye gideri ödeme NBD
düzeltmesinin üstüne tekrar eklenmez.
