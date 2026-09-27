# Finansal Değerlendirme — Ödeme/Hakediş Planı NBD, Teminat Maliyetleri, Eskalasyon, Kur Riski

İki teklif aynı tutarda olabilir ama biri %50 avans + teslimde bakiye, diğeri %20 avans +
kabulden 90 gün sonra bakiye isteyebilir; biri %30 avans + aylık hakediş, diğeri avanssız +
kabul sonrası ödeme isteyebilir. **Bunlar aynı fiyat değildir.** Bu modül farkı
parasallaştırır.

## 1. Ödeme/hakediş planının net bugünkü değeri

Her firmanın ödeme planını dönemlere ayır:
- **Makine/ekipman:** t=0 (sipariş/avans), imalat hakedişleri, sevkiyat, saha teslim,
  kabul/devreye alma, garanti sonu bakiyesi.
- **Yapım işi:** t=0 (sözleşme/avans), aylık veya imalat-bazlı hakedişler, geçici kabul
  ödemesi, kesin hesap, teminat kesintilerinin iadesi (kesin kabulde).

```
Ödeme NBD = Σ ( ödeme_t / (1 + i)^t )
```

- `i` = işverenin/alıcının kendi fon maliyeti veya alternatif getiri oranı. Kullanıcıdan
  alınır; alınamazsa güncel TL mevduat/TLREF düzeyine yakın bir oran **açık varsayım**
  olarak işaretlenir.
- **Her para birimi kendi oranıyla iskonto edilir — bu kural ihlal edilirse analiz
  sistematik olarak yanlış firmayı seçer.** Ayrıntı: aşağıdaki "1b" bölümü. Tüm firmalar
  **aynı yöntemi** ve aynı TL oranını kullanır, ama döviz cinsi akışa TL oranı
  uygulanmaz.
- **t=0 ödemesi iskonto edilmez.** Excel'de `=NPV()` kullanılmaz; dönem bazlı açık formül
  (`=tutar/(1+oran)^dönem`) yazılır.
- Dönem birimi **ay** (teslim süreleri farklı olduğu için); yıllık oran verilmişse
  `(1+i_yıl)^(1/12)-1` ile aylığa çevrilir ve dönüşüm **görünür hücrede** gösterilir.
- Hakediş ödemeleri iş programına dağıtılır; firma iş programı vermemişse doğrusal dağılım
  varsayılır (varsayım işaretli).

**Çıktı:** nominal tutar ve NBD ayrı sütunlardır. İşaret kesindir:
`finansman düzeltmesi = ödeme NBD'si − aynı ödemelerin nominal toplamı`.
Bu fark 7. basamağa eklenir; pozitif iskonto oranında vadeli ödeme düzeltmesi negatiftir.
NBD'nin tamamı nominal bedelin üstüne eklenmez. Ödeme planına yalnız satıcı bedeli
konmuşsa nakliye/vergi/diğer alımların ayrı ödeme tarihleri de hesaplanır; satıcı
vadesi bütün giderlere uygulanmaz. Bütün teklifler aynı değerleme tarihine getirilir.
Kesin tarihler biliniyorsa `t = (ödeme tarihi − değerleme tarihi).gün / 365` ve yıllık
efektif oran kullanılır; aylık yöntemde yıllık oran doğrudan aylık üsse konmaz.
Yıllık efektif oran ile bankanın basit/nominal faiz kotasyonu birbirine karıştırılmaz.
Tam mutabakat: `hesaplama-kontrolleri.md` §3.

## 1b. Döviz cinsi ödemelerde iskonto — sık yapılan ve tek yönlü hata

Döviz cinsi bir ödemeyi **spot kurla TL'ye çevirip TL iskonto oranıyla** indirgemek,
"TL hiç değer kaybetmeyecek" demekle aynı şeydir. Bu hata her zaman aynı yöne çalışır:
**ödemeyi öteleyen döviz teklifini haksız kazandırır.**

```
A: 4.500.000 TL peşin   |   B: 100.000 EUR, 12 ay sonra
(spot 45,00 · TL oranı %40 · EUR oranı %4)

YANLIŞ: 100.000 × 45,00 = 4.500.000 → /1,40 = 3.214.286 TL   → "B %29 ucuz"
DOĞRU : 100.000 / 1,04  =   96.154 € → ×45,00 = 4.326.923 TL   → B %3,8 ucuz
hata: 1.112.637 TL (%35) — sıralamayı ve kararı değiştirir
```

**Kural (iki yol — seçilen yöntem ve oranların dayanağı yazılır):**

1. **Kendi para biriminde iskonto et, sonra çevir** (varsayılan; daha az girdi ister)
   `NBD_TL = Σ [ ödeme_t(döviz) / (1 + i_döviz)^t ] × spot kur`
   `i_döviz` = alıcının aynı para birimindeki fon maliyeti; piyasa göstergesi ancak
   bu maliyet bilinmiyorsa işaretli bir yaklaşım olarak kullanılır;
   kullanıcıdan alınır, alınamazsa varsayım işaretlenir.
2. **Forward kurla çevir, sonra TL oranıyla iskonto et**
   `F_t = spot × (1 + i_TL)^t / (1 + i_döviz)^t` → `NBD_TL = Σ [ ödeme_t × F_t / (1 + i_TL)^t ]`
   Bankadan aynı vade/tutar için uygulanabilir forward kotasyonu varsa ayrı korunma
   senaryosu kurulur. Teorik iki yol yalnız yukarıdaki faiz paritesi formülüyle aynıdır;
   gerçek kotasyon marj/masraf içerdiğinde eşitlik beklenmez. Forward kuru tahmin edilen
   gelecek spot kur değildir. Fiyata gömülü forward maliyeti ayrıca eklenmez.
   Yukarıdaki örnekte teorik 12 ay forward kuru 60,576923'tür.

**Excel'de:** her para birimi için ayrı bir oran hücresi açılır (`i_TL`, `i_EUR`, `i_USD`),
firma satırı hangi hücreye bağlıysa görünür durur. Aynı para biriminde ödeme yapan tüm
firmalar **aynı** oran hücresine bağlanır.

**Peşin ödemede fark yoktur** (t=0 iskonto edilmiyor); hata yalnız **vadeli** döviz
ödemesinde doğar — avans/bakiye yapısı farklı olan tekliflerde mutlaka kontrol edilir.

Bu hesap kur **riskini** ortadan kaldırmaz; riskin parasallaştırılması ve duyarlılık
senaryoları için bkz. §6.

## 2. Hakediş teminat kesintileri (yapım işine özgü)

Hakedişlerden yapılan kesintiler (tipik **%5-10** "teminat kesintisi"/alıkonma, kesin
kabulde iade) firmanın nakit akışını, dolayısıyla fiyatını etkiler; işveren açısından ise
iade edilene kadar faizsiz güvencedir.

- Her firmanın kabul ettiği kesinti oranı ve iade zamanı tabloya yazılır.
- NBD hesabında kesintiler ödeme akışından düşülür, **iade tarihi ayrı bir pozitif akış**
  olarak eklenir.
- Kesintiyi reddeden veya çok düşük kabul eden firma, **yüksek avansla birleşiyorsa** risk
  göstergesi olarak işaretlenir.

## 3. İş bitmeden ödenen pay (risk göstergesi)

**teslim/geçici kabul öncesi ödenen toplam / sözleşme bedeli.** Oran ne kadar yüksekse
işveren riski o kadar yüksektir (yarıda bırakma, teslim etmeme, iflas). Bu **maliyet değil
risk göstergesidir**; parasallaştırılmaz, risk matrisine ve Ticari Koşullar yorumuna girer.

Yüksek avans karşılığında **avans teminat mektubu zorunlu** kabul edilir —
**avans teminatsız yüksek avans kırmızı çizgi adayıdır.**

## 4. Teminat mektubu ve akreditif komisyon maliyetleri

Yüklenicinin/satıcının verdiği teminatlar (geçici, kesin/performans — yapım işinde %6
tipik, avans, garanti dönemi) **onun** maliyetidir ve fiyata yansımıştır. İşverenin/alıcının
kendi vereceği güvenceler (ödeme garantisi, akreditif) **işveren** maliyetidir ve tekliften
teklife farklılaşır:

**Komisyon yöntemi banka kotasyonundan alınır.** Her ürünün üç aylık ve her
başlayan dönemin tam ücretli olduğu varsayılamaz. Ürün, matrah, oran, minimum ücret,
faturalama dönemi, başlangıç/bitiş tarihi ve BSMV/istisna bilgisi ayrı girdidir.

- **Başlayan takvim çeyreği tam** koşulunda üç aylık tarih dilimleri sayılır;
  `CEILING(gün/90)` takvim ayı sözleşmesinin yerine geçmez.
- **Günlük oransal** koşulunda `matrah × yıllık basit oran × gün / gün_esası`;
  gün esası (360/365) kotasyondan alınır.
- **Dönemlik** koşulunda her dönem `MAX(matrah_dönem × dönem_oranı, asgari_dönem_ücreti)`;
  bir defalık açılış/mesaj/teyit giderleri ayrıca, bir kez eklenir.
- Yıllık oran ancak kotasyon basit yıllık komisyon tarif ediyorsa `/4` ile çeyreğe
  çevrilir. Efektif faiz dönüşümü bununla aynı değildir.
- Vergi yükü `vergiye tabi komisyon × teyitli BSMV oranı`dır; oran ve istisna
  işlem bazında kontrol edilir. Bilinmeyen oran otomatik %5 yapılmaz.

**Koşullu hesap örneği:** 1.000.000 TL matrah, 7 ay, başlayan 3 aylık dönem tam,
dönem komisyonu %0,5, örnek BSMV %5 ve minimum ücret yoksa:
`3 × 1.000.000 × 0,005 × 1,05 = 15.750 TL` nominal yük.
Bu oranlar örnektir, güncel banka teklifi veya vergi hükmü değildir.

Teminat süresi her belgenin kendi geçerlilik ve çözülme tarihinden alınır; bütün
teminatlara teslim + garanti otomatik eklenmez. Her komisyon kendi ödeme tarihinde
iskonto edilir. **Satıcının verdiği teminatın anaparası satınalma gideri değildir**;
alıcıya ayrıca fatura edilmeyen satıcı komisyonu da KTM'ye eklenmez.
Bloke/depozito: çıkış (+), çözülme/iade (−) akışlarının NBD'si alınır; aynı
anaparaya ayrıca fırsat maliyeti eklenmez.

Kaynak kontrolü (2026-09-05): [İş Bankası ücret tarifesi](https://www.isbank.com.tr/urun-ve-hizmet-ucretleri)
ürün türüne göre dönem ve asgari ücret ayrımı yapar; geçici mektuplarda ilk ay,
kesin/avans mektuplarında üç aylık dönem bilgisi vardır. İşlemde güncel kotasyon esastır.

Hesaplanacak kalemler:
- **Akreditif (L/C)** açılış + teyit komisyonu, swift/masraf, vadeli L/C ise iskonto
  maliyeti — özellikle ithal tekliflerde. **Peşin havale isteyen firma ile L/C kabul eden
  firma arasındaki fark buradan çıkar.**
- Alıcının verdiği banka teminat mektubu varsa komisyonu ve gayri nakdi kredi limiti
  kullanımı.
- Bloke/depozito isteniyorsa alternatif getiri kaybı.

Oranlar bankaya ve firmanın limitine bağlıdır; kullanıcıdan alınır, alınamazsa varsayım
işaretlenir. **Bu satır küçük görünse de iki teklif arasındaki farkı tersine
çevirebilir** — mutlaka gösterilir.

## 5. Eskalasyon / fiyat farkı analizi (KTM 9. basamak)

Üç fiyat rejimi görülür:

1. **Sabit fiyat, eskalasyonsuz:** kısa işlerde normal; uzun işte (>4-6 ay) firma ya risk
   primi gömmüştür ya da yarı yolda revizyon talebi/uyuşmazlık riski taşır. Not düşülür.
2. **Endeksli eskalasyon / fiyat revizyon maddesi:** TÜİK inşaat maliyet endeksi, çelik
   için LME/piyasa+kur formülü, makinede "kur %5'ten fazla artarsa fiyat güncellenir" veya
   hammadde endeksi. Formülün **tabanı** (hangi ay), **eşiği** (%X üstü mü), **kapsamı**
   (tüm bedel mi malzeme payı mı) ve **tavanı** çıkarılır.
3. **Döviz cinsi teklif:** kur riski işverendedir (aşağıdaki bölüm).

**Ortak zemine getirme:** kullanıcıdan alınan senaryo (ör. "iş süresince endeks %X artar") ile
her rejimin senaryo maliyeti hesaplanır ve KTM'ye girer; hesap varsayım işaretlidir ve
**%0 / %X / %2X üç senaryolu duyarlılık satırı** gösterilir.

Eskalasyonlu/fiyat revizyonlu teklif Özet'te **"fiyatı sabit değildir"** uyarısı taşır —
bu bir eleme değil, şeffaflık notudur; eskalasyonsuz ama gerçekçi olmayan ucuz teklif daha
riskli olabilir.

## 6. Kur riski

- Döviz cinsi teklifte spot **TCMB DSK** ile hesapla (ana `SKILL.md` kuralı) ve
  **iki yönlü** duyarlılık satırı ekle: **kur −%10 / −%20 / baz / +%10 / +%20**. Tek yönlü
  senaryo (yalnız artış) analizi tek tarafa yatırır: TL teklif her zaman kazanan görünür,
  oysa kur gerilerse döviz teklifi öne geçer. Her senaryoda firmaların KTM'si **ve
  sıralaması** yazılır; sıralamanın hangi kur seviyesinde değiştiği ("başabaş kur") tek
  satırla belirtilir — karar toplantısında en çok işe yarayan çıktı budur.
- **"TL teklif kur riskinden muaf" varsayımı kontrol edilir:** TL teklifin fiyat revizyon
  maddesi kura endeksliyse (ör. "kur %5'ten fazla artarsa fiyat güncellenir") o teklif de
  kur riski taşır ve duyarlılık satırında **sabit gösterilmez.** Endeksli TL teklif ile
  döviz teklifi arasındaki fark, eşiğin ve tavanın olup olmamasıdır.
- Sözleşmede kur sabitleme/tavan yoksa risk işverendedir; forward/hedge maliyeti
  biliniyorsa alternatif olarak gösterilir.
- Kur maddesinde **hangi kur** (TCMB DSK mı) ve **hangi tarih** (fatura, sevk, ödeme) esas
  alınıyor — bu tek kelime ciddi tutar farkı yaratır.

## 7. Vergi ve nakit akışı notları

- **KDV** indirim hakkına göre ayrılır: indirilemeyen kısım maliyet, indirilebilir
  kısım ödeme/mahsup veya iade tarihlerine bağlı nakit akışıdır. Teşvik istisnası
  yalnız geçerli belge, ürün ve işlem kapsamı teyit edilince uygulanır.
- **KDV tevkifatı (işlem, alıcı statüsü ve güncel oran teyit edilerek):** işveren KDV'nin bir kısmını doğrudan vergi
  dairesine öder; firma bazında fatura düzeni farkı varsa nakit akışına yansıtılır.
- **Damga vergisi** sözleşme bedeli üzerinden doğar; oranı ve kimin ödeyeceği tekliflerde
  farklılaşabilir, karşılaştırmaya girer.
- **SGK teminatı:** kesin kabul/teminat iadesi öncesi **ilişiksizlik belgesi** şartı
  hatırlatılır (bkz. `sozlesme-maddeleri.md`).
- Vergisel konularda **mali müşavir teyidi şarttır**; bu skill vergi danışmanlığı yerine
  geçmez ve ilgili hücreler "teyit bekleniyor" işaretlenir.

## 8. Doğrulama

1. Dönem birimi tüm firmalar için aynı mı; **aynı para biriminde** ödeme yapan firmalar
   aynı oran hücresine mi bağlı?
2. **Döviz cinsi vadeli ödeme, TL oranıyla iskonto edilmiş mi?** Edilmişse hatadır —
   §1b'deki iki yoldan biri uygulanır ve hangisi kullanıldığı yazılır.
3. t=0 ödemesi iskonto edilmemiş mi?
4. Avans + net hakediş + kesinti iadesi toplamı sözleşme bedeline eşit mi;
   hakedişlerden avans mahsubu ve kesinti bir kez düşülmüş mü?
5. Teminat süreleri belgenin gerçek başlangıç, bitiş ve çözülme tarihleriyle tutarlı mı?
6. Eskalasyon senaryosu tüm eskalasyonlu tekliflere **aynı** endeks artışıyla mı
   uygulanmış?

## 9. Nakit ihtiyacı bağlantısı

Ödeme takvimi kurulduğunda `nakit-kalite-stok.md` §1 uygulanır: NBD yanında nominal
tepe nakit ihtiyacı ve tarihi gösterilir. Tahsisli nakit/limit biliniyorsa ek
finansman ihtiyacı hesaplanır; bilinmiyorsa şirketin ödeme gücü hakkında hüküm verilmez.
