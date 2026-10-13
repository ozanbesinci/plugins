---
name: teklif-karar-rapor
description: Doğrulanmış teklif analizinden tek gerekçeli satınalma eylemi önerisi, aynı snapshot bağlı Excel/PDF ve çıktı QA üretimini yönetir. Ana teklif akışının rapor/kapanışında kullan; eksik girdiyi tamamlamaz ve kullanıcı adına satınalma onayı vermez.
---

# Karar ve Rapor — 5.1.3
## Sorunun yanıtına bağlı bekleme

[Kullanıcı yanıtı bekleme kuralı](../../USER-EVIDENCE-POLICY.md#sorunun-yanıtına-bağlı-bekleme) zorunludur. Yalnız sorunun cevabına bağlı ajan ve işler durur; soru anında çalışan bağımsız ajanlar devam eder. Bekleyen ajan cevap gelene kadar araç/model çağrısı, okuma, hesap, yazma, rapor veya kontrol yapmaz; süre sınırı ve periyodik sorgulama yoktur. Soru kimliği/kapsamı ve bağımlı görev/ajan kimliklerini gösterimden önce kaydet. Yalnız ilgili yeterli yanıt bu bağımlılığı açar; “devam”, sessizlik veya seçili varsayılan cevap/onay değildir. Cevaplanmış soruyu sebepsiz tekrarlama.

## Kullanıcı kanıtı önceliği

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir.

Karar ve Excel/PDF kullanıcı teyidine dayalı geçerli girdiyi gösterir. Dayanak “Kullanıcı teyidi” olarak resmî biçimde belirtilir; belge değeri ve değişiklik izi korunur.

[Kullanıcı Kanıtı ve Değerlendirme Önceliği](../../USER-EVIDENCE-POLICY.md) bütün aşamalarda uygulanır.

## Kurumsal dil

[Kurumsal Dil ve Yayın Standardı](../../EDITORIAL-POLICY.md) uygulanır. Kullanıcı soruları ve bütün çıktı metinleri resmî ve nesnel dille hazırlanır; kişisel hitap ve sohbet geçmişine atıf kullanılmaz.

## Her çağrıda başlangıç bildirimi

Bu beceri fiilen çalışmaya başladığında, ilk kullanıcı mesajında ortak okuyucunun ürettiği satırı aynen göster. Kendi paketindeki `../../scripts/skill_startup.py --skill teklif-karar-rapor` komutunu kendi fiziksel skill klasöründen çalıştır; başka plugin'in aynı adlı skill'ini genel adla çağırma. Okuyucu gerçek beceri adını ve o çağrıdaki VERSION dosyasını kullanır:

**[Beceri adı] skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: [gerçek sürüm]**

Köşeli alanlar yalnız şablondur; kullanıcıya gösterilmez. Ad veya sürüm kaynağı eksik/bozuk/çelişkiliyse hatayı bildir ve becerinin asıl işlemini başlatma. Plugin sürümünü skill sürümü yerine yazma.

Ana akış bir alt skill'in görevini başlatacaksa ana ajan o alt skill'in gerçek satırını kullanıcı kanalında **görev dispatch'ından önce** gösterir. Alt ajan kullanıcıya ayrı mesaj göndermez ve görev JSON'una bildirim öneki eklemez. Yalnız bir referansı okumak veya sıradaki adım olarak bir skill'den bahsetmek bildirim gerektirmez. Başka bir gerçek çağrı başladığında tekrar göster.

Ana giriş [Teklif Değerlendirme](../teklif-degerlendirme/SKILL.md). Doğrudan çağrılmışsan önce onu oku ve aynı run'a bağlan; ikinci prepare/DB açma. Mevcut run/task/context yoksa ana başlangıca dön. [Ortak sözleşme](../teklif-degerlendirme/references/module-contract.md) kimlik, strict şema, kanıt, soru, makbuz ve yetki sınırlarını belirler. Model alt görevinde yeni alt ajan açma.

## Sorumluluk

Karar veya çıktı incelemesinde [Karar ve görünür çıktı](../teklif-degerlendirme/references/analysis-quality-workflow.md#karar-ve-görünür-çıktı) yöntemini uygula; görünür iddia, tutar, birim ve koşulun aynı kanıta bağlı olduğunu doğrula.

decision_summary yalnız güncel canonical karar paketini görür; ham belgeleri, başka model sohbetlerini ve sonradan tahmin edilen finans girdisini almaz. Model özeti kaynak/calculation/claim ID'lerine bağlı olmalı; unsupported claim kesin öneride kullanılamaz.

Karar için yeterli girdi ve snapshot olması **rapora hazır** durumudur; `VERIFIED` teslim değildir. Henüz rapor/QA/validate_run üretilmemişse `READY_FOR_REPORT` olarak bildir; VERIFIED yalnız gerçek son validate_run sonucuysa kullanılabilir. Özet modelinin iki tutarı çıkarıp yeni tasarruf/fark rakamı üretmesi hesap kanıtı değildir. Ayrı kaynaklı deterministik calculation/claim ID'si yoksa “98.000 EUR ve 99.000 EUR” gibi kanıtlı tutarları göster, yeni “1.000 EUR tasarruf/fark” iddiası yazma.

Tamamlanan analiz tek ana eylem ve gerekçeyle kapanır: firma/kapsam/kanıtlı tutar/ticari koşul/risk ve sonraki adım. Tam doğrulanmış girdide uygun firmayla ilerlemeyi önerebilirsin. Kritik ticari bilgi eksikse somut teklif/teyit yenileme talebi veya mevcut şartlarda alımı önermeme eylemi verir; zorla firma seçmezsin. Cevap bekleyen işi bitmiş sayma. Teknik hesap/QA BLOCKED başarılı karar teslimi değildir. Öneri, satınalma onayı/teklif kabulü/imza değildir.

Kesin karar öncesi çözülmemiş kullanıcı sorusuna dön. Cevabı bekleyen rapor görevi yanıt gelene kadar durur. Eksik fiyat/belge, tek tedarikçi veya tüm tekliflerin elenmesi, kullanıcı yanıtı beklenmeyen bir raporun üretimini tek başına durdurmaz. Tek XLSX/PDF çiftinde gerekçe, kapsam, kaynak ve sonraki aksiyon bulunur. Ön rapor teslimini soru çözümü veya VERIFIED olarak sunma; kullanıcı senaryolarını kaynak ve resmî karar hesabından ayrı göster.

Claim_registry + scope_ledger + bağımsız hesap ve yeterlilik kapılarından sonra reviewed_snapshot immutable dondurulur. Resmî Excel/PDF/özet aynı snapshot ve parent SHA'dan türetilir; canlı DB'den yeni değer ekleme. Artifact bindings kaynak/locator/status/claim/caveat'ı korur. `report_export.py` resmî çıktı yoludur; `report_delivery.py` kesin karar kapısını yükseltmeden ön rapor veya güvenli bildirim çifti üretir. Fiziksel arızada sınırlı alternatif yol denenir; iki dosya yoksa başarı denmez.

## Kapanış

Resmî aktif çıktı grubu `official_delivery.py` ile, ön rapor grubu `report_delivery.py` ile doğrulanır. Geçmiş sabit `output/` dosyasını güncel revizyon yerine kullanma. Excel'den içe alınan kullanıcı senaryosu yeni ön rapor çiftidir; resmî snapshot/karar veya kapanış güvencesini yükseltmez. PDF'de senaryo girdileri ve hesaplanan/bilinmeyen finansal değerler kaynak olgularından ayrı gösterilir.

Mekanik formül/kaynak/bütünlük QA, cross_output_consistency, provenance_survival, revision-aware coverage ve gereken görsel QA'dan sonra validate_run.py. artifact_visual_review yalnız paketteki renderlara bakar; mekanik PASS görsel inceleme değildir. Kaynak tutarlarını Excel/PDF ile elle mutabıklaştır; brüt tutar eşliği tüm maliyet hesabının doğrulandığı anlamına gelmez.

VERIFIED/PRELIMINARY/BLOCKED ve PASS/SKIPPED aşamalarını açık bildir; açık kritik girdi/coverage'i saklama. COMPLETE reentry salt okunur; değişen kaynak/artefakt/QA parent eski onayı geçersiz kılar. Görsel QA yeniden kullanımı yalnız ilgili içerik/snapshot/hash sözleşmesi aynıysa mümkündür.

Ayrıntı: [qa-and-output](../teklif-degerlendirme/references/qa-and-output.md); kapılar ve pinler için ana skill'in mevcut yürütme protokolü.
