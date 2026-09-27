# Şartname Yoksa — Şartnamesiz Mod

Klasörde teknik şartname **yoksa** teknik uygunluk değerlendirmesi yapılmaz. Bu bir eksik
değil, **bilinçli bir moddur:** olmayan bir ölçüte göre puan vermek uydurmadır ve yanlış
satınalma kararı üretir.

**Ama analiz durmaz.** Şartnamesiz modda karşılaştırılabilecek çok şey vardır: kapsam,
miktar, fiyat, ticari koşullar, teslim süresi, garanti, firma yeterliliği, sözleşme
maddeleri. Doğru satınalmanın büyük kısmı buradadır.

## 1. Şartname var mı — nasıl karar verilir

Şartname yerine geçen üç şey **kabul edilir** (varlığı Özet'te hangisi olduğu yazılarak
belirtilir):
1. Teknik şartname / spesifikasyon belgesi.
2. Keşif/metraj cetveli (BoQ) — teknik ölçüt değil ama **kapsam ve miktar referansı** verir.
3. Kullanıcının yazdığı gereksinim listesi (mail, mesaj, RFQ metni) — kısa da olsa ölçüttür.

Bunlardan hiçbiri yoksa şartnamesiz moda geçilir. **Bir firmanın kendi teklifi asla
şartname yerine kullanılmaz** — o firmanın kapsamını ölçüt yapmak diğerlerini haksız
biçimde uygunsuz gösterir.

## 2. Şartnamesiz modda ne değişir

| Adım | Şartname varken | Şartname yokken |
|---|---|---|
| Uygunluk matrisi (Adım 4) | gereksinim × firma, üç renk | **yapılmaz**; sekme oluşturulmaz |
| Elemeli kapı — teknik (Adım 6) | asgari teknik şartlar uygulanır | **yalnız idari kapı** uygulanır (geçerlilik, imza/kaşe, istenen teminatı kabul, para birimi) |
| Eşit kapsam düzeltmesi (5c) | şartnamenin TAM kapsamına getirilir | **ortak referans kapsama** getirilir (aşağıya bak) |
| Miktar mutabakatı | keşif/proje metrajı referans | keşif/proje varsa o; yoksa bağımsız firma sayısına göre senaryo/RFI (`teklif-sayisi-modlari.md`) |
| Puanlama | teknik uygunluk kriteri var | teknik uygunluk ağırlığı **kapsam belirsizliği + yeterlilik + sözleşmesel koşullara** dağıtılır; dağıtım Puanlama sekmesinde yazılır. Şartname yokken tahmin payı büyür, yani kriter 2 bu modda daha ayırt edicidir |
| Karar Özeti | "şartnameye uygun en iyi teklif" | **"şartname olmadığı için teknik denklik doğrulanmamıştır"** uyarısı zorunlu |

## 3. Ortak referans kapsam (şartnamenin yerini tutan iskele)

**Bu yöntem en az iki bağımsız tedarikçinin teklifini gerektirir.** Tek teklif varsa ortak referans kapsam
**kurulamaz** — tek kaynağın kendi kapsamını ölçüt yapmak, ölçütü firmaya yazdırmaktır.
O durumda eksik olabilecek kalemler dalın kontrol listesinden **soru olarak** çıkarılır
ve kullanıcıya sorulur (bkz. `teklif-sayisi-modlari.md` §1).

Şartname yoksa ve iki veya daha fazla teklif varsa kapsam ölçütü **tekliflerin
birleşimidir**:

1. Tüm tekliflerdeki kalemler tek listede toplanır (`poz-eslestirme-normalizasyon.md`
   mantığıyla eşlenir).
2. Birleşim **aday kapsam** listesidir; ihtiyacı karşılayan zorunlu/tercih edilen
   kalemler ile gereksiz opsiyonlar ayrılır. Bir firmanın fazladan verdiği özellik
   otomatik olarak diğerlerine maliyet yüklemez. Belirsiz önemli kalemin gerekliliği
   kullanıcıyla netleştirilir; gerekirse ortak asgari ve geniş kapsam senaryoları kurulur.
3. O kalemi vermeyen firmalar için kalem **sıfır sayılmaz** — piyasa rayici veya diğer
   firmaların fiyatı ile tahmin edilerek eklenir (sarı dolgu + mavi font, dayanağı not
   sütununda).
4. Sonuç: "Eşit Kapsam Senaryosu" sekmesi şartname olmadan da kurulur ve genellikle
   **sıralamayı değiştiren asıl bulgu budur.**

Bu yaklaşımın sınırı açıkça yazılır: ortak referans kapsam, **doğru kapsam olduğunu
garanti etmez** — hiçbir firmanın düşünmediği bir gereksinim (ör. 3. taraf denetim,
eğitim, yedek parça) listede hiç görünmez.

## 4. Şartnamesiz modun en kritik üç bulgusu

Bu üçü Özet'in KRİTİK UYARI kutusuna girer:

1. **Kapsam eşitsizliği.** Şartname yokken firmalar birbirinden farklı şey teklif etmiş
   olma ihtimali en yüksektir. Fiyatların doğrudan kıyaslanamaz olduğu buradan çıkar.
2. **Teknik denklik doğrulanmamış.** İki teklif farklı malzeme sınıfı, farklı kapasite,
   farklı kalınlık, farklı marka içeriyor olabilir; hangisinin "yeterli" olduğunu söyleyen
   bir belge yok. Ucuz teklifin neden ucuz olduğu **bilinmiyor** demektir.
3. **Sonraki alımlar için şartname önerisi.** Analizden çıkan gereksinim listesi, bir
   sonraki alımda kullanılmak üzere **taslak şartname maddeleri** olarak RFI sekmesinin
   altına yazılır. Bu, şartnamesiz alımın tekrarlanmasını engelleyen tek çıktıdır.

## 5. Kullanıcıya ne söylenir

Analize başlamadan, envanter tablosuyla birlikte tek cümle:

> "Klasörde teknik şartname bulunmadı. Teklifleri **kapsam, maliyet, ticari koşullar ve
> firma yeterliliği** üzerinden karşılaştıracağım; **teknik uygunluk değerlendirmesi
> yapılmayacak.** Elinizde bir gereksinim listesi veya RFQ metni varsa paylaşın — ölçüt
> olarak kullanırım."

Kullanıcı "şartname yok, devam et" derse mod kesinleşir ve rapor boyunca bu not korunur.
**Şartname sonradan gelirse** analiz sıfırdan yazılmaz, sürümlenir (`_v2`) ve Değişim
Kaydı sekmesine "şartname eklendi → teknik uygunluk ilk kez değerlendirildi" satırı girer.
