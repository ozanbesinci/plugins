# Analiz Hazırlığı — Kapsam, Kaynak ve Karşılaştırılabilirlik

## Maliyet Köprüsü Zinciri (bu skill'in omurgası)

**Teklif fiyatları asla doğrudan kıyaslanmaz.** Her teklif sırayla aşağıdaki basamaklardan
geçirilir ve sonunda tek bir **Karşılaştırılabilir Toplam Maliyet (KTM)** üretilir. Zincir
Excel'de **görünür satırlar** hâlinde kurulur; her basamak formülle bir öncekine bağlanır.

| # | Basamak | Ne yapar | Ne zaman devrede |
|---|---|---|---|
| 1 | Teklif fiyatı | kendi para birimi, kendi teklif tipi, kendi Incoterms'i, kendi kapsamı, kendi miktarı | her zaman |
| 2 | Kur çevrimi | tek para birimi (TCMB Döviz Satış Kuru; erişim yoksa kullanıcıdan) | farklı para birimi varsa |
| 3 | Miktar düzeltmesi | ortak referans metraja / ortak adede getirme | firmalar arası miktar farkı varsa |
| 4 | İthalat köprüsü | DDP eşdeğer maliyet (navlun, sigorta, gümrük, vergi, müşavirlik, iç nakliye) | ithal teklif veya farklı Incoterms |
| 5-A | Eşit kapsam düzeltmesi — **firmalar arası** | bir firmanın verip diğerinin vermediği kalemleri tam kapsama getirme (montaj, vinç, iskele, test/NDT, sigorta, İSG, 3. taraf denetim, eğitim, as-built) | her zaman |
| 5-B | Eşit kapsam düzeltmesi — **ortak boşluk** | **hiçbir** firmanın fiyatlamadığı ama işin gerektirdiği kalemler (çoğunlukla şartname/keşif cetveli onları hiç istemediği için) | dalın kontrol listesinde olup hiçbir teklifte olmayan kalem varsa |
| 6 | Vergisel düzeltme | **indirilemeyen** vergiler (gümrük vergisi/İGV, damga vergisi, SGK yükümlülükleri) toplama girer; **indirilebilir KDV maliyete girmez; indirilemeyen kısmı girer; tevkifat ek vergi değildir** — ayrı satırda nakit akışı olarak durur | yapım/hizmet işinde her zaman; malda fark varsa |
| 7 | Finansman düzeltmesi | NBD − nominal tutar + yalnız alıcının ödediği banka masrafları; avans/kesinti ödeme planında tek kez | her zaman |
| 8 | Ömür boyu maliyet (TCO) | enerji, bakım, yedek parça, sarf, fire, duruş (N yıl, **reel oranla** iskonto edilmiş) | ekipman ömür boyu tüketim yaratıyorsa |
| 9 | Eskalasyon / fiyat rejimi riski | eskalasyonlu ve sabit teklifleri ortak riske getirme (senaryolu) | süre ve fiyat rejimi bunu anlamlı kılıyorsa |
| = | **KARŞILAŞTIRILABİLİR TOPLAM MALİYET (KTM) — indirilebilir KDV hariç** | | |

**5-A / 5-B ayrımı:** 5-A firmaya özgü kapsam farkıdır. 5-B ancak aynı tutar,
para birimi ve ödeme tarihinde bütün seçeneklere ekleniyorsa ortak proje maliyetidir.
Bu koşulda **KTM maliyet sırası değişmez; oransal fiyat puanları sıkıştığı için toplam
puan sırası değişebilir.** Ortak bedel dahil/hariç puan duyarlılığı gösterilir
(`puanlama-metodolojisi.md`). Teknik çözüme göre değişen altyapı, montaj veya işletme
maliyeti, hiçbir firma fiyatlamasa bile eşit dağıtılmaz.

**Muhatap kapsam belgesine göre belirlenir:** şartname istememişse İDARE; açıkça
istemiş ama firmalar fiyatlamamışsa ilgili FİRMALAR; genel dahil beyanı varsa önce teyit.
Rayiç yoksa tutar boş ve **FİYATLANMADI** olur. Ara toplamın adı "bilinen maliyetler
ara toplamı"dır; eksik maliyet sıfırmış gibi nihai KTM ve kesin öneri üretilmez.

**Devre dışı kalan basamak Excel'de "uygulanmadı" olarak gerekçesiyle yazılır, gizlenmez.**
Puanlamada fiyat kriteri **KTM üzerinden** hesaplanır, teklif fiyatı üzerinden değil.

**KTM'nin vergi zemini: indirilebilir KDV hariç.** İndirilemeyen KDV kısmı ve
alıcının gerçekten taşıdığı diğer vergiler maliyete girer; indirim hakkı otomatik
varsayılmaz. İndirilebilir KDV'nin tahsil/mahsup tarihine kadar finansman etkisi ayrı
hesaplanır. Teklifler aynı indirim hakkı ve vergi zeminiyle karşılaştırılır; KDV dahil
fiyat satırın kendi oranıyla ayrıştırılır, genel bir %20 oranı uygulanmaz.
Ayrıntı: `ithalat-maliyet-koprusu.md` §2b ve `hesaplama-kontrolleri.md`.

---

## İş Akışı

### Adım 0 — Anlamadan başlama: soru kapısı (ZORUNLU)

**Analize başlamadan** belirsizlikler toplanır. Kural üçtür:

1. **Belirsizlikler netleştirilir; dayanaksız veri üretilmez.** Kritik belirsizlik
   ilgili kararı engeller; bağımsız envanter, çıkarım ve açık konulu ön analiz sürdürülebilir.
2. **Soruları tek seferde, numaralı ve kısa sor.** Kullanıcıyı adım adım yormak yerine
   bir blok hâlinde: "Başlamadan 4 şeyi netleştirmem gerekiyor: 1) … 2) …"
3. **Cevap gelmeyen soruyu varsayımla geçebilirsin ama sessizce geçemezsin** — varsayımı
   açıkça söyle, Excel'de sarı+mavi işaretle, gerekçesini yaz.

Adım 1'in envanter tablosu çıkarıldıktan sonra tipik olarak şunlar sorulur (yalnız
gerçekten belirsiz olanlar):

- **Dosya rolü belirsizse:** "X dosyası hangi firmanın teklifi / şartname mi?"
- **Alım kapsamı:** kaç kalem/adet alınacak, opsiyonlar dahil mi
- **Şartname yoksa:** elinizde gereksinim listesi veya RFQ metni var mı
- **Para birimi ve kur:** hangi para biriminde karşılaştırılsın; internet erişimi yoksa
  kullanılacak kur ve tarihi
- **Karar ölçütlerinde öncelik:** fiyat mı, teslim süresi mi, kalite/teknik mi, servis mi
- **Finansal parametreler:** iskonto oranı ve teminat komisyon oranı; **vadeli döviz
  ödemesi varsa o para biriminin oranı da** (EUR/USD) — TL oranıyla iskonto edilmez,
  bkz. `finansal-degerlendirme.md` §1b. Bilinmiyorsa varsayılanlar işaretli kullanılır
- **TCO gerekiyorsa:** yıllık çalışma saati, birim enerji fiyatı, değerlendirme ömrü,
  duruş maliyeti ve **yıllık enflasyon beklentisi** (reel iskonto oranı için zorunlu
  girdi, bkz. `tco-omur-boyu-maliyet.md` §3a)
- **Nakit ihtiyacı için:** ödeme/teslim/iade tarihleri; mevcutsa alıma tahsisli nakit
  ve kullanılabilir finansman limiti. Şirketin toplam banka bakiyesi gerekmez.
- **Kalite/stok gerekiyorsa:** hata/iade geçmişi, yeniden işleme ve ikame koşulları;
  tüketim takvimi, başlangıç stok, raf ömrü, MOQ ve sipariş/teslim/depo giderleri.
- **Çıktı:** hızlı/standartta yazılı rapor da isteniyor mu; rapor firma dışına gidecek mi (maskeleme).
  Yüksek güvencede PDF zorunludur; ayrıca tercih sorulmaz.
  Rapor isteniyorsa PDF üretilir; doğrulandıktan sonra ara `.md` silinir — PDF için ayrıca sorulmaz.

**Dosyalar ve amaç açıksa ek iş sorusu sorma. Kullanıcı profil seçmediyse envanterle
birlikte hızlı/standart/yüksek güvence seçimini al.** Gereksiz soru da kullanıcıyı
yorar; ölçü şu: *cevabı bilmeden verilecek karar yanlış olabiliyorsa sor.*

### Adım 0b — Alım dalı ve teklif tipi kapısı

**Dal:** `dosya-tanima-ve-siniflandirma.md` ile içerikten tespit edilir — inşaat/yapım,
makine/ekipman, genel mal/hizmet veya **karma**. Karma ise ilgili tüm referanslar okunur,
kapsam sınırları (ara yüzler) baştan ayrı bir tabloya yazılır. Dal belirlenemiyorsa
"genel mod"da yürünür ve bu Özet'te belirtilir. **Alım dalı dayanaksız olarak belirlenmez.**

**Teklif tipi** (yapım işinde zorunlu, diğerlerinde kapsam karşılığı vardır) analizden önce
tespit edilir ve raporun ilk bulgusudur:
- **Götürü bedel (anahtar teslim):** miktar riski yüklenicide; fiyat farkının bir bölümü
  risk primidir.
- **Birim fiyatlı:** miktar riski işverende; toplam tutar "tahmini keşif toplamı"dır,
  **taahhüt değildir** — bu ayrım Özet'te açıkça yazılır.
- **Karma:** hangi kalem hangi rejimde, tablo hâlinde.

Firmalar **farklı rejimlerde** teklif vermişse bu en kritik bulgudur: doğrudan kıyas
yapılamaz; KTM "ortak rejim varsayımı" üzerine kurulur (hangisi olduğu yazılır) ve RFI'da
tüm firmalardan **aynı rejimde revize teklif** istenmesi önerilir.

### Adım 0c — Teklif sayısı kapısı

**Kaç teklif olduğu varsayılmaz.** Bir tane de olabilir, on iki tane de; yöntem buna göre
değişir çünkü medyan, sapma, sıralama ve duyarlılık belirli sayıların altında **anlamını
yitirir**. `references/teklif-sayisi-modlari.md` okunur ve mod seçilir:

| Bağımsız geçerli tedarikçi | Mod | Kısaca |
|---|---|---|
| **1** | Tek teklif | Karşılaştırma yok → **makullük ve kapsam denetimi** + pazarlık gündemi. Puanlama yapılmaz; Özet'te "TEK TEKLİF — REKABET YOK" uyarısı durur. Maliyet köprüsü yine kurulur |
| **2** | İkili | Medyan/sapma istatistiği yok → **fark analizi**. Anormal düşük teklif testi mutlak alt sınırla yapılır |
| **3–6** | Tam (varsayılan) | Bütün adımlar uygulanır |
| **7+** | Kısa liste | Eleme + KTM hepsine; derin analiz ilk 4-5'e, gerekçesi yazılı ve kullanıcı değiştirebilir |

**İki sayı gösterilir:** bağımsız geçerli tedarikçi ve karşılaştırılabilir seçenek.
Revizyon tek, alternatif ayrı sütundur; aynı firmanın alternatifleri rekabeti artırmaz.
Yukarıdaki mod bağımsız tedarikçi sayısına göre seçilir. Tek firmada birden çok
alternatif varsa seçenek maliyet/uygunluk kıyası yapılır, rekabet puanlaması yapılmaz.
Eleme sonrası sayılar ve mod yeniden belirlenir (`teklif-sayisi-modlari.md`).

Klasörde hiç teklif yoksa analiz başlamaz: envanter tablosu gösterilir, tek soru sorulur.
Şartname tek başına geldiyse yapılacak iş var — gereksinim listesi + teklif isteme kontrol
listesi çıkarmak; bu, sonraki turda gelen tekliflerin karşılaştırılabilir olmasını sağlar.

### Adım 1 — Dosya envanteri, okuma ve sınıflandırma

`references/dosya-tanima-ve-siniflandirma.md` okunur ve uygulanır:
biçime göre okuma → rol sınıflandırması (teklif / şartname / keşif / proje / yazışma /
belge / alakasız) → alım dalı tespiti → **envanter tablosu kullanıcıya gösterilir.**

Bu adımda ayrıca:
- **Veri kaybı kontrolü:** sayfa/tablo/görsel sayısı, boş-metinli sayfa; boş sayfa görsel
  olarak okunur. Taranmış PDF ve JPEG doğrudan görsel olarak okunur ve okunan değerler
  "görselden okundu" kaynağıyla işaretlenir.
- **Bozuk metin tespiti:** `6 65.000,00` = 665.000 gibi hataları firmanın **beyan ettiği
  genel toplamla** çapraz doğrula.
- **Sürüm ve geçerlilik kaydı:** teklif no/tarih/revizyon/geçerlilik bitişi ayrı tabloya.
  Aynı firmanın birden fazla revizyonu varsa yalnız en son değerlendirilir, eskisi
  "değerlendirme dışı" notuyla listede kalır.

  **Tazelik iki ayrı testle ölçülür; ikisi de her zaman çalıştırılır.**

  | Test | Ölçü | Eşik |
  |---|---|---|
  | **Beyan edilen geçerlilik** | teklifte yazan geçerlilik bitişi ↔ analiz tarihi | dolmuş veya <15 gün kalmış → **KRİTİK UYARI** |
  | **Teklifin yaşı** | teklif tarihi ↔ analiz tarihi — **geçerlilik beyanı olsun olmasın** | >60 gün → **KRİTİK UYARI**; 30-60 gün → uyarı |

  **İkinci test birinciye bağlı değildir.** En sık karşılaşılan durum, geçerlilik süresinin
  hiç beyan edilmemesidir: o zaman birinci test sessizce hiç çalışmaz ve **aylarca eski bir
  teklif "sorun görünmeden" analize girer.** Teklif tarihi de yoksa dosya sistemi tarihi
  kullanılır ve bunun dosya tarihi olduğu tabloya yazılır.

  Yaş testi tetiklendiğinde **teklif tarihi bilgi satırı değil, birinci bulgudur:**
  Özet'in KRİTİK UYARI kutusuna, Karar Özeti'nin kırmızı çizgilerine ve RFI'nın 1 numaralı
  maddesine girer. Metin şudur: *"Bu teklif N gün eskidir ve geçerlilik beyanı yoktur;
  imzalı-kaşeli, tarihli ve asgari 30 gün geçerli teyit/revize teklif alınmadan hiçbir sayı
  bağlayıcı değildir."* Analiz durmaz — maliyet köprüsü ve puanlama normal kurulur, ancak
  çıktı **ÖN SONUÇ** etiketi taşır.

  Malzeme fiyatı oynak dallarda (betonarme, çelik, kablo, ambalaj) yaş testi ayrıca
  **9. basamağı (eskalasyon) devreye alır**: senaryolu fiyat güncelleme kurulur ve oranın
  ancak revize teklifle belirlenebileceği yazılır — senaryo, revize teklifin yerine geçmez.

### Adım 2 — Ölçütün belirlenmesi: şartname var mı?

**Şartname (veya keşif cetveli ya da kullanıcının gereksinim listesi) VARSA:**
`references/sartname-gereksinim-cikarimi.md` ile taranır — 19 maddelik ortak çerçeve,
zorunlu↔tercih↔bilgi ayrımı, iç çelişki listesi. Dala karşılık gelen
`ekipman-*.md` / `is-turu-*.md` / `dal-genel-mal-hizmet.md` de bu adımda okunur.
Şartname uzunsa (>15 sayfa) tamamı parça parça okunur, her gereksinim **verbatim alıntı +
madde numarası** ile kaydedilir.

**Şartname YOKSA:** `references/sartname-yoksa.md` okunur ve **şartnamesiz mod** uygulanır.
Özetle: teknik uygunluk matrisi kurulmaz, teknik elemeli kapı uygulanmaz (idari kapı
kalır), kapsam ölçütü tekliflerin birleşiminden türetilen **ortak referans kapsamdır**,
puanlamada teknik uygunluk ağırlığı yeniden dağıtılır ve raporda
**"teknik denklik doğrulanmamıştır"** uyarısı zorunludur.
**Bir firmanın kendi teklifi asla şartname yerine kullanılmaz.**
Kullanıcıya bu durum analiz başlamadan tek cümleyle bildirilir.

### Adım 3 — Teklif verisi çıkarımı ve miktar mutabakatı

**Her teklif için:** teklif no/tarih/revizyon, geçerlilik, para birimi ve KDV durumu,
teklif tipi, Incoterms ve teslim yeri, kalem/poz bazlı miktar × birim × birim fiyat,
iskonto, opsiyonlar, kapsanan adet/metraj, **dahil-hariç listeleri**, ödeme planı, istenen
teminatlar, süre **ve neye bağlı olduğu** (yer teslimi, avans, resim onayı, ruhsat),
garanti, menşe, beyan edilen enerji/verim değerleri, yedek parça fiyat listesi, eskalasyon
talebi, sapma/muafiyet beyanları, referans işler.

**Kritik kontrol — kapsam eşitliği.** Firmalar aynı kalemleri teklif etmemiş olabilir
(9 ekipmandan 6'sını verir; opsiyonu baz fiyata katar; hafriyatı hariç tutar; vinci
"işverence" yazar). Bu durumda fiyatlar **DOĞRUDAN KIYASLANAMAZ** — en kritik bulgu olarak
öne çıkarılır.

**Miktar mutabakatı.** Beyan edilen miktarlar karşılaştırılır (çelik tonajı, beton m³,
kaplama m², ekipman adedi, kg, litre, kişi-vardiya). Referans; keşif/proje metrajı yoksa
beyanların medyanıdır — **medyan yalnız 3 ve üzeri beyanla kullanılır**, iki beyanda iki
senaryo kurulur, tek beyanda referans yoktur ve miktar RFI konusudur. Fark **>%5** ise:
sonuçlar
**"ÖN SONUÇ — mutabakat bekliyor"** etiketiyle sunulur, birincil RFI maddesi miktar
netleştirmesi olur, KTM'nin 3. basamağında tüm teklifler ortak referans miktar × kendi
birim fiyatlarıyla yeniden hesaplanır (tahmin işaretli). Prosedür ve teorik/kantar tonaj
ayrımı: `poz-eslestirme-normalizasyon.md`.

**Hakkaniyet kontrolü.** "Şartnameye uygun imal edilecektir" gibi genel bir beyan varsa,
kalem bazında belirtilmemiş olsa da not edilir. **"Belirtilmemiş" ile "açıkça
hariç/reddedilmiş" farklı şeylerdir** — bu ayrım baştan sona korunur.

**İzlenebilirlik.** Her nicel değerin yanında kaynak referansı bulunur (dosya adı + sayfa
no); her veri tablosunda **"Kaynak" sütunu** açılır. Kaynağı gösterilemeyen değer ya
varsayım olarak işaretlenir ya da yazılmaz.

**Kur çevrimi.** Farklı para birimleri tek para birimine çevrilir. Kaynak **TCMB**'dir:
`https://www.tcmb.gov.tr/kurlar/today.xml` (geçmiş tarih için
`.../kurlar/YYYYMM/GGAAYYYY.xml`), varsayılan **Döviz Satış Kuru**. Kur, tarih ve tür
Excel'de **görünür ve düzenlenebilir hücrelerde** durur; tüm çevrimler ona formülle
bağlanır. **Çevrim `tutar × ForexSelling / Unit` şeklindedir.**
**İnternet erişimi yoksa kur kullanıcıdan istenir — kaynağı belirsiz veya tahmin
kur kullanılmaz.**

**Spot kur yalnız peşin ödeme için yeterlidir.** Vadeli bir döviz ödemesini spot kurla
çevirip TL iskonto oranıyla indirgemek sistematik hatadır ve **ödemeyi öteleyen döviz
teklifini haksız kazandırır**; zincirin 7. basamağında `finansal-degerlendirme.md` §1b
uygulanır (her para birimi kendi oranıyla iskonto edilir veya forward kur kullanılır).

### Adım 4 — Uygunluk değerlendirmesi (şartname varsa)

Her gereksinim × her firma için üçlü sınıflandırma:
- **UYGUN/DAHİL** — yeşil `C6EFCE`, yazı `006100`
- **KISMEN/BELİRTİLMEMİŞ** — sarı `FFEB9C`, yazı `9C6500`
- **UYGUN DEĞİL/EKSİK/HARİÇ** — kırmızı `FFC7CE`, yazı `9C0006`

Her hücreye durum + teklifteki karşılığın kısa özeti yazılır. Şartname yoksa bu adım
atlanır ve atlandığı Özet'te yazılır.
