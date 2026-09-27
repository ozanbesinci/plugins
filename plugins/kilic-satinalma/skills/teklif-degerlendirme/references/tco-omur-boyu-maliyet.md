# Ömür Boyu Maliyet (TCO / Life Cycle Cost)

Satın alma fiyatı tek başına yeterli değildir. Enerji veriminin fiyat farkını kapatıp
kapatmadığı kullanım süresi, tüketim ve birim fiyatla hesaplanır. Bu modül teklifleri
**işletme maliyetiyle birlikte** kıyaslar.

## 1. Gerekli parametreler

Dosyalardan çıkmıyorsa kullanıcıya sorulur; yine yoksa aşağıdaki varsayılan kullanılır ve
**varsayım olarak işaretlenir**.

| Parametre | Kaynak | Varsayılan (işaretlenerek) |
|---|---|---|
| Değerlendirme ömrü (yıl) | Kullanıcı / şartname | 10 yıl (proses ekipmanı), 15 yıl (tank/yapısal), 7 yıl (paketleme/otomasyon ağırlıklı hat) |
| Yıllık çalışma saati | Kullanıcı | 6.000 / 8.000 h yalnız senaryo; vardiya × saat × çalışma günü ile doğrulanır |
| Birim elektrik fiyatı | Kullanıcı — fatura | Sanayi ortalaması; **tahmin edilmez, kullanıcıdan alınmalı** |
| İskonto oranı | Kullanıcı / finans | Kaynağı `finansal-degerlendirme.md` ile aynıdır, ama **cinsi akışla eşleşmek zorundadır** — bkz. §3a. Sabit (bugünkü) fiyatlarla kurulan tabloda **reel oran** kullanılır |
| Yıllık enflasyon / fiyat artışı | Kullanıcı | **Sessizce sıfır varsayılamaz.** Kullanıcıdan gelen %0 geçerlidir. Reel orana geçmek için gerekli girdidir (§3a); alınamazsa varsayım işaretlenir ve duyarlılık satırı kurulur |
| Duruş maliyeti (TL/saat) | Kullanıcı | Sorulmadan tahmin edilmez; bilinmiyorsa duruş kalemi sıfırlanır ve "hesaba katılmadı" yazılır |

## 2. Maliyet kalemleri

**a) Enerji.** `yıllık enerji (kWh) = ortalama elektrik giriş gücü (kW) × çalışma saati`;
`yıllık enerji maliyeti = kWh × TL/kWh`. Kurulu güç × yük faktörü yalnız giriş gücü
bilinmediğinde işaretli yaklaşımdır. Motor etiketindeki mil gücü kullanılıyorsa
motor/sürücü verimi ayrıca hesaba katılır; ölçülmüş elektrik girişine tekrar bölünmez.
Firmaların beyan ettiği güç değerleri farklıysa (aynı iş için 30 kW ve 37 kW), fark
doğrudan bu satıra yansır. Verim eğrisi/verim sınıfı verilmişse (IE3/IE4, pompa verimi)
nominal güç yerine **gerçek çekilen güç** kullanılır. Beyan yoksa RFI'ya "garanti edilen
tüketim değeri" sorusu eklenir ve satır varsayımla doldurulur.

**b) Diğer enerji/sarf:** buhar, basınçlı hava, soğutma suyu, azot, yağ, filtre, kesici
takım, conta/salmastra, bant/kayış.

**c) Planlı bakım.** Üreticinin bakım planındaki periyodik işler: parça + işçilik. Firma
bakım sözleşmesi teklif ediyorsa yıllık bedeli buraya girer. Servis teknisyeni günlük
ücreti ve yol/konaklama, servis ağının mesafesine bağlıdır
(bkz. `tedarikci-yeterlilik-risk.md`).

**d) Yedek parça.** Firmanın verdiği yedek parça fiyat listesi ile 1-2 yıllık önerilen
stok. **Kritik:** aynı parçanın firmalar arasındaki fiyat farkı (bir firmanın makinesi ucuz
ama yedek parçası 3 kat pahalı) burada ortaya çıkar. Muadil parça kullanılabilir mi, yoksa
üreticiye bağımlılık mı var — ayrıca not edilir.

**e) Verim/kapasite farkı.** Bir teklif şartname kapasitesinin üstünde, diğeri sınırdaysa:
fazladan kapasite değer mi, atıl kapasite mi? Zorunlu asgari kapasitenin altı elemedir; maliyet eklemekle uygun hale gelmez.
Onaylı farklı kapasite alternatifleri ancak aynı ihtiyacı karşılayacak ünite/adet ve
kullanım programıyla kıyaslanır.

**f) Öngörülen duruş.** yıllık beklenen arıza saati × duruş maliyeti (TL/h). Müdahale süresi toplam
onarım/duruş süresi değildir; arıza sıklığı, teşhis, parça, onarım ve yeniden devreye
alma ile yedek ekipman/ara stok etkisi birlikte değerlendirilir. Duruş maliyeti bilinmiyorsa
sıfırlanır ama "servis müdahale süresi farkı parasallaştırılmadı, niteliksel kriter olarak
puanlamada yer aldı" notu düşülür.

**g) Ömür sonu / hurda değeri** — varsa negatif kalem olarak son yıla yazılır (genelde
ihmal edilebilir; ihmal edildiği yazılır).

## 3. Hesap yöntemi

Excel'de yıl bazlı tablo: satırlar = kalemler, sütunlar = 1..N yıl. Her yılın toplamı
iskonto edilir:

```
NBD = Σ ( yıl_t toplam işletme maliyeti / (1 + iskonto)^t )
```

`=NPV()` **yerine** dönem bazlı açık formül (`=E12/(1+$B$4)^E$3`) kullanılır; okunabilir ve
doğrulanabilir olur.

### 3a. Oranın cinsi akışın cinsine uymak zorundadır

Bu modülün en kolay yapılan ve **modülü işlevsiz bırakan** hatası: işletme maliyetlerini
bugünün fiyatlarıyla sabit yazmak, ama **nominal** iskonto oranıyla (TL fon maliyeti,
TLREF düzeyi) indirgemek. Yüksek enflasyonlu para biriminde bu, ömür boyu maliyeti
neredeyse yok eder:

```
1.000.000 TL/yıl işletme maliyeti · 10 yıl · nominal oran %40 · enflasyon %30

YANLIŞ (nominal oran + sabit akış) : 2.413.571 TL  → yalnız 2,41 yıllık maliyet
DOĞRU  (reel oran + sabit akış)    : 6.804.212 TL  → 6,80 yıl
→ ömür boyu maliyet %64,5 eksik gösterilir
```

**İki tutarlı yol var; biri seçilir ve hangisi seçildiği tabloya yazılır:**

| Yol | Akış | Oran | Ne zaman |
|---|---|---|---|
| **A — reel (varsayılan)** | bugünkü fiyatlarla sabit | **reel** oran | Kalemlerin hepsi genel enflasyonla birlikte hareket ediyorsa; daha az girdi ister |
| B — nominal | her yıl enflasyonla artırılmış | nominal oran | Bir kalem farklı hızda artıyorsa (elektrik tarifesi, sözleşmeli bakım bedeli) — kalem bazlı artış oranı girilebilir |

```
reel oran:  r_reel = (1 + r_nominal) / (1 + π) − 1        (π = yıllık enflasyon)
örnek:      (1 + 0,40) / (1 + 0,30) − 1 = 0,0769 → %7,69
```

**Yaygın yanlış:** `r_nominal − π` (= %10) çıkarma yoluyla hesaplamak. Yukarıdaki örnekte
6.144.567 TL verir — doğrusundan %9,7 aşağıda. Düşük oranlarda yakın, yüksek enflasyonda
sapma büyür; **bölme formülü kullanılır.**

**Excel'de:** `r_nominal`, `π` ve `r_reel` üç ayrı görünür hücredir; `r_reel` formülle
(`=(1+B4)/(1+B5)-1`) kurulur, elle yazılmaz. İskonto satırı hangi hücreye bağlıysa
başlıkta görünür: "iskonto oranı (reel)".

**Ödeme planı NBD'siyle ilişki:** `finansal-degerlendirme.md` §1 ödeme planını **nominal**
tutarlarla ve nominal oranla kurar — orada akış da nominaldir, tutarlıdır. Bu iki modül
farklı oran **cinsi** kullanabilir; koşul, her modülün kendi içinde tutarlı olması ve
**bunun yazılı olmasıdır.** Aynı sayı iki modülde farklı görünüyorsa gerekçesi not edilir.

Enflasyon varsayımı sonucu doğrudan etkilediği için TCO tablosunda **π için duyarlılık
satırı** kurulur (ör. %20 / %30 / %40) ve sıralamayı değiştirip değiştirmediği yazılır.

**KTM'ye katkı** = işletme maliyetlerinin NBD'si. Bu değer Özet sekmesindeki maliyet
köprüsü zincirinin **8. basamağına** formülle bağlanır.

## 4. Sunum kuralları

- Satın alma maliyeti ve ömür boyu maliyet **ayrı ayrı ve toplam olarak** gösterilir;
  hangisinin sıralamayı değiştirdiği açıkça yazılır.
- Enerji tüketimi beyanları **garanti mi, gösterge mi?** Garanti değilse TCO sonucu "beyan
  esaslı, garanti altına alınmamış" uyarısıyla sunulur ve RFI'da garanti + ceza koşulu
  istenir.
- **Başabaş süresi hesapla:** daha pahalı ama verimli teklifin fiyat farkını kaç yılda geri
  ödediği. Tek satırlık bu bilgi karar toplantılarında en çok işe yarayan çıktıdır.
- Ekipman enerji/bakım tüketmiyorsa (basit yapısal imalat, depo rafı, çelik konstrüksiyon)
  modül **"uygulanmadı"** işaretlenir; gerekçesi yazılır.

## 5. Ortak ömür ve başabaş hesabı

- Bütün seçenekler aynı analiz ufku ve aynı faydalı çıktıyla kıyaslanır. Ömrü kısa
  seçenekte yenileme/değişim yatırımı ve ömür sonu değerleri kendi tarihlerine yazılır.
  Teslim/devreye alma tarihleri farklıysa işletme akışları aynı değerleme tarihine
  indirgenir; gecikme nedeniyle üretilemeyen fayda görünür olur.
- Başlangıç yedek parça stoğu ile yıllık tüketilen parçalar çift sayılmaz; kullanılan
  başlangıç stoğu ilk yıl yeniden satın alınmış gibi yazılmaz. Hurda geliri eksi,
  söküm/bertaraf maliyeti artıdır; ikisi de son tarihe iskonto edilir.
- Sabit bugünkü maliyet C0 için nominal yol `C0 × (1+enflasyon)^t`; reel yol sabit
  C0 ve `(1+r_nom)/(1+enflasyon)−1` oranı. Verilen tutar zaten birinci yıl nominal
  bedelse yeniden bir yıllık enflasyon eklenmez.
- Basit geri ödeme = ek ilk yatırım / yıllık net tasarruf (sabit ve pozitifse).
  İskontolu geri ödeme, yıllık tasarrufların kümülatif NBD'sinin ek yatırım NBD'sini
  ilk aştığı tarihtir. Değişken tasarrufta kümülatif tablo kullanılır. Tasarruf ≤0
  veya ufuk boyunca fark kapanmıyorsa **geri ödeme yok / analiz ufkunda yok** yazılır.
- Duruş kaybında satış cirosu otomatik zarar değildir: kayıp katkı payı, telafi
  üretimi, fazla mesai ve ilave giderlerden dayanaklı değer kurulur. Aynı kayıp
  teslim/servis puanında yeniden cezalandırılmaz.
