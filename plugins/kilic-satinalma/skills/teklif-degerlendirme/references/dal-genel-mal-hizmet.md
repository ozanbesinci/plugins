# Dal: Genel Mal ve Hizmet Alımı (inşaat/makine dışı)

İnşaat ve makine dalı sinyalleri baskın değilse bu dosya okunur. Kapsar: sarf ve ambalaj
malzemesi, kimyasal, hammadde, yedek parça alımı, nakliye/lojistik, bakım-onarım hizmeti,
temizlik, güvenlik, danışmanlık, yazılım/lisans, kiralama (araç, ekipman, gayrimenkul),
mobilya-donanım.

**Ortak omurga değişmez:** kapsam eşitliği → KTM zinciri → ticari/sözleşmesel koşullar →
firma yeterliliği ve risk → elemeli kapı ve puanlama → doğrulama. Bu dosya yalnızca
**hangi teknik/ticari kalemlerin sorulacağını** söyler.

## 1. Alımın gerçek birimini bul (en kritik adım)

Genel alımlarda fiyat farkı çoğu zaman **birimin farklı olmasından** doğar, kalitedendir
sanılır. Karşılaştırma **kullanım başına maliyete** indirgenir:

| Alım | Yanlış kıyas | Doğru kıyas birimi |
|---|---|---|
| Ambalaj filmi | ₺/rulo | **₺/kg** veya ₺/1.000 paket (mikron ve rulo uzunluğu farkı) |
| Kimyasal / deterjan | ₺/bidon | **₺/kg aktif madde** veya ₺/kullanım dozu |
| Yem, hammadde | ₺/çuval | ₺/ton + **spesifikasyon** (protein/nem) başına |
| Nakliye | ₺/sefer | **₺/ton-km** veya ₺/palet; bekleme, hamaliye, ADR dahil mi |
| Bakım hizmeti | ₺/ay | ₺/müdahale + yanıt süresi + kapsam dışı işlerin saat ücreti |
| Temizlik/güvenlik | ₺/ay | **₺/kişi-vardiya**; asgari ücret artışı ve SGK yükü hangi tarafta |
| Yazılım/lisans | ₺/yıl | ₺/kullanıcı/yıl + yenileme artış oranı + destek dahil mi |
| Kiralama | ₺/ay | toplam sahip olma maliyeti: peşinat + kira × süre + bakım + sigorta + iade koşulu |

Firma farklı birimde teklif verdiyse **çevrim açık bir satırda gösterilir** ve kullanılan
katsayı (mikron, yoğunluk, gramaj, doz) kaynağıyla yazılır.

## 2. Mal alımında sorulacaklar

- Ürün spesifikasyonu: marka/model/menşe, gramaj-kalınlık-konsantrasyon, raf ömrü
- Uygunluk belgeleri: gıda temas (EC 1935/2004), MSDS/GBF, analiz sertifikası (CoA),
  helal/ISO gereksinimi varsa
- Ambalaj ve paletleme birimi; **minimum sipariş miktarı (MOQ)** ve minimum kamyon şartı
- Teslim: nereye, kaç günde, kısmi teslim mümkün mü, stok tutma taahhüdü var mı
- Fiyat geçerliliği ve **fiyat revizyon maddesi** (endeks/kur) — sürekli alımda esas mesele
- İade/uygunsuz ürün prosedürü, numune onayı
- Sürekli alımlarsa: yıllık tahmini tüketim üzerinden **çerçeve sözleşme + kademeli fiyat**
  mümkün mü

## 3. Hizmet alımında sorulacaklar

- **Kapsam sınırı:** hangi iş dahil, hangisi ek ücretli; kapsam dışı işin saat/gün ücreti
- **SLA:** yanıt süresi, çözüm süresi, çalışma saatleri, hafta sonu/gece kapsamı, ceza
- Personel: kaç kişi, nitelik/sertifika, devir hızı, kim eğitir
- **İSG ve SGK:** işveren sorumluluğu, alt yüklenici bildirimi, ilişiksizlik belgesi,
  iş kazası sorumluluğu — hizmet alımının en büyük gizli riski buradadır
- Sigorta: mesleki sorumluluk, 3. şahıs mali mesuliyet
- Ekipman ve sarf kimden (temizlikte kimyasal, bakımda yedek parça)
- Süre, fesih ve yenileme koşulları; **otomatik yenileme maddesi** varsa riskli işaretlenir
- Gizlilik/KVKK: tesise giren personel, işlenen veri
- Devir/alt yüklenici izni

## 4. Kiralamada sorulacaklar

- Toplam maliyet: peşinat + kira × süre + bakım + sigorta + lastik/sarf + iade masrafı
- Kilometre/çalışma saati limiti ve aşım bedeli
- Bakım-onarım ve ikame (yedek araç/ekipman) taahhüdü, duruş süresi
- Erken iade/fesih cezası, hasar muafiyeti, sözleşme sonu satın alma opsiyonu
- Kiralama ↔ satın alma karşılaştırması: NBD ile (bkz. `finansal-degerlendirme.md`)

## 5. Elemeli kapı — genel alımda asgari şartlar

Şartname yoksa yalnız idari kapı uygulanır (bkz. `sartname-yoksa.md`). Şartname veya
gereksinim listesi varsa tipik asgari şartlar: zorunlu belge (MSDS, gıda temas, mesleki
yeterlilik), MOQ'nun ihtiyaçla uyumu, teslim süresi üst sınırı, SLA yanıt süresi üst sınırı.

## 6. Risk kalemleri (risk matrisine eklenecek)

1. Tek kaynağa bağımlılık (ürün özel, muadil yok)
2. Sürekli alımda fiyat revizyon baskısı ve endeks maddesi
3. Stok tükenmesi / teslim gecikmesi → üretim duruşu
4. Spesifikasyon kayması (ilk parti uygun, sonrakiler farklı) → **numune + parti bazlı CoA**
   şartı önerilir
5. Hizmet alımında personel devri ve nitelik düşüşü
6. SGK/İSG müteselsil sorumluluk
7. Otomatik yenileme veya cezalı erken fesih ile sözleşmede kilitlenme
8. Kiralamada iade sonu hasar/masraf sürprizi

## 7. Nicel kıyas satırları (Teknik Detay sekmesi)

- Seçilen kıyas birimi başına maliyet (yukarıdaki tablo)
- Yıllık tahmini tüketim × birim fiyat = **yıllık maliyet** (tek seferlik tutar değil,
  sürekli alımda karar bu satırla verilir)
- Fiyat geçerlilik süresi ve revizyon riski
- SLA/teslim performansı taahhüdü

## 8. Bu dalın hesap kontrolleri

`hesaplama-kontrolleri.md` §1–2 uygulanır: ardışık iskonto, fiyat birimi, paket/MOQ,
kullanılabilir miktar, aktif madde ve bölünmüş siparişte kaybolan indirimler.
Kiralama/yazılımda aynı dönem için peşinat, periyodik ödeme, kurulum, yenileme artışı,
limit aşımı, çıkış/iade gideri ve iade edilecek depozito ayrı nakit akışlarıdır;
sabit kira × ay yalnız nominal bütçedir. Satın alma alternatifiyle NBD karşılaştırılır.
Genel alımın puan ağırlıkları ihtiyaca göre kurulup 100'e tamamlanır; makine/yapım
seti otomatik kopyalanmaz, uygulanmayan kriter çıkarılır.

## 9. Kalite ve stok kararları

Kalite kaybı, toplu indirim veya tekrarlayan tüketim varsa `nakit-kalite-stok.md`
§2–3 uygulanır. Teklifin ucuzluğu kullanılabilir çıktı ve uygulanabilir teslim
planıyla sınanır; yeni giderler mevcut nakliye/fire/finansman satırlarına ikinci
kez eklenmez. Nakit takvimi varsa aynı kaynaktan §1 de kurulur.
