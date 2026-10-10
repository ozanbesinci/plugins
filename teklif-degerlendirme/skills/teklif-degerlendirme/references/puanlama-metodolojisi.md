# Puanlama Metodolojisi — Elemeli Kapı, Normalizasyon, Duyarlılık

**Sıra kesindir:** (1) elemeli kapı → (2) ağırlıklı puanlama → (3) duyarlılık kontrolü.
Bu sıra bozulursa uygunsuz ama ucuz bir teklif ağırlıklı puanla birinci çıkabilir.

## 0. Kaç teklif varsa ona göre (önce bu)

Bu dosyanın yöntemi **2 ve üzeri bağımsız geçerli tedarikçi** varsayar; alternatifler
rekabet sayısını artırmaz (`teklif-sayisi-modlari.md`). Sayı farklıysa
`teklif-sayisi-modlari.md` esastır:

- **Tek teklif:** puanlama **yapılmaz.** Tek teklife tam puan vermek, olmayan
  bir sıralamaya gerekçe üretir; normalizasyon formülleri de (`MIN(tüm KTM)/firma_KTM`)
  zorunlu olarak 10 verir — anlamsız bir tam puan. Yerine **eşik değerlendirmesi**:
  elemeli kapıdan geçti mi, kırmızı çizgiler karşılanıyor mu, hangi koşullar sözleşme
  öncesi düzeltilmeli. Ağırlık duyarlılığı sekmesi de kurulmaz.
- **İki teklif:** puanlama ve duyarlılık kurulur; **göreli** puan farkı %5'in altındaysa (§3b) "ayırt
  edilemez" notunu alır ve karar koşullara/riske bırakılır.
- **Yedi ve üzeri:** eleme ve KTM hepsine uygulanır, ağırlıklı puanlama **kısa listeye**
  (ilk 4-5) uygulanır; kısa liste ölçütü Puanlama sekmesine yazılır ve kullanıcı
  değiştirebilir.

Elemeden sonra elde kaç teklif kaldığı belirleyicidir: 5 teklif elemeyle 1'e düştüyse
puanlama yapılmaz, tek teklif moduna geçilir.

## 1. Elemeli (knock-out) kapı

Puanlamadan önce iki grup zorunlu şart kontrol edilir. Her biri
**GEÇTİ / ELENDİ / EKSİK BİLGİ** olarak işaretlenir. "Eksik bilgi" **eleme değildir**;
RFI'ya girer ve teklif "koşullu" olarak puanlamaya alınır, koşul Özet'te görünür.

### a) İdari zorunluluklar (her iki dal)

- Teklif geçerlilik süresi analiz tarihinde devam ediyor mu — **ve geçerlilik hiç beyan
  edilmemişse teklifin yaşı** (`references/analiz-hazirligi.md` Adım 1, tazelik iki testi). Geçerlilik beyanı
  olmayan bir teklif bu kapıdan "GEÇTİ" olarak çıkmaz; yaşına göre EKSİK BİLGİ veya
  KRİTİK UYARI alır
- Yetkili imza / kaşe / teklif mektubu formatı
- Şartnamede istenen zorunlu belgeler sunulmuş mu
  - **Makine:** CE beyanı, kalite sertifikaları, kapasite raporu, iş bitirme
  - **Yapım:** iş bitirme, EN 1090 FPC, ISO belgeleri, vergi/SGK borcu yoktur, ticaret sicil
- Teklif istenen para birimi / Incoterms / rejim / format şartına uygun mu
- İstenen teminatları vermeyi kabul ediyor mu

### b) Asgari teknik zorunluluklar

Şartnamede **"zorunlu / şart / asgari"** ifadeleriyle geçenler:

**Makine/ekipman dalı**
- Zorunlu belgelendirme (CE, PED, ATEX, gıda temas uygunluğu, hijyenik tasarım) —
  sağlanmıyorsa eleme
- Kapasite/performans alt sınırı
- Zorunlu malzeme kalitesi (ör. paslanmaz kalite düşürülmüş mü)
- Zorunlu emniyet seviyesi (PL/SIL)
- Şartnamenin açıkça reddettiği bir çözümün teklif edilmesi

**İnşaat/yapım dalı**
- Zorunlu belgelendirme: EN 1090 FPC + istenen EXC sınıfı, ISO 3834 — şartname açıkça şart
  koşmuşsa sağlanmaması eleme
- Zorunlu malzeme sınıfı (S355 istenirken S275; C30 istenirken C25)
- Zorunlu iş bitirme eşiği (benzer nitelik/ölçek)
- Şartnamenin açıkça reddettiği çözüm (galvaniz şartına karşı yalnız boya)
- Statik projeye aykırı kesit küçültme (onaylı alternatif hesap sunulmadan)

### Kurallar

- Elenen firma puanlama sekmesinde **satır olarak görünür** ama toplam puanı hesaplanmaz,
  sıralamaya girmez ve **"ELENDİ — gerekçe"** yazılır.
- Eleme kararı şartnamedeki zorunluluk ifadesinin **verbatim alıntısıyla** desteklenir.
- Şartname o şartı "tercih edilir" diye yazmışsa bu **eleme değil, puan kaybıdır**.
- **Anormal düşük teklif eleme sebebi değildir** — açıklama istenir ve risk matrisine girer.
- **Tüm firmalar elenirse:** hiçbiri seçilemez sonucunu ver, RFI ve zeyilname yolunu öner,
  şartnamenin gerçekçiliğini sorgula.

## 2. Ağırlıklı puanlama

Ağırlıklar toplamı 100; dala ve işin niteliğine göre uyarlanır, hücreler **düzenlenebilir**
bırakılır. Uyarlama yapıldıysa **gerekçesi Puanlama sekmesine yazılır.**

### Çifte sayım yasağı (ağırlıkları kurmadan önce oku)

**KTM'ye para olarak girmiş bir eksiklik, puanlamada ikinci kez cezalandırılmaz.**
Maliyet köprüsü zaten eksik kapsamı, ödeme planı farkını ve işletme maliyetini paraya
çevirip KTM'ye yazıyor; aynı konu bir de kriter olarak puanlanırsa firma iki kez düşer ve
"fiyat ağırlığı 25" cümlesi anlamını yitirir.

| Köprüde parasallaşan | Basamak | Puanlamada ne kalır |
|---|---|---|
| Eksik kapsam kalemleri — **firmalar arası** | 5-A | Tutarın kendisi **değil**, o tutarın ne kadarının analizdeki tahminlere dayandığı → kriter 2 |
| Ortak kapsam boşluğu — **hiçbir firmada yok** | 5-B | Ayrı nitel puan verilmez; KTM oranlarını sıkıştırabilir. Ortak tutar dahil/hariç puan duyarlılığı gösterilir; muhatap kapsam belgesinden belirlenir |
| Ödeme/hakediş planı, teminat komisyonu | 7 (finansman) | Ödeme **tutarı/vadesi değil**, sözleşme hükümleri: ceza, sorumluluk sınırı, garanti kapsamı, teminat verme kabulü → kriter 5 |
| Enerji, bakım, sarf, yedek parça **fiyatı** | 8 (TCO) | Fiyat **değil**, bulunabilirlik ve üreticiye bağımlılık (muadil kullanılabilir mi, tek kaynak mı) → kriter 8 |
| Eskalasyon senaryosu beklenen bedeli | 9 | Bedel **değil**, rejimin belirsizliği ve dengesiz teklif deseni → yapımda kriter 10, makinede kriter 11 |

Bir basamak **"uygulanmadı"** işaretliyse (ör. TCO kurulmadı, duruş maliyeti bilinmiyor) o
konu **niteliksel kriter olarak puanlamaya girer** ve bu durum kriterin gerekçe sütununa
yazılır — `tco-omur-boyu-maliyet.md` §2(f)'deki desen budur. Yani her konu **ya parada ya
puanda**, ikisinde birden değil; hangisinde olduğu her zaman yazılı.

### Varsayılan set — makine/ekipman dalı

| # | Kriter | Ağırlık | Puanlama |
|---|---|---|---|
| 1 | Karşılaştırılabilir Toplam Maliyet (KTM) | 25 | Formül |
| 2 | Maliyet belirsizliği / firmaya özgü brüt NBD tahmin payı | 15 | Formül |
| 3 | Teknik gereksinimlere uygunluk | 15 | Formül (uygunluk matrisinden) |
| 4 | Test / kalite / belgelendirme | 8 | Öznel |
| 5 | Sözleşmesel koşullar (ödeme tutarı/vadesi **hariç** — o KTM'de) | 8 | Öznel |
| 6 | Teslim süresi (saha teslim) | 5 | Formül |
| 7 | Garanti, satış sonrası servis, müdahale süresi | 6 | Yarı-formül |
| 8 | Yedek parça bulunabilirliği ve üreticiye bağımlılık (fiyat **hariç** — o TCO'da) | 4 | Öznel |
| 9 | Tedarikçi kurumsal/mali yeterlilik ve referans | 6 | Öznel |
| 10 | Mevcut tesis parkı ile standardizasyon uyumu | 6 | Öznel |
| 11 | Tedarik/lojistik riski (menşe, tek kaynak, kur) | 2 | Öznel |

Uyarlama örnekleri: sürekli çalışan üretim/paketleme hattında 7+8+10 artırılır (duruş
maliyeti yüksek); tek seferlik yapısal imalatta 1 ve 3 artırılır; ithal ekipmanda 11
artırılır.

### Varsayılan set — inşaat/yapım dalı

| # | Kriter | Ağırlık | Puanlama |
|---|---|---|---|
| 1 | Karşılaştırılabilir Toplam Maliyet (KTM) | 30 | Formül |
| 2 | Maliyet belirsizliği / firmaya özgü brüt NBD tahmin payı | 12 | Formül |
| 3 | Teknik gereksinimlere uygunluk | 14 | Formül |
| 4 | Kalite/belgelendirme ve test planı | 8 | Öznel |
| 5 | Sözleşmesel koşullar (ödeme tutarı/vadesi **hariç** — o KTM'de) | 8 | Öznel |
| 6 | Süre (iş programının gerçekçiliği dahil) | 8 | Yarı-formül |
| 7 | Garanti ve kabul sonrası sorumluluk | 4 | Yarı-formül |
| 8 | Yüklenici kurumsal/mali yeterlilik ve iş bitirme | 10 | Öznel |
| 9 | Şantiye organizasyonu, ekipman parkı, İSG yaklaşımı | 4 | Öznel |
| 10 | Fiyat rejimi riski (eskalasyon/dengesiz teklif/anormal düşük) | 2 | Öznel |

Uyarlama örnekleri: karmaşık montajlı/yüksek yapıda 8+9 artırılır; süre-kritik projede 6
artırılır; basit saha işinde 1 artırılır.

**Karma işte** (ekipman + yapım) tek bir set kurulur: iki tablonun kriterleri birleştirilir,
çakışanlar tekilleştirilir ve toplam yeniden 100'e normalize edilir; birleştirme gerekçesi
yazılır.

## 3. Normalizasyon formülleri

Ölçülebilir kriterlerde 1-10 arası öznel puan **verilmez**, formül kullanılır. Böylece bir
girdi değiştiğinde puan kendiliğinden güncellenir. **Bütün puanlar 0-10 ölçeğindedir**
(bkz. §3b — ölçek ve eşik).

- **Maliyet (düşük iyi):** `puan = 10 × MIN(tüm KTM) / firma_KTM` (oransal — varsayılan)
  - Alternatif: **aralık (min-maks)** yöntemi — `puan = 10 × (MAKS − firma_KTM) / (MAKS − MIN)`.
    Hangisinin kullanıldığı Puanlama sekmesine **yazılır**; ikisi farklı sonuç verir ve
    seçim ağırlığın anlamını değiştirir (bkz. §3c).
- **Süre (kısa iyi):** `puan = 10 × MIN(tüm süre) / firma_süre`
  - Makine: **saha teslim** süresi (ithal tekliflerde navlun+gümrük dahil, bkz.
    `ithalat-maliyet-koprusu.md`)
  - Yapım: geçici kabule kadar toplam süre; gerçekçi olmayan kısa süre (iş programı
    desteklemiyorsa) öznel düzeltme notuyla işaretlenir
- **Maliyet belirsizliği / tahmin payı:**
  `puan = 10 × (1 − firmaya özgü tahmini maliyetlerin brüt NBD'si /
  firmaya özgü bütün maliyetlerin brüt NBD'si)`.
  Brüt payda, ortak 5-B hariç, pozitif giderlerin toplamıdır; hurda/iade alacakları
  paydadan düşülmez. Pay yalnız tahmin işaretli bu giderleri içerir: 5-A ile sınırlı
  değildir; tahmini navlun, bakım ve eskalasyon da kapsama alınır. Pay ile payda aynı
  dönem, para birimi ve iskonto esasındadır. Firma/üçüncü tarafın geçerli sabit fiyatı
  tahmin sayılmaz. Kısmen tahminse o kısım ayrıştırılır.
  Ortak 5-B hem paydan hem paydadan çıkarılır; böylece ortak gider büyüdükçe firmanın
  belirsizliği yapay olarak küçülmez. Fiyatlanmamış kalem sıfır tahmin sayılmaz:
  kriter ve toplam **koşullu**, eksik maliyet aralığı/RFI görünür olur.
- **Teknik uygunluk:**
  `puan = 10 × Σ(gereksinim_ağırlığı × uygunluk_katsayısı) / Σ(uygulanabilir ağırlık)`.
  Katsayılar: UYGUN=1, kanıtlı KISMEN=0,5, UYGUN DEĞİL=0. BELİRTİLMEMİŞ,
  KISMEN ile aynı veri değildir: bilinmeyen katsayı için 0–1 aralığında alt/üst
  puan gösterilir; zorunlu madde RFI/koşullu kapıda kalır. Uygulanmayan gereksinim
  paydadan çıkarılır. Ağırlık belirlenmemişse her bağımsız gereksinim 1; aynı
  gereksinimin tekrarları sayılmaz. Eleme şartı puanla telafi edilmez.
- **Garanti süresi (uzun iyi):** `puan = 10 × firma_süre / MAX(tüm süre)`

Öznel kriterlerde puan hücresi **mavi font + sarı dolgu** (düzenlenebilir) ve **gerekçe
sütunu zorunlu** — gerekçesiz öznel puan yazılmaz.

**Sınır kontrolleri:** MIN/MAX yalnız puanlamaya uygun ve karşılaştırılabilir
seçenekler üzerinde çalışır; elenenler ve boş fiyatlar referansa girmez. Negatif/0
KTM varsa oransal maliyet formülü uygulanmaz. Eşit maliyetler aynı puanı alır;
min=maks durumunda aralık yöntemi bölme yapmaz. Aynı gün teslim (0 gün) için
önceden belirlenmiş hedef/tavan puanı kullanılır; süreye yapay 1 gün eklenmez.
Garanti süreleri aynı başlangıç ve kapsama getirilir; hepsi 0 ise puan 0,
bilinmeyense nötr/RFI uygulanır. Ağırlıklar negatif olamaz ve toplam tam 100 olmalıdır.

Toplam: `=SUMPRODUCT(ağırlıklar, puanlar)/100`. Ayrıca `=SUM(ağırlıklar)` hücresi 100
kontrolü için görünür tutulur.

> **openpyxl uyarısı:** formül dosyaya yazılırken argüman ayırıcısı **her zaman virgül**
> olmalıdır (`=SUMPRODUCT(C5:C15,D5:D15)/100`). Türkçe Excel ekranda noktalı virgül
> gösterir ama dosya biçiminde virgül saklanır; noktalı virgülle yazılan formülü Excel
> okuyamaz. Bkz. `excel-ve-rapor-uretimi.md` → tuzaklar.

## 2b. Ayırt edici ağırlık oranı (ZORUNLU — puanı sunmadan önce hesapla)

Bir kriter, **tüm tekliflere aynı puanı** veriyorsa sıralamaya hiçbir katkısı yoktur.
Bu iki sebeple olur ve ikisi de sıktır:

1. **Veri yok** — hiçbir teklifte o konuda beyan bulunmadığı için üçüne de nötr puan
   verilmiştir (ödeme planı, süre, garanti, yeterlilik belgesi… çoğu alımda eksiktir).
2. **Fark yok** — kriter gerçekten ayırt etmemiştir (ör. ortak keşif cetveliyle çalışılan
   bir işte kapsam belirsizliği kriteri üç firmada da 10,00 çıkar).

Ağırlık toplamı 100 olsa bile **fiilen çalışan ağırlık** bundan küçüktür:

```
ayırt edici ağırlık = puanları BİRBİRİNDEN FARKLI olan kriterlerin ağırlık toplamı
ayırt edici oran   = ayırt edici ağırlık / 100
```

**Bu oran Puanlama sekmesinde ve Karar Özeti'nde yazılır**, şu biçimde:
*"100 ağırlık puanının N'i ayırt etmiyor; sıralamayı fiilen şu kriterler belirliyor: …"*

| Ayırt edici oran | Puanın statüsü | Ne yazılır |
|---|---|---|
| **≥ %60** | Ağırlık ayrışması yeterli; veri kalitesini kanıtlamaz | diğer belirsizlik kontrolleriyle sunum |
| **%30 ≤ oran < %60** | Zayıf — puan, birkaç kriterin gölgesidir | hangi kriterlerin taşıdığı açıkça yazılır |
| **< %30** | **Puan tablosu tek başına karar gerekçesi DEĞİLDİR** | *"Sıralamayı fiilen yalnız … belirliyor; puan tablosu çok kriterli bir karar görüntüsü veriyor ama değildir. RFI cevapları gelmeden karar gerekçesi olarak kullanılmamalıdır."* |

**Neden zorunlu:** yarısı nötr doldurulmuş bir puan tablosu, ekrandaki görüntüsüyle
zengin ve dengeli bir çok kriterli karar gibi durur; oysa sonuç tek bir kriterin
(genellikle fiyatın) yeniden yazılmış hâlidir. Bu, skill'in ürettiği en sinsi yanlış
güvendir — çünkü tablo ne bir hata verir ne de eksik görünür.

**Nötr puan kuralı:** veri olmadığı için verilen puan **5,0**'dir (0-10 ölçeğinin ortası),
hücre sarı dolgu + mavi font ile düzenlenebilir bırakılır ve gerekçe sütununa
*"VERİ YOK — RFI sonrası doldurulacak"* yazılır. Sıfır verilmez (cezalandırma olur),
10 verilmez (ödüllendirme olur). Nötr puanlı her kriter **aynı zamanda bir RFI maddesidir** —
biri varsa diğeri de olmalıdır.

## 3b. Puan ölçeği ve yakın puan eşiği

**Kriter puanları 0-10. Toplam puan da 0-10** — `SUMPRODUCT(ağırlık; puan)/100` formülü
ağırlık toplamı 100 olduğu için sonucu 10'a indirir (tüm kriterlerde 10 alan teklif
tam 10,00). Bu **her sütun başlığında yazılır:** "Puan (0-10)", "Toplam (0-10)".

100'lük sunum tercih ediliyorsa formül `/10` olur ve başlıklar "(0-100)" yazar. **İkisi
karıştırılmaz;** bir dosyada tek ölçek kullanılır ve ölçek Karar Özeti'nde de aynı kalır.

**Yakın puan eşiği görelidir ve yönetim tercihidir; bilimsel güven aralığı değildir:**

```
göreli fark = (birinci_puan − ikinci_puan) / birinci_puan (birinci > 0 ise)
göreli fark < %5  →  "puanlar yakın; bu bir istatistiksel eşdeğerlik testi değildir"
```

Birinci puan 0 ise göreli fark hesaplanmaz; sıralama için veri/ölçüt yetersizliği yazılır.

0-10 ölçeğinde bu tipik olarak **0,3-0,5 puanlık** bir farka karşılık gelir. Eşik mutlak
puan olarak değil **oran** olarak yazılır; ölçek değişse bile kural aynı kalır. Eşiğin
altında kalındığında karar puanla verilmez: KTM, kırmızı çizgiler ve koşullar belirleyici
olur (bkz. §5).

## 3c. Hangi normalizasyon — ve "ağırlık 30" ne kadar ağırlık

Oransal yöntem (`10 × MIN/firma`) farkları **sıkıştırır**; bu yüzden bir kriterin
yazılı ağırlığı ile fiili etkisi aynı şey değildir:

| Karşılaştırma | Puanlar | Toplama etkisi (0-10) |
|---|---|---|
| KTM %10 fark, ağırlık 30 — **oransal** | 10,00 ↔ 9,09 | **0,273** |
| KTM %25 fark, ağırlık 30 — **oransal** | 10,00 ↔ 8,00 | 0,600 |
| Öznel kriterde 3 puanlık takdir, ağırlık 8 | 9 ↔ 6 | **0,240** |

Yani **8 ağırlıklı bir kriterdeki tek takdir kararı, 30 ağırlıklı fiyat kriterindeki %10
fiyat farkına denk.** "Fiyat ağırlığı 30" cümlesi yanıltıcıdır; oransal yöntemde fiili
ağırlık çok daha küçüktür. Bu bir hata değil, yöntemin özelliğidir — ama **bilinerek
seçilmelidir.**

| | Oransal (varsayılan) | Aralık (min-maks) |
|---|---|---|
| Ağırlık ne kadar çalışır | Yayılım küçükse çok az | Tam — en pahalı 0, en ucuz 10 |
| Aykırı değere dayanıklılık | Yüksek | Düşük (tek aşırı pahalı teklif ölçeği ezer) |
| Büyük farkı cezalandırma | **Zayıf** — %50 pahalı teklif 6,67 alır | Güçlü |
| Küçük farkı büyütme | Yok | **Var** — %2 fark 10 ↔ 0 olabilir |
| 2 teklifte | Çalışır | **Kullanılmaz** — fark %1 de olsa %100 de olsa hep 10/0 verir |

**Kural:** yöntem puan sonuçları görülmeden seçilir; kazananı değiştirmek için sonradan ayarlanmaz. Gerekçesi ve **fiyat yayılımı** (`MAKS/MIN − 1`) Puanlama sekmesine
yazılır. Varsayılan oransaldır. Aralık yöntemi **5 ve üzeri teklifte** ve yayılım anlamlı
olduğunda kullanılır; 2 teklifte hiç kullanılmaz, 3-4 teklifte yalnız gerekçeyle. Yayılım
**%50'nin üzerindeyse** fiyat farkının puana nasıl yansıdığı Karar Özeti'nde gösterilir.
Yüksek maliyet ağırlığı ayrı duyarlılık senaryosunda denenir; baz ağırlık sonuca göre
sessizce değiştirilmez.

Bu belirsizliğin panzehiri §5'teki kuraldır: karar hiçbir zaman tek başına toplam puana
dayandırılmaz, **KTM sıralaması ayrı bir ayak olarak** gösterilir.

## 4. Ağırlık duyarlılığı (puanlama yapılırken zorunlu kontrol)

En az üç senaryo kurulur; **her senaryoda ağırlık toplamı 100 olmalıdır:**

| Senaryo | Mantık |
|---|---|
| Baz | Yukarıdaki (veya kullanıcının onayladığı) ağırlıklar |
| Maliyet odaklı | KTM ağırlığı makinede ~40, yapımda ~45'e çıkarılır; fark diğerlerinden oransal düşülür |
| Teknik/hizmet veya yeterlilik odaklı | KTM makinede ~15, yapımda ~18'e düşürülür; teknik uygunluk + servis/standardizasyon (makine) veya yüklenici yeterliliği + kalite (yapım) artırılır |
| (opsiyonel) Hız/süre odaklı | Teslim süresi / süre ağırlığı artırılır |

Her senaryoda mevcut seçenekler sıralanır. Maliyet ağırlığı w değerinden w_yeni
değerine çıkarken diğerleri `ağırlık_yeni = ağırlık_eski × (100−w_yeni)/(100−w)`
ile oransal düzenlenir (w=100 ise başka ağırlık dağılımı açıkça tanımlanır). Sonuç yorumu iki cümleyle yazılır —
**ama önce §2b'deki ayırt edici oran hesaplanır, çünkü "sıralama değişmedi" cümlesinin
anlamı ona bağlıdır:**

- Sıralama değişiyorsa: **"Karar ağırlık seçimine duyarlıdır; X ile Y arasındaki seçim
  fiyat/teknik(yeterlilik) önceliğine bağlıdır ve bu tercih yönetimce yapılmalıdır."**
  Bu durumda **tek bir firmayı kesin öneri olarak sunma.**
- Sıralama tüm senaryolarda aynı **ve ayırt edici oran ≥ %60** ise:
  **"Denenen ağırlık senaryolarında sıra değişmedi; sonuç bu senaryolarla sınırlıdır."**
- Sıralama aynı ama ayırt edici oran < %60 ise: **"Denenen senaryolarda sıra
  değişmedi; sınırlı sayıda kriter ayrışıyor. Bu tek başına kararın sağlamlığını kanıtlamaz."**
  Düşük ayırt edici oran sıralamanın değişmesini matematiksel olarak imkansız kılmaz.

**Ortak maliyet duyarlılığı:** A=100, B=120 ise fiyat puanları 10 ve 8,333'tür.
İkisine 1.000 ortak gider eklenirse 10 ve 9,821 olur. Maliyet sırası korunur ama
başka kriterlerin etkisi büyüyerek **toplam puan sırasını değiştirebilir**. Bu yüzden
KTM'nin tamamı üzerinden baz puanı koru; aynı ortak NBD'yi her seçenekten çıkararak
ikinci puan senaryosu göster. Hangisinin kararı taşıdığı açıkça yazılır.

**Belirsizlik duyarlılığı:** eksik veri için 5 puan kesin bilgi değildir. Önemli
bilinmeyen kriterleri gerekçeli alt/üst puanlarla dene; sıra değişiyorsa RFI sonrası
karar gerekir. Ayırt edici oran veri güvenilirliğinin yerine geçmez. Ek olarak her
kriterin puan aralığı × ağırlık/100 katkısını göster; 0,01 puanlık farkı anlamlı
ayrışma diye sunma. %30/%60 eşikleri iç uyarı eşikleridir, doğruluk belgesi değildir.

Ek olarak kur duyarlılığı ve eskalasyon senaryosu (bkz. `finansal-degerlendirme.md`)
sıralamayı değiştiriyorsa aynı sekmede gösterilir.

## 5. Puan sunumunda sınır

Toplam puan **tek başına karar gerekçesi değildir.** Karar Özeti'nde her zaman üç ayak
birlikte gösterilir: **puan sıralaması + KTM sıralaması + kırmızı çizgi/uygunsuzluk
durumu.** Üçü farklı firmayı işaret ediyorsa bu çelişki açıkça yazılır ve karar yönetime
bırakılır. **Göreli** puan farkı (§3b: `(birinci−ikinci)/birinci`) **%5'in altındaysa** "puanlar yakın; bu bir istatistiksel eşdeğerlik testi değildir" notu düşülür.
