# Teklif Sayısına Göre Modlar

Klasöre kaç teklif konduğu **belirsizdir**: bir tane de olabilir, on iki tane de.
Skill'in yöntemi buna göre değişir — çünkü karşılaştırma, medyan, sapma ve sıralama
kavramları belirli sayıların altında **anlamını yitirir**. Sayıya bakmadan aynı analizi
uygulamak, olmayan bir rekabeti varmış gibi göstermek demektir.

**İki ayrı sayı tutulur:** karşılaştırılabilir seçenek sayısı ve bağımsız tedarikçi
sayısı. Revizyonlar tek, alternatifler ayrı sütundur. Bir firmanın üç alternatifi
**üç rakip değildir**. Alternatifler ihtiyaç ve maliyet açısından kıyaslanabilir,
ama tek kaynak durumunda rekabet uyarısı ve makullük denetimi korunur; piyasa/medyan
kanıtı üretilmez, rekabet puanlaması yapılmaz. İki veya daha çok bağımsız tedarikçi
varsa seçenekler puanlanabilir; piyasa/medyan testlerinde aynı firmanın seçenekleri
ayrı bağımsız gözlem sayılmaz. Aynı karşılaştırılabilir kapsamda firma başına bir
esas teklif seçilemezse o test uygulanmaz.

Eleme sonrası sayılar yeniden hesaplanır. Aşağıdaki mod tablosu **bağımsız geçerli
tedarikçi sayısına** göre uygulanır; seçenek sayısı ayrıca gösterilir.

## Mod tablosu

| Bağımsız geçerli tedarikçi | Mod | Ne değişir |
|---|---|---|
| **1** | Tek teklif modu | Karşılaştırma yok. Analiz **makullük ve kapsam denetimine** döner; aşağıdaki bölüm uygulanır |
| **2** | İkili mod | Medyan/sapma istatistiği yok; **fark analizi** yapılır. Min/max iki değerden oluşur, "medyandan sapma" satırı kurulmaz |
| **3–6** | Tam mod (varsayılan) | Skill'in bütün adımları uygulanır |
| **7 ve üzeri** | Kısa liste modu | Eleme + KTM tüm tekliflere; **derin analiz ilk 4-5'e**, kalanlar özet satır olarak durur. Gerekçesi Özet'te yazılır |

## 1. Tek teklif modu (N=1)

Bu bir eksiklik değil, ayrı bir iştir: **tek tekliften karar çıkarmak.** Satınalmada
sık görülür (tek kaynak, acil ihtiyaç, tek yetkili distribütör, diğer firmalar teklif
vermedi). Skill kıyas taklidi yapmaz; şu dört soruya cevap üretir:

1. **Kapsam tam mı?** Şartname veya gereksinim listesi varsa uygunluk matrisi normal
   kurulur — bu tek teklifte bile çalışır ve en değerli çıktıdır. Şartname yoksa
   kapsam ölçütü kalmaz: "ortak referans kapsam" **kurulamaz** (tek kaynağın kendisi
   ölçüt yapılamaz, bkz. `sartname-yoksa.md`); eksik olabilecek kalemler ancak dalın
   kontrol listesinden **soru olarak** çıkarılır.
2. **Fiyat makul mü?** Karşılaştırma yoksa referans dışarıdan gelir ve **her biri
   varsayım işaretlidir:** birim maliyet metriği (₺/kg, ₺/m², ₺/ton kapasite, $/kW),
   varsa geçmiş alım fiyatı, ham malzeme maliyeti üzerinden alt sınır testi
   (`poz-eslestirme-normalizasyon.md` §5), muadil ürünün liste fiyatı. Referans
   bulunamıyorsa **"fiyat makullüğü değerlendirilemedi"** yazılır — tahmini bir
   "uygun görünüyor" cümlesi yazılmaz.
3. **Koşullar riskli mi?** Ticari ve sözleşmesel analiz (`sozlesme-maddeleri.md`,
   `finansal-degerlendirme.md`) tam olarak uygulanır — bunların hiçbiri rekabet
   gerektirmez ve tek teklifte **pazarlığın asıl malzemesi** budur.
4. **Firma yeterli mi?** `tedarikci-yeterlilik-risk.md` tam uygulanır.

**Çıktıda zorunlu üç şey:**
- Özet'in en üstünde **"TEK TEKLİF — REKABET YOK"** uyarısı ve tek teklif olmasının
  bilinen sebebi (kullanıcıdan sorulur: başka firma çağrıldı mı, çağrıldı da cevap
  vermedi mi, tek kaynak mı).
- **Pazarlık gündemi:** kırmızı çizgiler + koşul iyileştirme maddeleri (ödeme planı,
  teminat, garanti süresi, ceza limiti, eskalasyon maddesi) — indirim tek kalem değildir.
- **İkinci teklif önerisi:** hangi tür firmadan, hangi asgari bilgi setiyle. Tek
  kaynak gerçekten tek kaynaksa bunun **yazılı gerekçesi** öneri olarak konur (denetim
  izi; şirket prosedürü bunu istiyorsa oraya dayanak olur).

**Kurulmayan sekmeler** (Özet'te "uygulanmadı — tek teklif" yazılır): Puanlama Matrisi,
Ağırlık Duyarlılığı, Poz Bazlı Birim Fiyat karşılaştırması, Eşit Kapsam Senaryosu'nun
firmalar arası kısmı. **Kurulan sekmeler:** Özet, Karar Özeti, Elemeli Değerlendirme
(idari + varsa teknik), Fiyat Detayı, Şartname Uygunluğu, Teknik Detay, Ticari Koşullar,
Sözleşme Maddeleri, Yeterlilik ve Risk, RFI. Maliyet köprüsü **kurulur** — tek teklifte
de teklif fiyatı ile gerçek maliyet aynı şey değildir (kur, ithalat, eksik kapsam, vergi,
finansman, TCO hepsi geçerli).

**Puanlama yapılmaz.** Tek teklife tam puan vermek, olmayan bir sıralamaya
gerekçe üretir. Yerine **eşik değerlendirmesi** konur: elemeli kapıdan geçti mi,
kırmızı çizgiler karşılanıyor mu, hangi koşullar sözleşme öncesi düzeltilmeli.

## 2. İkili mod (N=2)

- **Medyan yok.** İki değerin medyanı ortalamadır; "medyandan ±%30 sapma" testi anlamsız
  olur ve kurulmaz. Yerine **doğrudan fark tablosu**: kalem × Firma A × Firma B × fark
  (tutar ve %) × farkın açıklaması (kapsam mı, kalite mi, fiyatlama mı).
- **Referans metraj** medyandan türetilemez: keşif/proje metrajı varsa o kullanılır;
  yoksa iki beyan da gösterilir ve KTM **her iki referansla** hesaplanır (iki senaryo).
  Tek bir ortalama uydurulmaz.
- **Anormal düşük teklif testi** karşılaştırmalı değil, **mutlak** yapılır: ham malzeme +
  asgari işçilik alt sınırı — yani **Test A** (`poz-eslestirme-normalizasyon.md` §5).
  **Test B (yakınsama) iki teklifte kurulmaz:** iki değerin birbirine yakınlığı piyasa
  kanıtı değildir, o test N≥3 gerektirir.
- Puanlama ve duyarlılık **kurulur** ama yorumu değişir: iki teklif arasında %5'in
  altındaki puan farkı "ayırt edilemez" notunu alır ve karar koşullara/riske bırakılır.

## 3. Kısa liste modu (N≥7)

Yedi ve üzeri teklifte hepsini aynı derinlikte analiz etmek hem bağlamı tüketir hem de
karar için gereksizdir. Sıra:

1. **Elemeli kapı hepsine** uygulanır (idari + varsa teknik). Elenenler tabloda gerekçesiyle
   kalır.
2. **KTM'nin karar etkisi olan bütün basamakları hepsine** uygulanır: finansman,
   TCO ve eskalasyon farkı bir teklifi öne geçirebiliyorsa bunlar tamamlanmadan
   kısa liste dışına atılmaz. İlk kaba toplam "ön maliyet"tir, nihai KTM değildir.
3. **Kısa liste:** KTM'ye göre ilk 4-5 teklif + elemeli kapıdan geçmiş ama teknik olarak
   dikkat çeken teklifler. Seçim ölçütü Özet'te **yazılır** (yalnız fiyata göre kısa liste
   yapılmışsa bu söylenir).
4. **Derin belge/teknik inceleme** kısa listeye uygulanır; eksik maliyet aralığı
   kısa listeye girebilecek bir teklifi gösteriyorsa o teklif de kapsama alınır. Kalanlar Özet'te tek satır: firma, KTM,
   kapsam durumu, "kısa listeye alınmama gerekçesi".
5. **Daha geniş piyasa görünümü:** bağımsız ve aynı kapsamlı fiyatlarda medyan kullanılabilir;
   N≥7 tek başına istatistiksel güven veya piyasa doğrulaması değildir; poz bazlı
   min/medyan/max analizi bu modda en değerlidir ve **tüm** tekliflerin fiyatlarıyla
   yapılır (kısa liste değil).

**Kullanıcıya bildirim:** "12 teklifin tamamı ön değerlendirmeden geçirilerek
karşılaştırılabilir toplam maliyetleri hesaplanacaktır. Ayrıntılı analiz ilk 5 teklif
için yapılacaktır. Kısa listeye eklenmesini istediğiniz teklifleri belirtebilirsiniz."
Kısa liste **kullanıcının değiştirebileceği** bir karardır.

## 4. Sıfır teklif

Klasörde teklif rolüne atanabilecek dosya yoksa analiz başlamaz. Envanter tablosu
gösterilir ve tek soru sorulur: teklifler henüz gelmedi mi, başka bir yerde mi, yoksa
dosyalar yanlış mı sınıflandırıldı? Şartname tek başına yüklenmişse yapılabilecek iş
vardır ve önerilir: şartnameden **gereksinim listesi + RFI/teklif isteme kontrol listesi**
çıkarmak. Bu, sonraki turda gelen tekliflerin karşılaştırılabilir olmasını sağlar.
