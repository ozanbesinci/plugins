# 5.0.18 veri, kaynak ve güncelleme sözleşmeleri

Yazılım kabulü, koşunun bilgi yeterliliği ve satınalma kararı ayrı sonuçlardır. Şartname/finans/otorite eksikliği tamamlanmış bir koşuda gerekçeli PRELIMINARY olabilir; pending görev, bozuk kaynak veya çıktı kaybı BLOCKED olur. Hiçbiri kesin firma seçim yetkisi vermez.

## Kaynak ilişkisi

`python scripts/source_relations.py --run "<koşu>" --source-document "<kimlik>" --target-document "<kimlik>" --relation corroborates --declaration "<beyan.json>"`

Beyan: `{"authority":"Açık beyanı veren kişi veya test yazarı","reason":"Aynı ticari teklif için ayrı kayıt gerekçesi","same_offer_confirmed":true,"independent_capture":true}`. Bu beyan model tarafından dayanak olmadan oluşturulamaz. Kaynakla veya açık kullanıcı beyanıyla doğrulanmamış ilişkiler, dosya adı ya da fiyat tahminine dayanılarak kurulamaz.

İlişki çıkarım görevleri tamamlanmadan kaydedilir; belge kimlikleri ayrı, firması aynı, aktif kaynak baytları kayıt hashleriyle eşleşmiş olmalıdır. Aynı bayt kopyası bağımsız teyit değildir. Görsel teyidinde hedef görsel, kaynak ayrı okunabilir yapısal kayıttır. Mevcut mekanik teyit açık Excel hücre alanlarını değerlendirir; diğer biçimler yalnız ilişkiyle doğrulanmış sayılmaz. Miktar birimi boşsa veya para/miktar/ürün/tarih eşleşmiyorsa teyit yoktur. Çok kalemli veya çelişkili görüntü belirsizliği tek skalar eşitliğiyle kapatılmaz.

`supersedes` ayrı ticari teklifler için açık eski/yeni ilişkisini kaydeder; `independent_alternative` beyanı teklifleri ayrı tutar. Bağımsız alternatifin bulunması tek başına güncel karşılaştırma otoritesini çözmez; gerekli RFI korunur.

## Uyumluluk ve yeniden deneme

Koşunun `execution_contract` kaydı çalıştırılan Python/JSON/SQL baytlarını pinler. Context dosyası ve sonuç şeması her görevde ayrıca pinlenir. Sözleşme değişimi eski run'a otomatik yeni onay veya bağımlılık dönüşümü sağlamaz: mevcut koşu salt korunur; aynı kaynak/profil/tarih/finans verisiyle yeni koşu gerekir. Kontrol ilgisiz README açıklamasını yürütme değişikliği saymaz.

DB dönüşümü yalnız desteklenen şema sürümünü mevcut kolonu kontrol ederek dönüştürür; ALTER başarısızsa güncel sürüm etiketi yazılmaz. Bu işlem çalışma kodu uyumluluğunun yerine geçmez. Kaynak sonuçlarının tekrar kullanımı yalnız aynı bounded context, sonuç şeması ve izinli kanıtlarla yapılabilir; gerçek eski makbuz ayrıca tutulur, yeni token sıfır olarak ayrılır.

Hatalı JSON yanıt sonrası context aynı baytlarla kalır. Yenileme zamanı/sayaçları iş girdisi değişikliği değildir; fiyat, profil, analiz tarihi, kaynak, kanıt veya talep değişirse eski context ezilmez ve eski yanıt kabul edilmez.

## Kapanış

`COMPLETE` kapanışı kanonik tablolar, görevler, gerçek makbuzlar/şema doğrulamaları, snapshot, QA ve çıktı envanterini hashler. Sonraki `next` veya `validate_run` çağrısı bu kapanışı ve fiziksel kaynak/arşiv/context/yanıt/çıktı baytlarını salt okunur inceler. Bozulmuş koşuyu kendiliğinden yeniden üretmez veya eski onayı geri vermez; ayrı düzeltme/kabul koşusu gerekir.

## Kalem ve bedel

Bir kalem fiyatı beyan genel toplamı değildir. Hesaplanan kalem toplamı kaynak skalarından ayrı tutulur ve kendi durumuyla görünür. Teyitsiz kalem, eksik çarpan veya karma fiyat türünde aritmetik toplam karar verisi olmaz. Birim fiyat ve satır toplamı aynı ticari satırın iki görünümüyse otomatik iki katkı oluşturulmaz; uzlaşma yoksa incomplete kalır. Kapsamın dahil/ek/belirsiz maliyet rolü iş tanımından ayrı tutulur. Kaynak sınıfı veya tedarikçi adı revizyon otoritesi değildir.


## 5.0.19 — Aşama ve kaynak girdisi sınırı

Görev önceliği yalnız aynı evre içinde geçerlidir. PREPARE bitmeden sonraki evre context’i pinlenmez. Firma ve kaynak ilişkisi beyanı bütün sınıflandırmalar bittikten sonra, ilk sınıflandırma dışı dispatch öncesinde tamamlanır. Geç ilişki isteği herhangi bir kanonik değişiklikten önce reddedilir; context değiştirilmez. DB şeması 5.0.18 kalır, çalışma sözleşmesi yeni koda bağlanır.
