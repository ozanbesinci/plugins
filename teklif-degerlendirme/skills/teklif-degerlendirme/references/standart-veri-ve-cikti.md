# Merkezi veri, kanıt ve çıktı sözleşmesi — v4

Kaynak belge yorumunu model; kimlik, tamlık, hesap, karşılaştırma ve dosya üretimini
kod yapar. Merkezi sözleşme `teklif-data/v4` türündedir. Üretimde sözleşmenin çalışan
doğrulayıcısı `scripts/veri_kontrol.py`; hesap girdileri `motor-kullanimi.md`'dedir.
Ek alanların varlığı, doğrulanmamış bir hesabın desteklendiği anlamına gelmez.

## Kimlikler ve kaynaklar

- Envanter her özgün dosya için `source_id`, `relative_path`, `sha256` ve byte
  boyutu taşır. Kod kaynakları hashler; ajan hash üretmez veya tahmin etmez.
- `offers`: `id`, bağımsız tedarikçiyi gösteren `supplier_id`, `name` ve
  `source_ids` kaynak kimliği listesi. Liste kaynak-kapsam kaydındaki firma
  eşlemesiyle birebir aynı olmalıdır.
  Aynı firmanın alternatifleri farklı teklif kimliği, aynı tedarikçi kimliği taşır.
  `lines` varsa her kalem benzersiz `id` ve bilinen quantity/unit_price/vat_rate
  girdileri için `bindings` (alan → fact_id) taşır. Hakem düzeltmesi kalem girdisine
  de uygulanır; kaynak değerini tutup eski kalem hesabını bırakma.
- `requirements`: özgün madde numarasına bağlı benzersiz `id`, gereksinim,
  `category:mandatory|preference|information` ayrımı. Şartname yoksa boş liste;
  teklif şartnameye çevrilmez. `context.has_spec:true` iken ayrı requirements
  görevinin sonuç JSON'undaki `requirements` listesi boş olamaz. Merkezi liste,
  görev çıktılarının kimlik bazında birleştirilmiş içeriğiyle birebir eşleşir;
  çıkarılmış madde sessizce düşürülemez veya değiştirilemez.
- `analysis_date` ISO tarihtir. Teklif tarihi ve geçerlilik sonu ayrı olgulardır.

## Olgu kayıtları

`facts` bir listedir; her satır tek `fact_id` taşır. Çıkarım ile bağımsız okuma aynı
kimlik sözleşmesini kullanır:

| Kimlik | İçerik |
|---|---|
| `<teklif>/field/<alan>` | Sabit kritik firma alanı |
| `requirement/<madde-id>` | Şartname gereksiniminin özgün hükmü |
| `<teklif>/requirement/<madde-id>` | Firmanın gereksinime uygunluk hükmü |
| İşe özgü kararlı kimlik | Kapsam, ek, çelişki veya diğer bulgu |

Kritik alanlar: `total`, `currency`, `vat`, `quantity`, `quote_date`,
`validity`, `delivery`, `payment`, `incoterms`, `warranty`. Alan kaynakta yoksa
kayıt atlanmaz; `missing` durumuyla tutulur. Tarih olgularında doğrulanmış değer
`YYYY-MM-DD`; “30 gün geçerli” ifadesinde özgün metin saklanır ve son tarih kodla
teklif tarihinden türetilir. Tarih yoksa son gün uydurulmaz.

Örnek olgu:
```json
{
  "fact_id": "F1/field/currency",
  "value": "EUR",
  "critical": true,
  "evidence_status": "verified",
  "source_id": "<envanterden>",
  "source_sha256": "<envanterden>",
  "location": "PDF s.2, fiyat tablosu",
  "quote": "Toplam teklif bedeli: ... EUR"
}
```

Kanıt durumları:

- `verified`: özgün kaynak, konum ve kısa alıntıyla doğrulanmış.
- `missing`: belgede belirtilmemiş.
- `excluded`: açıkça hariç; kaynaktan alıntı zorunlu.
- `unreadable`: okunamayan; hangi sayfa/hücre olduğu belirtilir.
- `conflicting`: kaynaklar veya aynı belgenin maddeleri çelişiyor; kanıtları göster.
- `assumption`: açık varsayım; gerekçe ve kullanıcı teyidi ihtiyacını göster.

Doğrulanmamış olguya `open_issue` ve `fact_ids` üzerinden muhataplı RFI bağlanır.
Kritik bilgi, ön sonuç üretmek için kritik olmaktan çıkarılmaz. `excluded` ile
`missing` fiyatlanmamış maliyetin aynı olduğu anlamına gelmez.

## Tamlık ve karar girdileri

- `rfi`: her satır `owner`, `question`, `fact_ids`; muhatap firma, TÜM FİRMALAR
  veya İDARE. Önceki revizyonda cevapsız kalan sorular korunur.
- `scope_items`: ilgili `fact_ids`, 5-A/5-B sınıfı, muhatap ve maliyet durumu.
  Kapsam olgusu `kind:"scope"` olarak işaretlenir. Her belirtilmemiş/hariç kapsam
  için maliyet adayı veya `scope_not_applicable` içinde gerekçe vardır.
  Her kapsam kaydının benzersiz `id` ve `classification` alanı vardır. 5-A'da
  `offer_id`; 5-B'de bütün teklifleri kapsayan `allocations` satırlarında offer_id,
  amount, currency, payment_date ve fact_ids bulunur. 5-B tutar/döviz/ödeme tarihi
  bütün firmalarda aynı ve kanıtlı olmalıdır; bilinmeyen gider 5-B olamaz.
- `exclusions`: uygunsuzluğa bağlı `fact_ids`, karar ve `reason`.
  Bir gereksinim hükmü `noncompliant` ise eleme değerlendirmesi atlanamaz.
- `costs`: teklif kimliği → motorun `cost_summary` girdisi. Olay kimlikleri
  benzersizdir; tutar, kur, oran, ödeme tarihi ve kapsamın dayandığı olgularla bağ kur.
  Bilinen olayda `bindings` nesnesinin `amount`, `currency`, `payment_date`
  anahtarları ilgili olgu kimliklerini gösterir; değerler olgularla birebir aynı
  olmalıdır. Payload `assumption_sources` alanı oran/kur/yöntem parametrelerinin
  dayanağını açıklar. Bilinmeyen olay `known:false`, `fact_ids` ve RFI bağlantısı
  taşır; tutarı sıfır yazılmaz. Bilinen toplam nihai KTM değildir.
- `scoring`: yalnız elemeli kapı ve maliyet tamamlandığında, en az iki bağımsız
  uygun tedarikçi için motorun puanlama girdisi. Alternatifler tedarikçi sayısını artırmaz.
  Her criteria satırında `bindings`, bütün supplier_id değerlerini dayanağa bağlar:
  maliyet için `{kind:"cost",offer_id:"A",metric:"known_present_value_in_base_currency"}`;
  diğer sayısal ölçüt için `{kind:"fact",fact_id:"<doğrulanmış-olgu>"}`.
  `values` bu bağlardan kodla bulunan değerlerle aynı olmalıdır. Hakem düzeltmesi
  uygulandıktan sonra maliyet ve puan girdileri bu bağlardan yeniden türetilir.
  Karşılaştırılan maliyetlerin base_currency ve base_date alanları aynı olmalıdır.
  Maliyet puanlamasında aynı dövizin kur ve iskonto oranı setleri de aynı olmalıdır;
  USD tutarı TRY tutarıyla veya farklı değerleme günleriyle doğrudan kıyaslanamaz.
  İki veya daha çok ölçütte `sensitivity` en az iki alternatif içerir:
  `{id,label,weights:{criterion_id:"ağırlık"}}`. Ağırlık toplamı100, alternatifler
  bazdan ve birbirinden farklı olmalıdır. Baz+alternatiflerin puan/sıra sonuçları
  Excel'de görünür; tek ölçütte ağırlık alternatifinin neden olmadığı açıklanır.

Mekanik tamlık geçişi, belgenin anlamının doğru yorumlandığına tek başına kanıt değildir.
Kaynak kapsama kaydı (`coverage`) her dosyayı `source_id`, `source_sha256`,
`status` (`read`, `unreadable`, `not_applicable`), `locations`, `notes` ve
`document_kind` (`offer`, `specification`, `support`, `unreadable`) ile tek tek
gösterir. Türü `offer` olan dosyada boş olmayan `offer_ids` bulunur. Bütün
kayıtlardaki teklif kimlikleri merkezi `offers` kümesiyle, her teklifin `source_ids`
listesi de o teklife bağlanan kaynaklarla birebir örtüşür. Okunamamış dosya
gerekçesi kaybolmaz.

## Bağımsız okuma ve düzeltme

Bağımsız sonuç aynı `facts` kimlikleri ve `free_notes` listesiyle kaydedilir.
`reviewed_source_ids` bütün envanter kaynaklarını, `offer_ids` bütün merkezi
teklifleri kapsar. Merkezi verideki bütün kritik alan/hüküm kimlikleri bağımsız
sonuçta bulunur; doğrulanamayan alan atlanmaz, açık `missing` kaydıyla verilir.
Okunamayan kaynaklar serbest notta belirtilir; kimliğini listelemek okundu kanıtı değildir.
Hızlı profilde ayrıca `image_reviews` listesi vardır: source_id, koşuya göreli
image_path, image_sha256, location ve observations. Her kritik kaynağın özgün sayfa
görüntüsü açılıp incelenir. PDF sayfaları `ortam_ve_belge.py --source ... --output ...
--pages 1,3` ile metinli sayfalar dahil üretilebilir; yalnız metin çıkarımı yeterli değildir.
Serbest notlar eşleşmiyor diye düşürülmez; hakeme gider. Kodun fark dosyası
`teklif-diff/v4`, `data_sha256`, `blind_sha256` ve `differences` taşır.

Hakem dosyası güncel `data_sha256`, `diff_sha256` ve her `difference_id` için
tek `decision` (`main` / `independent` / `open`) ile `reason` taşır.
Değişecek olgu `replacement` içinde tam kaynak kanıtıyla verilir. Yüksek güvencede
`decision_reasons_sha256`, eleme ve öneri gerekçelerinin ayrıca incelendiği kayda bağlanır.

Kod `apply` ile düzeltmeyi uygular. Etkilenen maliyet girdisi, Excel hücresi ve
karar özeti yeni veri hash'ine bağlanır; eski sayısal sonucu yeni olguya kopyalama.
Hakemin `open` kararı açık konu kalır; çıktı kesin öneri içeremez.

## Excel ve karar özeti

`excel_uret.py` merkezi JSON'dan profil dosyasını üretir; `excel_dogrula.py`
gerçek Excel ile hesaplatıp sayısal mutabakatı, parametre geri alma testini ve düzeni
raporlar. Üreticiye desteklenmeyen alan eklendi diye hesap doğrulanmış olmaz.
Girdi/hücre bağı ve kontrol raporu saklanır. `qa` hakem öncesi taslağı ve ucuz
mekanik preflight'i otomatik üretir. Gerçek COM yalnız son karar Excel'inde çalışır.

`decision` dosyası `data_sha256`, `summary`, `recommendation` taşır. Metin yeni
`decision_summary` GPT-6.1/High görevinin gerçek oturumundan gelir; kod son veriyle bağlar. Kritik açık konu varsa
`recommendation:null`. Profil düşürme varsa somut gerekçe summary içinde görünür.
Yüksek güvencede çözülemeyen uzman konuları, muhatap ve istenen teyitle ayrıca listelenir.
Üretici ve doğrulayıcıya bu ayrı karar JSON'u `--decision` ile verilir; hesap
sözleşmesi ve Excel makbuzu `decision_sha256` taşır. Merkezi verideki eski metin,
bağımsız son karar dosyasının yerine geçirilmez.
Son üretime güncel QA ve envanter de verilir. Sözleşmenin profil,
inventory_sha256 ve qa_sha256 bağları teslim kapısında kontrol edilir.
