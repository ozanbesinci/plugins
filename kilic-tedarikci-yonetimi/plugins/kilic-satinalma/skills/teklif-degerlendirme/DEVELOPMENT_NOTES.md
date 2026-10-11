---
title: Kılıç 5.x rapor ve senaryo geliştirme dilimi
created: 2026-10-11
modified: 2026-10-11
type: development
status: 🟡 devam ediyor
tags: [is, kilic, gelistirme]
---

# Kod ile iş paketi eşlemesi

Bu aday, sabit başlangıç commit'i `f5f739d867a0de701ee4adf20854941a7d3c331c` üzerinde ayrı çalışma kopyasında geliştirilir. Kullanıcı GitHub ve Business yayınına yetki verdi; yayın ancak son sürüm kabulünden sonra yapılır. Bilgisayardaki üretim kurulumu ve güncelleyici kapsam dışıdır.

| Paket | Çalışan uygulama noktası | Bu dilimdeki değişiklik | Kabul sınırı |
|---|---|---|---|
| WP-001 | scripts/run_tests.py, db.py, test_engine_support.py | İki ayrı süreç; gerçek bağlantı sınıfı kontrolü; donmuş kaynak; ayrı PASS/FAIL/ERROR/SKIP/NOT_RUN kanıtı | Gerçek koşu JSON ve logları gerekir; eski 399 PASS yeni kanıt değildir |
| WP-047 | workflow.py, report_hooks.py, report_delivery.py, official_delivery.py, report_export.py, closure_integrity.py | Ön ve resmî raporda immutable çift revizyon; dosya doğrulaması/rename sonrası tek DB transaction; eski READY korunur; bağımsız PDF ve güvenli dizin alternatifi; kapalı koşunun yardımcı dosyaları da mühürlü | READY fiziksel teslimdir; analitik kabul ayrıca doğrulanır. Şirket belgeleri ve canlı modelle uçtan uca kabul açık |
| WP-048 | report_model.py, matrix_workbook.py | Teklif × madde; uygunsuz/belirtilmemiş/teyit/çelişkili/okunamayan ayrı; kaynak hash, firma, teklif, locator ve kritik etki | Otomatik teknik uygunluk kararı yok; birim dönüşümlerinin tüm iş kuralları ve kullanıcı esasları henüz tamamlanmadı |
| WP-046 | scenario_formulas.py, scenario_finance.py, finance_workbook.py, dated_cashflows.py, dated_workbook.py, scenario_import.py, report_export.py, qa.py | İzinli konum/ifade sözleşmesi; kaynak mühürü; sekiz formüllü grup, beş finans ve iki tarihli nakit sekmesi; 12 ödeme, KDV geri kazanımı, sabit/yıl bazlı gider/kalıntı NBD ve ayrı tarihli maliyet defteri; Excel'den yeni ön rapor çiftine varsayım aktarımı | En çok100yıl veya48nakit kaydı; açık kullanıcı kur/tarih/yöntem beyanı; hedef para365gün efektif NBD. Bağımsız deftere diğer sayfa toplamları eklenmez. Resmî puanlama politikası kurumsal teyit ister. Kapalı koşuya içe alma yerine yeni analiz gerekir |

Resmî raporlar aynı reviewed snapshot'tan üretilir. İş engeli raporları kaynak arşivleri doğrulanmış ayrı bir muhafazakâr model kullanır; calculation, ranking, decision veya reviewed snapshot statüsünü yükseltmez. Bütünlük bozuksa kaynak tutarları yayımlanmayan güvenli bildirim çifti denenir.

Excel yapısal formül kontrolü ile native yeniden hesaplama iki ayrı kanıttır. Formül yapısı PASS, cached sonucun hesaplandığı anlamına gelmez. Boş maliyet/formül girdisi sıfır değildir. Senaryo puanı bağımsız tedarikçi sıralaması değildir.

Negatif regresyonlar `scripts/tests/test_report_slice.py` ve motor kimliği testlerindedir. Gerçek sonuçlar devir paketinin `05_KANIT_VE_DEVIR/` klasöründeki koşu JSON/loglarına yazılır; bu not sonuç sayısı veya üretim kabulü beyan etmez.

Yeni özel regresyonlar: `test_official_atomic.py`, `test_scenario_finance.py`, `test_finance_workbook.py` ve `test_scenario_import.py`. Resmî dosya/metadata kesintisi ve kapalı model tahrifi, eksik ödeme/KDV/kur politikası, kaynak/formül tahrifi ve eski kaynak bazı reddi ayrı testlerdir.

`test_annual_costs.py`: değişken yıllık enerji/bakım/diğer giderler, bilinen sıfır ile eksik yıl/kategori ayrımı, nominal/NBD/senaryo tutarlılığı, dönem dışı/çift yıl/model reddi, Excel'den yeni çift rapora aktarım ve iki PDF yolunda görünürlük. Yıl ve formül hücreleri korunur; yalnız gider hücreleri ve model kullanıcı girdisidir. Eksik yıllık maliyet sabit modelin tutarıyla tamamlanmaz.

`test_dated_cashflows.py` ve `test_scenario_dates.py`: kaynak para tutarı/nakit tarihinde kullanıcı kur projeksiyonu/hedef para NBD,12maliyet türü,tamlık,negatif KDV geri dönüşü/kalıntı,tekil literal kimlik ve maliyet çift sayımı,gerçek takvim günü,1900sahte artık gün,tip/tarih/kur tahrifi ve kaynak korunması. Kullanıcı tam kapsam beyanı şirket onayı değildir. Eksik kur/tarih/maliyet türü toplamı boş bırakır.

WP-026: ikincil DuckDB PDF okuyucusu isteğe bağlıdır; yokluğu environment.json uyarısıdır. Birincil PDF okuma, ana DuckDB motoru ve rapor bağımlılıkları ayrı zorunlu kalır. Özel testte --require-pdf-extension açık gereksinimdir. Hiçbir ortam kontrolü paket veya extension kurmaz.

Kullanıcı Excel senaryosu açık ön raporda `python scripts/scenario_import.py --run <koşu> --workbook <kullanıcı-kopyası.xlsx>` ile alınır. İçe alma önce kaynak/model/sözleşme mühürlerini doğrular; yalnız mavi ve kilidi açık varsayım hücrelerini okur. Her iki dosyası doğrulanmış yeni ön rapor üretmeden IMPORTED dönmez. Kaynak facts, resmî snapshot ve decision_summary yazılmaz; senaryo sonucu firma önerisi değildir.

`office_execution.py` ve `excel_worker.py` native Excel yeniden hesabı/son PDF alternatifini kopya üzerinde ayrı süreçte çalıştırır. Varsayılan süre sınırı 45 saniyedir; sonuç kimliği ve çıkış kodu doğrulanmadan özgün rapor dosyası değiştirilmez. Süre aşımında yalnız kendi Python süreci sonlandırılır. Yeni Excel örneği için receipt + süreç oluşturulma zamanı + aynı handle üzerindeki kimlik kanıtlanabiliyorsa o örnek de sonlandırılır; sahiplik kanıtlanamıyorsa hiçbir Excel sürecine dokunulmaz ve izole kopya yolu kaydedilir. Bu durumda native hesap available:false kalır; iki bağımsız dosya yolu ve karar güvencesi ayrı değerlendirilir.
