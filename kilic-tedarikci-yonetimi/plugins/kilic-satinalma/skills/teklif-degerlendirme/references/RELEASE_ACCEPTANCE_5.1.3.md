# 5.1.3 — yanıta bağlı bekleme ve yayın kabulü

Plugin 1.3.3 altı teklif becerisini 5.1.3, paket içi Güncelleyici girişini ve motorunu 2.3.1 olarak dağıtır. Kanal kararlıdır. Güncelleyici için ayrı depo yayını veya canlı program kurulumu yapılmaz.

## Çalışma davranışı

Kullanıcı sorusundan önce soru kimliği, kaynak kapsamı ve bağlı ajan/görev kimlikleri kalıcı olarak kaydedilir. Koordinatör bağlı işi güvenli işlem sınırında durdurur; yeni bağlı dispatch, model sonucu, hesap ve rapor girişleri bekleme kaydı tarafından engellenir. Soru anında çalışan bağımsız işler devam eder.

Bekleme süreyle kalkmaz; sessizlik, önceden seçili seçenek ve “devam” eksik bilgi veya onay yerine geçmez. Kısmi/ilgisiz yanıt beklemeyi korur. Gerçek yeterli yanıt yalnız ilgili bağımlılığı bir kez kaldırır. Eksiksiz “bilinmiyor” yanıtı aynı kapsamda tekrar sorulmaz; ticari eksik ve QA kaydı açık kalır. Yeni koşu gerektiren yanıt bu engeli kaldırmaz. Yeniden başlatma yanıt üretmez. Soru gösterimi otomatik ön rapor başlatmaz.

Kapı plugin girişlerine bağlı işlerde uygulanır. Kayıtlı iş/ajan koordinasyonu gerekir; kayıtsız dış süreçleri işletim sistemi düzeyinde durduran bir hizmet değildir.

## Kaynak ve kanıt düzeltmeleri

Gerçek kullanıcı beyanına bağlı, hash doğrulanmış tekil teklif nüshası seçimi kaynak otoritesine uygulanır. Firma kimliği ve karşıt revizyon kontrolleri korunur. “KDV dahil değildir” ifadesi KDV hariç kanıtını destekler, KDV dahil kanıtını desteklemez. Kaynak, satınalma kanıtı, miktar/fiyat, bağımsız kontrol, gerçek model makbuzu ve karar kapıları gevşetilmez.

## Yayın doğrulaması

Tam SQLite ve native DuckDB testleri bu son sürümlü kaynak ağacının hash haritasına bağlı JSON/loglarla GitHub release yanında verilir. Test sayısı ve sonuçları bu dosyalardan okunur; önceki sürüm testleri güncel kabul sayılmaz. Paket ve Git ağacı bayt/sürüm eşliğiyle kontrol edilir. Güncelleyicinin offline Python sonuçları ayrı updater-python.json kaydıdır; atlanan kontroller PASS değildir.

Business kabulü mevcut pazarın GitHub main kaynaklı eşitlenmesi ve görünen plugin sürümünün kontrolüdür. Gerçek Business analizi/model makbuzu, tüm kurulum-kurtarma matrisi ve personel pilotu bu kaynak yayınıyla tamamlanmış sayılmaz. Teklif değerlendirmesindeki VERIFIED ve satınalma onayı kendi koşu kanıtlarına bağlı kalır.
