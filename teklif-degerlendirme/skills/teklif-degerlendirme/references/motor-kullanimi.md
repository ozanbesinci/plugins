# Teklif Motoru — JSON Hesap Arayüzü

`scripts/teklif_motoru.py`, teklif değerlendirmedeki aritmetiği dil modelinden ayıran saf Python motorudur. Ağ, Excel, güncel kur/faiz/vergi verisi veya iş girdisi üretmez. Bu nedenle gerçek dosyadan çıkarılan tutar, oran, tarih, para birimi ve kaynak bilgisi çağıran süreç tarafından açıkça verilmelidir.

## Çalıştırma

Skill kökünden örnek kullanım:

```powershell
'{"operation":"fx_convert","payload":{"amount":"10000","forex_selling":"30","unit":"100"}}' | python scripts/teklif_motoru.py
```

İstek ve cevap tek JSON nesnesidir. JSON sayıları ya metin olarak verilmeli ya da JSON sayı olmalıdır; motor bunları `Decimal` olarak okur. Çıktıda parasal ve hesaplanmış rakamlar hassasiyet kaybını önlemek için metindir. Başarılı cevap `{"ok":true,"result":...}`; girdi/hesap hatası `{"ok":false,"error":"..."}` ve süreç çıkış kodu `2` olur.

## İşlemler

### `price_line`

Zorunlu alanlar: `quantity`, `unit_price`, `vat_rate`. İsteğe bağlı: `price_unit` (varsayılan `1`), `discounts` (ardışık oran listesi), `price_includes_vat` (varsayılan `false`).

Kaynakla teyitli bedelsiz kalem için birim fiyat sıfır olabilir; negatif birim fiyat
kabul edilmez. Bilinmeyen fiyat sıfır olarak girilmez. KDV oranı her zaman açıkça verilir. Ardışık indirimler toplanmaz: `brüt × (1-d1) × (1-d2)`. Sonuçta `gross_before_discount`, `discount_amount`, `net_excluding_vat`, `vat_amount`, `total_including_vat` döner. Kur, fiyat ve KDV aynı şey değildir; bu işlem para birimi çevrimi yapmaz.

### `fx_convert`

Zorunlu alanlar: `amount`, `forex_selling`, `unit`. Dönüşüm tam olarak `amount × forex_selling / unit`dir. Kur tarihi, türü ve kaynağı bu küçük arayüzün dışında kalır; çağıran kayıt bunları kaynak veride tutmalıdır.

### `dated_npv`

Zorunlu alanlar: `base_date` (`YYYY-AA-GG`), `annual_rates` (`{"TRY":"0.40","EUR":"0.04"}` gibi), `events`.

Her olayda `event_id`, `amount`, `currency`, `payment_date` zorunludur. Yöntem yıllık efektif oran ve ACT/365 gün sayımıdır:

`NBD = tutar / (1 + kendi_para_birimi_yıllık_oranı)^((ödeme_tarihi − değerleme_tarihi)/365)`.

Her para biriminin kendi oranı zorunludur; eksik oranla hesap durur. Ödeme tarihi değerleme tarihinden önce olamaz. Sonuç para birimine göre ayrıdır; farklı para birimleri kendiliğinden toplanmaz.

### `cost_summary`

`dated_npv` alanlarına ek olarak her olayda `owner` ve `known` zorunludur. `known:true` olayları için `amount` gerekir. Her `event_id` benzersizdir; aynı kimlik ikinci kez gelirse motor hata verir. Böylece aynı navlun, KDV, banka gideri veya iade iki KTM basamağına sessizce yazılamaz.

`known:false` maliyetler toplamda sıfır sayılmaz; henüz bilinmeyen tarih/para birimi
bu kaydı bilinen tutara çevirmek için uydurulmaz. Çıktı `status:"known_subtotal_not_final"` ve `unknown_event_ids` döner. Bilinen hiçbir maliyet yoksa toplam üretilmez. Hiç bilinmeyen kalem kalmadığında durum `complete_cost_inputs` olur; bu yalnız sayısal maliyet girdilerinin tamamlandığını söyler, kaynak uygunluğu, şartname uygunluğu, mali/hukuki teyit veya analiz/karar onayı değildir. İsteğe bağlı `base_currency` ve `fx_rates` birlikte verildiğinde, bütün bilinen para birimleri için açık `{"forex_selling":"...","unit":"..."}` kuru gerekir ve bilinen NBD tek para birimine çevrilir.

### `cash_peak`

Zorunlu `events` alanındaki olaylar `event_id`, `amount`, `currency`, `payment_date` taşır. Pozitif tutar alıcı nakit çıkışı, negatif tutar iade/giriştir. Motor olayları tarihe göre kararlı biçimde sıralar; aynı gün ödeme önce, iade sonra verildiyse giriş sırası korunur ve aylık netleştirme tepeyi gizlemez. `currency` verilmemiş olsa bile bütün olaylar aynı para biriminde olmak zorundadır; dövizler önce açık kurla çevrilmelidir. İsteğe bağlı `available_cash` ile `peak_additional_financing_need` verilir.

Tepe nakit bir KTM ilavesi değildir; yalnız nominal likidite ihtiyacıdır.

### `score_suppliers`

`suppliers` dizisinde her satır `supplier_id` ve elemeli kapı sonucu olan `eligible:true/false` taşır. En az iki uygun tedarikçi yoksa motor puanlama yapmaz. Elenenler görünür kalır ama MIN/MAX/puan referansına girmez.

Her `criteria` satırı `criterion_id`, `weight`, `direction`, tüm tedarikçiler için `values` taşır. Ağırlıkların toplamı tam `100`, her ağırlık negatif olmayan sayı olmalıdır. `direction`: `lower` (düşük iyi), `higher` (yüksek iyi), `direct` (0–10 olarak verilmiş öznel puan). `method`: nicel kriterde `proportional` varsayılanı veya yalnız en az beş uygun tedarikçide izinli `range`.

Sonuç 0–10 ölçeğinde toplam puan, sıra, elenen tedarikçiler ve `distinguishing_weight` / `distinguishing_weight_ratio` içerir. Bütün uygun tedarikçilere aynı değeri veren kriterlerin ağırlığı ayırt edici değildir; raporda %30 ve %60 yorum eşikleri `puanlama-metodolojisi.md` uyarınca uygulanır.

## Sınırlar

Eşit toplam puan aynı yarışma sırasını alır (1, 1, 3 gibi); giriş sırası bir kazanan
üretmez. `has_unique_top_score:false` benzersiz birinci olmadığını gösterir.
`top_tied_supplier_ids` en yüksek puanı paylaşanları listeler. Tek başına benzersiz
puan da satınalma önerisi değildir; ayırt edici ağırlık ve kontrol kapıları ayrıca gerekir.

- Motor RFI açmaz, kaynak belge okumaz, Incoterms/gümrük/vergiyi yorumlamaz ve varsayılan oran üretmez.
- Yuvarlama politikası uygulamaz; teslim raporu veya Excel'de uygulanacak satır/genel toplam yuvarlama kuralı çağıran iş akışında açıkça seçilmelidir.
- Excel formülü veya `.xlsx` üretmez. Excel'in aynı formülleri bu motor çıktısıyla ayrıca mutabık tutulur.
- İşletme/TCO, kalite ve stok için yeni giderler `cost_summary` olayları olarak benzersiz kimlikle girilmelidir; motor bunların ticari kapsamının doğru olduğunu kendi başına doğrulamaz.

Test: `python scripts/test_teklif_motoru.py`. Mevcut `scripts/hesaplama_ornekleri_test.py` sentetik kontrol örnekleri ayrıca ve değiştirilmeden çalıştırılmalıdır.
