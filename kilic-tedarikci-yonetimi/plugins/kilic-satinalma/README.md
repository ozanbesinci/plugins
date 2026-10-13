# Kılıç Tedarikçi Yönetimi 1.3.3

Teklif Değerlendirme **5.1.3** ve paket içi Güncelleyici **2.3.1** içerir. Kılıç Satınalma Departmanı tarafından geliştirilmiştir.

Teklif akışı bir ana beceri ve beş alt beceriden oluşur: Belge ve Kaynak, Kapsam ve Ticari Koşullar, Maliyet Hesabı, Bağımsız Kontrol, Karar ve Rapor. Tek koşu, kaynak/hash/kanıt, gerçek model makbuzu ve ortak Excel/PDF veri özeti korunur. Her beceri kendi gerçek adı ve VERSION kaynağıyla başlangıç bildirimi gösterir.

## Bu sürüm

Yalnız kullanıcı sorusunun cevabına bağlı ajan ve işler durur. Soru anında çalışan bağımsız işler devam eder. Bekleme süresiz ve kalıcıdır; bağlı dispatch, araç/model, sonuç kaydı, hesap, rapor ve güncelleyici girişleri korunur. Aynı kaynak kapsamındaki cevaplanmış soru tekrar gösterilmez. Kısmi veya ilgisiz yanıt işi başlatmaz; “bilinmiyor” yanıtı eksik ticari değer üretmez.

Kullanıcının seçtiği teklif nüshaları hash bağlı kaynak otoritesi kaydıyla uygulanır. “KDV dahil değildir” ifadesinin doğru sınıflandırılması düzeltilmiştir. Kaynak kanıtı, satınalma onayı, miktar/fiyat doğruluğu, bağımsız kontrol ve gerçek QA kuralları korunmuştur.

## Değerlendirme ve rapor sınırı

Tek çok sekmeli formüllü Excel ve çok sayfalı PDF aynı dondurulmuş inceleme kaydından üretilir. Kullanıcı varsayımları kaynak verisinden ayrıdır. Bilinmeyen maliyet, tarih ve kur sıfır yapılmaz. Dosyanın oluşması VERIFIED veya satınalma onayı değildir. Yıllık gider, çok adımlı ödeme ve ayrı tarihli nakit akışı önceki kapsamıyla korunur.

Paket içi Güncelleyici 2.3.1 yalnız yanıta bağlı aktör kontrollerini ekler; kurulum yetkisini genişletmez. Güncelleyici kullanıcı seçimi ve somut plan için açık uygulama onayı gerektirir. Teklif analizi kendiliğinden program kurmaz. Ayrı Güncelleyici deposu yayını ve canlı kurulum bu sürümün kapsamı değildir.

Güncel [yayın kabulü](skills/teklif-degerlendirme/references/RELEASE_ACCEPTANCE_5.1.3.md) ve [manifest](release-manifest.json) geçerlidir. Son kaynak ağacına bağlı gerçek test JSON/logları GitHub release ile birlikte verilir; tarihsel test sayıları güncel sonuç olarak sunulmaz. Business eşitlemesi ve görünen sürüm ayrıca doğrulanır.

[Kullanıcı Kanıtı ve Değerlendirme Önceliği](USER-EVIDENCE-POLICY.md) ve [Kurumsal Dil ve Yayın Standardı](EDITORIAL-POLICY.md) bütün teklif becerilerine uygulanır.
