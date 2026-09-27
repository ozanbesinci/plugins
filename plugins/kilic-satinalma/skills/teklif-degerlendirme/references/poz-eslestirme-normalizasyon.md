# Poz Eşleştirme, Birim Normalizasyonu ve Metraj Mutabakatı

**Dal:** inşaat/yapım işi (kalem bazlı teklif veren makine işlerinde de kullanılabilir).

Yapım işi tekliflerinde firmalar aynı işi farklı poz yapılarıyla fiyatlandırır: biri
"çelik konstrüksiyon imalat+montaj" tek kalem yazar, diğeri imalat/nakliye/montaj/boyayı
dört kaleme böler. Karşılaştırma ancak **ortak bir poz haritası** üzerinden yapılabilir.

## 1. Ana iş grubu haritası

Her firmanın kalemleri aşağıdaki ana gruplara eşlenir. Gruplar projeye göre
daraltılır/genişletilir; kullanılmayan grup tabloda "bu projede yok" olarak kalır
(**silinmez** — kapsam kontrolü için görünür durur):

| # | Ana iş grubu | Tipik birim | Tipik alt kalemler |
|---|---|---|---|
| 1 | Hafriyat ve zemin işleri | m³ | kazı, dolgu, sıkıştırma, zemin iyileştirme, drenaj |
| 2 | Temel ve betonarme | m³ (beton), kg/ton (donatı), m² (kalıp) | grobeton, temel, perde, saha betonu |
| 3 | Ankraj ve saplama | adet / takım | ankraj plakası, kimyasal/mekanik ankraj, aplikasyon |
| 4 | Çelik imalat (atölye) | kg / ton | ana taşıyıcı, tali elemanlar, merdiven-korkuluk, plaka |
| 5 | Yüzey koruma | m² veya kg/ton üzerinden | kumlama (Sa 2½), astar+ara+son kat / sıcak daldırma galvaniz |
| 6 | Nakliye | ton / sefer / götürü | atölye→saha, gabari aşan yük |
| 7 | Saha montajı | kg/ton veya götürü | montaj işçiliği, bulon, saha kaynağı |
| 8 | Vinç ve kaldırma ekipmanı | gün / ay / götürü | mobil vinç, sepetli platform, forklift |
| 9 | Çatı ve cephe kaplama | m² | sandviç panel, trapez, ışıklık, mahya-baca detayları |
| 10 | Yağmur ve tesisat tamamlayıcıları | m / adet | oluk, iniş, dere, kar bariyeri |
| 11 | Geçici tesisler ve genel giderler | götürü / ay | mobilizasyon, şantiye binası, geçici elektrik-su, iskele, İSG organizasyonu, bekçilik |
| 12 | Test, kontrol, dokümantasyon | götürü / adet | NDT, beton numune, ankraj çekme testi, as-built, kalite dosyası |
| 13 | Diğer / projeye özgü | — | kapılar, doğramalar, epoksi zemin, altyapı bağlantısı |

**Eşleştirme kuralları**

- Firmanın tek kalemde birleştirdiği işler (ör. "imalat+montaj ₺/kg") ilgili gruplara
  bölünmeden **"4+7 birleşik"** etiketiyle yazılır; grup bazlı kıyasta bu hücre birleşik
  gösterilir ve dipnotlanır. **Yapay bölüştürme (oran uydurma) YAPILMAZ**; gerekiyorsa
  RFI ile ayrıştırma istenir.
- Hiçbir gruba eşlenemeyen kalem "kapsam dışı/belirsiz" listesine gider ve RFI'ya yazılır.
- Bir grupta **hiçbir firma** kalem vermemişse ve şartname o işi istiyorsa, bu **TÜM
  FİRMALAR için kapsam boşluğudur** — eşit kapsam düzeltmesine tahmini bedelle girer.

## 2. Birim normalizasyonu

- **kg ↔ ton:** tüm çelik kalemleri kg'a indirgenir; ton fiyatı /1000.
- **Boya:** m² bazlı ve kg/ton bazlı teklifler karışabilir. Ortak zemine getirmek için
  yüzey alanı ↔ tonaj dönüşümünde yapının profil kompozisyonuna göre **20-30 m²/ton**
  aralığında bir katsayı kullanılır; katsayı varsayım işaretlenir ve RFI'da firmadan
  kendi hesabı istenir.
- **Kalıp:** m² esası. "Beton m³ fiyatına dahil" diyen firma için kalıp satırı "dahil"
  notuyla boş bırakılır, kıyas beton satırında yapılır.
- **Götürü kalemler:** birim fiyat kıyasına girmez; toplam bazında eşit kapsam tablosunda
  karşılaştırılır.

## 3. Teorik tonaj vs. kantar (tartı) tonajı

Çelik işinde teorik metraj ile ödemeye esas kantar miktarı ayrı girdilerdir.
**Kantar her zaman daha yüksek değildir; %3-7 evrensel fire katsayısı değildir.**
Teslim edilmeyen atölye firesi, sırf kantar esası var diye teslim ağırlığına eklenmez.
Dara, ambalaj, bulon, boya/galvaniz, kaynak ve toleransın dahil/hariç oluşu sözleşmeden
okunur; teorik metrajın aynı kalemleri zaten içerip içermediği kontrol edilir.

`ödenecek kantar kg = ortak net teorik kg × doğrulanmış kantar/net katsayısı`
`kantar teklif toplamı = ödenecek kantar kg × net birim fiyat`

Örnek (katsayı **teyit edilmiş 1,05** ise): 100.000 kg × 30 TL/kg = 3.000.000 TL;
kantar seçeneği 105.000 kg × 30 TL/kg = 3.150.000 TL. Katsayı miktara veya birim
fiyata bir kez uygulanır, ikisine birden uygulanmaz. Katsayı bilinmiyorsa RFI ve
aralık senaryosu açılır; 1,05 otomatik baz yapılmaz. Ödeme esası ve kabul edilen
miktar ölçüm yöntemi sözleşmede açıkça sabitlenir.

## 4. Metraj mutabakat prosedürü

1. **Referans metraj belirle:** (a) idarenin keşif cetveli varsa o; (b) yoksa onaylı proje
   metrajı; (c) o da yoksa firma beyanlarının **medyanı** (TAHMİNİ işaretli).
   **Medyan yalnız 3 ve üzeri beyanla kullanılır.** İki beyan varsa medyan doğrulanmış ihtiyaç değildir:
   iki beyan da gösterilir ve KTM **her iki referansla** hesaplanır (iki senaryo). Tek
   beyan varsa referans yoktur — miktar RFI konusudur, doğrulanmamış olarak işaretlenir
   (bkz. `teklif-sayisi-modlari.md`).
2. Her firmanın beyan miktarı referansla karşılaştırılır; fark % tablo hâlinde gösterilir.
3. **Bütün miktar farklarında** ortak ihtiyaç × geçerli net birim fiyat esas alınır.
   %5 hesap muafiyeti değildir; yalnız uyarı eşiğidir. Sabit mobilizasyon/kurulum gideri
   miktarla çarpılmaz; kademeli fiyat ve MOQ yeniden kontrol edilir.
4. **Fark >%5:** ayrıca metraj uyuşmazlığı bulgusu açılır; sonuçlar
   **"ÖN SONUÇ — metraj mutabakatı bekliyor"** etiketi taşır; **RFI'nın 1 numaralı
   maddesi** metraj netleştirmesidir.
5. Götürü teklifte firma metraj beyan etmemişse zımni birim fiyat türetilemez; RFI ile
   tonaj/metraj beyanı istenir, o gelene dek firma "metraj beyansız" işaretlenir.

## 5. Poz bazlı sapma ve dengesiz teklif analizi

**Asgari teklif sayısı:** medyan tabanlı testler **3 geçerli teklifle** başlar; N≥7'de en
güçlüdür. İki teklifte medyan kurulmaz, yerine **doğrudan fark tablosu** (kalem × A × B ×
fark tutarı ve % × farkın açıklaması) yazılır. Tek teklifte bu bölümün karşılaştırmalı
kısmı uygulanmaz — yalnız aşağıdaki **mutlak** alt sınır testi geçerlidir.

Her ana grupta (birleşik kalemler kendi kategorisinde) firma birim fiyatları için
**MIN / MEDYAN / MAX** hesaplanır.

- **Sapma renklendirmesi:** medyandan ±%15-30 sarı, ±%30 üzeri kırmızı-vurgulu. Sapan her
  hücreye kısa yorum: kapsam farkı mı (bir şey dahil/hariç), kalite farkı mı, fiyatlama
  stratejisi mi.
- **Dengesiz teklif (front-loading) deseni:** iş programının ilk %30'luk dilimine düşen
  pozlarda (hafriyat, temel, ankraj, mobilizasyon) medyan **ÜSTÜ** ve son dilim pozlarında
  (montaj sonu, kaplama, test) medyan **ALTI** fiyatlayan firma işaretlenir. Yorum: nakit
  öne çekme; birim fiyatlı sözleşmede iş eksilişi/fesih hâlinde işveren aleyhine sonuç
  doğurur. Karar Özeti'nde uyarı + sözleşme önerisi (hakediş kesinti oranını artırma veya
  ödeme planını iş programına bağlama).
### Anormal düşük teklif — iki test

**Hiçbiri eleme sebebi değildir.** İkisi de aynı sonucu verir: açıklama talebi RFI'ya
yazılır, risk matrisine "yarıda bırakma / kalite düşürme riski" olarak girer ve panzehir
sözleşmededir (hakediş kesintisi + kesin teminat).

**Test A — mutlak alt sınır (ham malzeme fiyatı gerektirir).**

| Dal | Ölçü | Alt sınır |
|---|---|---|
| **Çelik** | imalat+montaj ₺/kg | ham profil/sac ₺/kg × **1,6-1,8** |
| **Betonarme — beton** | ₺/m³ (döküm dahil) | hazır beton ₺/m³ × **1,25-1,45** (pompa, vibrasyon, kür, fire) |
| **Betonarme — donatı** | ₺/kg (yerinde) | ham nervürlü demir ₺/kg × **1,20-1,35** (kesme-bükme-bağlama, fire) |
| **Betonarme — kalıp** | ₺/m² | malzeme payı küçük, **işçilik baskın** → mutlak sınır güvenilir değil, Test B kullan |

Tablodaki katsayılar yaklaşık tarama senaryolarıdır; kanıtlanmış maliyet tabanı veya
eleme eşiği değildir. Kapsam, tarih ve üretim yöntemiyle teyit edilir.

Ham fiyat kullanıcıdan alınır veya güncel piyasa değeriyle **varsayım işaretli** girilir.
**Ham fiyat yoksa bu test yapılmaz ve "yapılamadı" yazılır** — uydurma rayiçle alt sınır
kurulmaz.

**Test B — yakınsama testi (dış fiyat gerektirmez, N≥3).** Rakip tekliflerin kendisi
referanstır:

```
aynı kapsam/miktarda bağımsız diğer firmalar: MAX(diğer)/MIN(diğer) − 1 ≤ %5
ve (AVERAGE(diğer) − aday) / AVERAGE(diğer) ≥ %15 ise
→ ANORMAL DÜŞÜK SİNYALİ
```

Gerekçe: birbirinden bağımsız iki veya daha fazla firmanın **%5 içinde buluşması**,
tek başına piyasa fiyatını kanıtlamaz, yalnız açıklama isteme sinyalidir; üçüncünün ondan belirgin
sapması ancak (a) gerçek bir maliyet avantajıyla, (b) daha dar bir kapsam anlayışıyla veya
(c) sürdürülemez fiyatlamayla açıklanabilir — üçünü ayırt eden tek şey **birim fiyat
tahlilidir.**

Bu test **kapsamın eşit olduğu durumlarda en güvenilirdir** (ortak keşif cetveli, aynı
miktarlar); kapsam eşit değilse önce basamak 5-A uygulanır, test sonra çalıştırılır.
Yakınsama %5'ten genişse test **kurulmaz** — iki dağınık teklif referans üretmez.

**İki test birlikte okunur.** Test A geçip Test B tetikleniyorsa yorum "fiyat matematiksel
olarak mümkün ama piyasadan ayrışıyor"dur; ikisi birden tetikleniyorsa risk skoru yükseltilir.

Sinyal tetiklendiğinde istenecek şey nettir: sapmanın büyük olduğu pozlar için
**birim fiyat tahlili** (malzeme + işçilik + ekipman dökümü) ve iş programı.

## 6. Eşit kapsam kontrol listesi (inşaat)

Aşağıdaki kalemlerin her teklifte dahil/hariç/belirtilmemiş durumu tablolanır; hariç veya
belirtilmemiş olanlar **tahmini bedelle** eşit kapsam düzeltmesine girer:

vinç ve kaldırma ekipmanı · iskele · mobilizasyon/demobilizasyon · şantiye binası ve
geçici tesisler · geçici elektrik-su ve sarfiyatları · bekçilik/güvenlik · all-risk (CAR)
sigortası · 3. şahıs mali mesuliyet · İSG uzmanı ve organizasyonu · SGK bildirimleri ·
NDT ve test bedelleri · beton numune/karot · 3. taraf denetim · as-built ve kalite
dosyası · nakliye · gabari izinleri · atık/moloz nakli · saha temizliği · kesin kabule
kadar bakım
