# Çıktı ve kalite güvence

## Excel

Final v5.0.4 workbook karar-kritik turetilmis degerleri frozen snapshot'tan yazar ve formula-free tutulur. Kaynak metin formula-control karakteriyle baslarsa literal text olarak escape edilir.


Varsayılan sekmeler:

- Özet
- Envanter
- Teklif Karşılaştırma
- Ticari Koşullar
- Şartname Uygunluk (varsa)
- Kapsam ve Riskler
- RFI
- Kanıtlar
- Kaynak Otoritesi
- Veri Kalitesi
- Karşılaştırma Sözleşmesi
- Maliyet Köprüsü
- Bağımsız Hesap Kontrolü
- İddia Kaydı
- Kapsam Ledger
- Değişim Kaydı

Hızlı profilde gereksiz sekmeleri kaldır; yüksek güvencede uzman teyidi ve hesap detayını ekle.

Her görünür sonuç kaynak dosya ve locator'a geri izlenebilir olmalıdır. İç kimlikleri yönetici tablosunda göstermek zorunlu değildir; Kanıtlar sekmesinde saklanır.

## Mekanik QA

Kodla kontrol et:

- zorunlu sekmeler,
- final workbook icinde herhangi bir formula/formula-error tokeni (`#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`),
- boş kritik alanlar,
- duplicate fact/evidence,
- orphan evidence/fact,
- açık kritik issue ile çelişen final recommendation,
- currency/base-date uyumsuzluğu,
- source hash + hash-adresli source-archive kopyasi ve artifact parent hash zinciri,
- bozuk tarih ve negatif/anlamsız miktar,
- hidden sheet/row/column kaynak kaybı,
- external workbook links, formula-pattern anomaly ve pasted-over formula,
- reviewed snapshot -> Excel/decision/PDF lineage cross-output consistency,
- reviewed snapshot SHA parent zinciri ve artifact bindings,
- provenance survival: fact status/source/locator, claim class/caveat ve snapshot lineage,
- LLM schema-validation receipt tamligi,
- source-authority, comparability, grain integrity, independent recompute, cost-bridge residual, claim-support ve scope-ledger kapilari.

## Görsel QA

1. İlk final render'da profil gerektiriyorsa tüm sayfaları/sekme görünümlerini incele.
2. Her render için sayfa hash'i sakla.
3. Revizyonda yalnız değişen hash'li sayfaları tekrar görsel kontrolden geçir.
4. Önce mekanik sorunları kodla tespit et; vision yalnız layout/okunabilirlik/semantik görünürlük için kullanılsın.
5. Kesik metin, taşmış tablo veya okunaksız kritik alan varsa PASS verme.

## Teslim seviyeleri

- `VERIFIED`: kritik açık yok, kanıt-hesap-çıktı zinciri doğrulandı.
- `PRELIMINARY`: analiz yararlı fakat kritik bilgi/karşılaştırılabilirlik eksiği var; kesin öneri yok.
- `BLOCKED`: kaynak/parse/schema/QA güvenilir değil.

## Coverage kaydi

`coverage.py` source-authority, value accuracy, evidence integrity, independent review, data quality, comparability, independent calculation, cost bridge, grain integrity, claim support, reviewed snapshot, provenance survival, scope completeness, cross-output consistency, conclusion support, visual QA ve decision completeness kategorilerini scoped unit bazinda kaydeder. Her unit kendi revision hash'ini tasir.

`Observed defects = bad/total` olarak yorumlanir. `0/N`, N birimin tam dogrulandigi anlamina gelmez; unverified sayisi Assessment'ta gorunur kalir. Yuksek guvencede kritik unverified coverage `BLOCKED` olabilir.

## Cross-output acceptance

`cross_output_consistency.py` haritalanmış kritik alanları frozen reviewed snapshot değerleriyle karşılaştırır. Yaklaşık değer toleransı ile fiyat uyuşmazlığı gizlenmez. `provenance_survival.py` değer eşitliğinden ayrı olarak status/source/locator/caveat/claim-class lineage'ını denetler. PDF için snapshot + workbook parent hash zinciri kanıtlanır; ayrıca okunabilir PDF metninde tedarikci, kritik tutar/maliyet ve karar durumu kontrolleri yapılır. Yüksek guvence ilk kabul turunda gereken full visual review ayrica tamamlanmadan `VERIFIED` verilmez.

## Aynı sayfanın gerekçeli yeniden incelenmesi

Tamamlanmış bir görsel görevin sonucu üzerine yazılmaz. Görüntü değişmeden önceki incelemenin yanlış olduğu düşünülüyorsa `visual_recheck.py create` ile önceki görev, açık bulgu ve sayfa kimliğine bağlı ayrı görev oluşturulur. Somut gerekçe zorunludur; isteğe bağlı büyütülmüş görüntüler de SHA ile sabitlenir. Yeni görev yalnız seçilen tam sayfayı değerlendirir; büyütülmüş görüntü ek kanıttır.

```powershell
python scripts/visual_recheck.py create --run "RUN" --previous-task-id "TASK" --finding-id "FINDING" --render-key "page:20" --reason "Önceki bulgunun görüntüyle çeliştiği bölümün açıklaması" --supplementary-image "CROP.png"
```

Yeni görev normal bağlam dağıtımı, katı yanıt şeması ve gerçek model/efor/token makbuzu kapılarından geçer. Yeni PASS tek başına eski FAIL'i kapatmaz. Tam sayfa ile ek görüntüler bağımsız kontrol edildikten sonra ayrı gerekçeyle benimseme kaydı oluşturulur:

```powershell
python scripts/visual_recheck.py adopt --run "RUN" --recheck-id "RECHECK" --reason "Görünür kanıta dayanan benimseme gerekçesi"
```

Eski görev, bulgu ve makbuz korunur; hedef bulgu gerekçeli yeni kayda bağlanır. Başka açık hatalar, bekleyen sayfalar veya kaynak/hesap sorunları bu işlemle kapanmaz. Değişmiş belge/görüntü, yanlış sayfa, eksik/tekrarlı sayfa yanıtı, eski dağıtım paketi ve başarısız yeni inceleme kabul edilmez. Kod sözleşmesi değişen eski koşuya yeni kod zorla uygulanmaz; bağımsız aday koşusu hazırlanır.
