---
name: teklif-maliyet
description: Tekliflerin doğrulanmış kalem/kapsam/ödeme/finans girdilerini mevcut Python motoruyla hesaplar ve maliyet farkını mutabıklaştırır. Ana teklif akışında maliyet hesabı gerektiğinde kullan; model aritmetiği, kaynak yorumu ve bağımsız onay üretmez.
---

# Maliyet Hesabı — 5.1.0
## Kullanıcı kanıtı önceliği

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir.

Hesabı geçerli kullanıcı girdisiyle yeniden üret; belgedeki eski miktar veya koşulun kullanıcı düzeltmesinin önüne geçmesine izin verme. Bağımsız aritmetik kontrol sürer.

[Kullanıcı Kanıtı ve Değerlendirme Önceliği](../../USER-EVIDENCE-POLICY.md) bütün aşamalarda uygulanır.

## Kurumsal dil

[Kurumsal Dil ve Yayın Standardı](../../EDITORIAL-POLICY.md) uygulanır. Kullanıcı soruları ve bütün çıktı metinleri resmî ve nesnel dille hazırlanır; kişisel hitap ve sohbet geçmişine atıf kullanılmaz.

## Her çağrıda başlangıç bildirimi

Bu beceri fiilen çalışmaya başladığında, ilk kullanıcı mesajında ortak okuyucunun ürettiği satırı aynen göster. Kendi paketindeki `../../scripts/skill_startup.py --skill teklif-maliyet` komutunu kendi fiziksel skill klasöründen çalıştır; başka plugin'in aynı adlı skill'ini genel adla çağırma. Okuyucu gerçek beceri adını ve o çağrıdaki VERSION dosyasını kullanır:

**[Beceri adı] skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: [gerçek sürüm]**

Köşeli alanlar yalnız şablondur; kullanıcıya gösterilmez. Ad veya sürüm kaynağı eksik/bozuk/çelişkiliyse hatayı bildir ve becerinin asıl işlemini başlatma. Plugin sürümünü skill sürümü yerine yazma.

Ana akış bir alt skill'in görevini başlatacaksa ana ajan o alt skill'in gerçek satırını kullanıcı kanalında **görev dispatch'ından önce** gösterir. Alt ajan kullanıcıya ayrı mesaj göndermez ve görev JSON'una bildirim öneki eklemez. Yalnız bir referansı okumak veya sıradaki adım olarak bir skill'den bahsetmek bildirim gerektirmez. Başka bir gerçek çağrı başladığında tekrar göster.

Ana giriş [Teklif Değerlendirme](../teklif-degerlendirme/SKILL.md). Doğrudan çağrılmışsan önce onu oku ve aynı run'a bağlan; ikinci prepare/DB açma. Mevcut run/task/context yoksa ana başlangıca dön. [Ortak sözleşme](../teklif-degerlendirme/references/module-contract.md) kimlik, strict şema, kanıt, soru, makbuz ve yetki sınırlarını belirler. Model alt görevinde yeni alt ajan açma.

## Sorumluluk

Hesap öncesinde [Analiz birimi ve üyelik](../teklif-degerlendirme/references/analysis-quality-workflow.md#analiz-birimi-ve-üyelik) yöntemini uygula; toplam eşitliğinin yanında doğru kaynak/kalem kümesini doğrula.

Tek hesap motoru ana skill'in scripts/procurement_engine.py ve procurement_math.py dosyalarıdır. LLM sonuç hesaplamaz, ikinci maliyet motoru veya ayrı DB yazma. Yalnız kaynak/kullanıcı destekli açık ve karşılaştırılabilir girdilerle Python/DuckDB hesabını çalıştır.

Kalem kendi quantity/unit, amount_basis, currency, evidence_status ve evidence_refs'iyle doğrulanır. Birim fiyat/satır toplamı/beyan toplamını ayır; karışık fiyat türlerini ve ayrı teklif revizyonlarını toplayıp tek tutar yapma. Bilinmeyen tutar sıfır değildir. Ardışık indirim çarpımlıdır. Dahil kapsamı iki kez ekleme, ortak/firmaya özel kapsam boşluklarını ayır.

Kur, efektif iskonto, değerleme tarihi, vergi ve ödeme tarihinin başlangıcı verilmediyse PV/TCO/tek para sıralaması üretme; ana ajana gereken soru ve etkilenen hesap ID'lerini ilet. Kullanıcı yanıtı yeterli değilse hesap eksik kalır. Nominal brüt tutar ile karşılaştırılabilir/net/PV maliyetini ayır.

Önce grain/data_quality/otorite ve comparison_contract kapıları; elemeli uygun küme puandan önce. Fiyat kümesi karşılaştırılabilir maliyet altkümesi, ağırlıklı küme geçerli kriter puanlı uygun tekliflerdir; eksik kaynak bu ayrımda kaybolmaz. Cost_bridge açıklanan fark + residual mutabakatıdır; bilinmeyen fark açıklanmış sayılmaz.

## Dönüş

Teknik hesap istisnası FAIL/BLOCKED ve kaynak/hesap kimliğiyle ana ajana döner; kullanıcıdan hesabı doğru kabul etmesi istenmez. Ana hesap sonucu ve input hash Bağımsız Kontrol'e karşılaştırma hedefi olarak gönderilir; PASS kararı bağımsız kontrole aittir. Ürün motorunda bulunmayan erken bekleme kontrolü uygulanmış olarak gösterilemez.

Yöntem: [cost-and-finance-rules](../teklif-degerlendirme/references/cost-and-finance-rules.md). İthalatta yalnız gerektiğinde [import-tco-rules](../teklif-degerlendirme/references/import-tco-rules.md).
