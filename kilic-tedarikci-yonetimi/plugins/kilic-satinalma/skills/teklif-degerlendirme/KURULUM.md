# Kurulum ve çalışma ortamı — 5.2 geliştirme adayı

Python ve yerel hesap motorunun kurulumu eklentiden ayrıdır. Kullanıcı dağıtım paketindeki `kurulum/Kur.cmd` dosyasını bir defa açar. Kurucu Windows 64 bit / Python 3.14 ortamını, tam sürüm ve SHA256 ile kilitli paketleri kullanıcı profilindeki `%USERPROFILE%\KilicPython` altında hazırlar. Sistem PATH'i ve diğer Python ortamları değiştirilmez. Yönetici yetkisi istenmez; kurumsal çalıştırma ilkeleri engellenirse bu ilkeler atlatılmaz. Ayrıntı: [ayrı kurucu](../../../../kurulum/README.md).

Eklentide Güncelleyici yoktur. Analiz sırasında paket, Python, Office veya uzantı kurulmaz; başka bir beceriye onarım devredilmez. Eklenti hazır ortamı bulur ve doğrular. Kurucunun belge okuma/yazma kontrolleri, Microsoft Excel'in formülleri hesapladığını veya Work bağlantısının çalıştığını kanıtlamaz.

## Kayıtlı ortamı doğrulama

`<aktif-paket>`, çalıştırılan eklentinin köküdür. Genel `python`, PATH'teki bir Python veya en yeni görünen ortam seçilmez. Bütün analiz ve devam komutları aynı girişten çalışır:

```powershell
& "$env:USERPROFILE\KilicPython\teklif-python.exe" "<aktif-paket>/scripts/runtime_launcher.py" environment_check --strict --output "<yeni-kosu>/environment.json"
```

Başlatıcı bilgisayar/kullanıcı ve ortam kimliğini, Python yolunu ve tam paket kilidini doğrular. `READY` olmadan analiz başlamaz. `BLOCKED_ENVIRONMENT` eksik bileşen ve nedenleriyle bildirilir; eklenti kurulum yapmaz. Ortam hazırlandıktan sonra kontrol yeniden çalıştırılır.

DuckDB ana veritabanı zorunludur. İkincil DuckDB `pdf` okuyucusu isteğe bağlıdır; yokluğu uyarıdır. Birincil PDF okuma ve rapor bağımlılıkları ayrı kontrol edilir. Özel kabul senaryosu bu ikinci okuyucuyu gerektiriyorsa `environment_check --strict --require-pdf-extension` kullanılır. SQLite yalnız test ortamıdır; üretim yedeği değildir.

## Analizi başlatma ve sürdürme

```powershell
& "$env:USERPROFILE\KilicPython\teklif-python.exe" "<aktif-paket>/scripts/runtime_launcher.py" workflow prepare --source "<kaynak>" --run "<yeni-bos-kosu>" --profile standart
& "$env:USERPROFILE\KilicPython\teklif-python.exe" "<aktif-paket>/scripts/runtime_launcher.py" workflow next --run "<kosu>"
& "$env:USERPROFILE\KilicPython\teklif-python.exe" "<aktif-paket>/scripts/runtime_launcher.py" workflow status --run "<kosu>"
```

Kaynak salt okunurdur. Var olan veya kapanmış koşuya `prepare` uygulanmaz. Devamda aynı ortam ve koşu kimliği korunur. `NEEDS_USER_INPUT` dönerse yalnız ilgili iş belirsizliği sorulur; yanıt olmadan bağlı hesap ve karar ilerletilmez. `NEEDS_LLM` dönerse yalnız listelenen görev bağlamı ve şeması kullanılır.

Model görevini `record_results` ile kaydederken host gerçek model/efor/token veriyorsa bunlar aynen kullanılır. ChatGPT Work bu bilgiyi sunmuyorsa şu seçeneklerle açık eksiklik kaydı tutulur:

```text
--telemetry-status host_unavailable --telemetry-reason "ChatGPT Work görev bazlı kullanım bilgisini sunmuyor"
```

Bilinmeyen model, efor veya token uydurulmaz. Bilinen tüketim alt toplamı genel toplam değildir; bilinmeyen tüketim sıfır sayılmaz ve bütçe tavanının doğrulandığı söylenmez. Görev şeması, kaynak, bağımsız hesap, görev deneme sınırı ve ilgili QA kontrolleri uygulanmaya devam eder.

## Work masaüstü ve web

Aynı uygun Work görevinin webden devamı için yerel bilgisayar erişimi etkin ve bilgisayar bağlı olmalıdır. Webde açılan her yeni görevin yerel araçları görebildiği varsayılmaz. Yerel bağlantı yoksa bulut Python'una geçilmez. Python kurucusu, Work'ün yerel erişim veya Office uygulama kontrolünü kurmaz.

Tam otomatik formül hesabı ayrı kurulan LibreOffice motoruyla yapılır. Yeni kullanıcı `Kur.cmd`, mevcut kayıtlı Python kullanıcısı `Kur-Hesap.cmd` dosyasını bir defa açar. Her analizde kullanıcı işlemi gerekmez. Motor resmî, sabit hashli MSI paketinden yalnız kullanıcı klasörüne dosya açılarak hazırlanır; MSI kurulumu, sistem PATH'i, servis veya Office kaydı yapılmaz. Eklenti motor kaydını ve dosya bütünlüğünü doğrular; her hesap için ayrı profil ve geçici kopya kullanır.

Hesaplanan kopyada formüller ve sabitler doğrulanır; yalnız hücre sonuçları özgün Excel dosyasına aktarılır. Başarı `LOCAL_RECALCULATED`, başarısızlık `PENDING_LOCAL_RECALC` olarak açıklanır. LibreOffice hesabı Microsoft Excel çalıştırılmış gibi gösterilmez. Microsoft Excel ile sürüme özgü karşılaştırmalı kabul ayrı tutulur; yalnız eski motorla alınan sonuç yeni sürüme taşınmaz. Ortak çalıştırıcı, ACL, DCOM veya Office kimlik ayarları değiştirilmez.

## Rapor ve kabul

Excel kaynak verisini ve izinli kullanıcı senaryo formüllerini taşır; bu sürümde nihai dosya formülsüz değildir. Formüllerin konumu ve ifadesi, değişmez kaynak hücreleri ve izinli girdiler sözleşmeyle denetlenir. Formül yazılması veya dosyanın kaydedilmesi yeniden hesaplama kanıtı değildir.

Excel/PDF çifti aynı snapshot ve rapor revizyonuna bağlı üretilir. İki dosya ve bütünlük kontrolleri geçmeden teslim `READY` olmaz; teslim `READY` olması analiz veya senaryoların doğrulandığı anlamına gelmez. Hesaplanmamış senaryolar doğrulanmış sonuç diye sunulmaz. Resmî görsel QA `yuksek_guvence` profiline bağlıdır; hızlı profildeki `NOT_APPLICABLE` bütün profillerin görsel kabulü sayılmaz.

Gerçek Windows/Work kabulü, desteklenen hesap motoru, bağlantı dönüşü ve rapor kontrolleri ayrıca kanıtlanır. Teknik veya sentetik test sonucu gerçek tedarikçi belgesinin doğruluğu ya da satınalma onayı değildir. Güncel durum: [5.2 kabul kaydı](references/RELEASE_ACCEPTANCE_5.2.0.md). Bu geliştirme adayı kararlı yayın ilanı değildir.
