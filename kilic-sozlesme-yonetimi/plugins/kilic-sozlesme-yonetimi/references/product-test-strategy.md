# Ürün test ve kabul sözleşmesi

0.1.1: geliştirici koşucusu alt test sürecini SOZLESME_DEVELOPMENT=1 ile açıkça etiketler. NativeStartupTests ise bu işareti kaldırır, SOZLESME_TEST_INSTALLER ile verilen gerçek EXE'yi ayrı USERPROFILE klasörüne kurar ve REGISTERED yolunu sınar. Kurucu yolu verilmezse native kabul NOT_RUN olur; tam PASS sayılmaz. Kurucunun asInvoker olması temiz standart kullanıcı/SmartScreen veya gerçek Work kabulünün yerine geçmez. CI Python patch sürümü3.14.8'e sabittir; eski zorunlu DuckDB PDF kurulumu kaldırılmıştır.

`scripts/run_product_tests.py` gerçek Windows Store/DuckDB/kilit sağlayıcısını izole sentetik staging kopyasında çalıştırır. Kaynak ve staging hash'leri, test manifesti, fixture baytları, komut, ortam, native bağlantı testi ve tekil sonuçlar makbuzdadır. Çıktılar kurulu paketin dışında benzersiz koşu klasörüne yazılır. Her test başlama/terminal olayı ayrıca append-only JSONL olarak tutulur.

`--suite a0` P6, K29, hesap, K26 ve JSON hata testlerini; `--suite core` kalan sentetik Store/okuyucu/bağlam/izin/Word yapı/iş ve runtime policy testlerini çalıştırır. `--suite full` iki grubun birleşimidir. Zorunlu skip, FAIL, ERROR, kaynak değişimi veya süreç kesintisi başarı değildir. Süre aşımında durum NOT_RUN/TEST_TIME_LIMIT ve tam kabul NOT_GRANTED'dır. Koşu yeniden başlatılırsa önceki log/makbuz korunur.

Kaynak kapsamındaki PASS yalnız seçilen sentetik test grubuna aittir. Native Word görünümü, kurumsal kimlik, gerçek host, bağımsız uzman ve ekibin gerçek iş denemesi ayrı kabul hücreleridir. Bunların NOT_RUN olması, teknik PASS ile kararlı kabul oluşturmaz. Üretim Word ve K29 dış eylemleri kapalı kalır.

Windows CPython3.14 x64 binary seti `requirements-win-cp314.lock` içinde tüm bağımlılıklarla hash bağlıdır. Mevcut13 pin değiştirilmemiştir. `references/windows-wheel-manifest.json` dosyaları resmi PyPI JSON metadata SHA-256 değerleriyle eşler; bu lisans/kurumsal platform onayı değildir. CI yalnız bu seti kendi geçici runner ortamına kurar; kullanıcının ortak ortamını değiştirmez.

CI manifestteki14 Windows test grubunu ayrı job olarak çalıştırır; örtüşen testler kabul sayısına iki kez eklenmez; kardeş tedarikçi workflow'u ürün kabulüne eklenmez. GitHub action kimlikleri resmi `actions/checkout` ve `actions/setup-python` v7, `actions/upload-artifact` v4 tag'larının 14.10.2026'da çözülen sabit commit'leridir. [Checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), [upload-artifact](https://github.com/actions/upload-artifact). GitHub CI henüz çalıştırılmamışsa yerel kaynakta NOT_RUN olarak raporlanır.

Staging Windows sistem Temp alanında, küçük kalıcı makbuz/loglar output-root altındadır. Drive mirror yazarları test-temizliğiyle yarışmasın diye DB deneme alanı vault dışında tutulur. Staging yolu ve byte/digest eşliği makbuzda kalır. Native CAS/replay testlerinin60s beklemesi ürünün5s busy ret politikasını veya müşteri gecikmesi kabulünü değiştirmez.

Paket Git dışında da seçilmiş sentetik grupları çalıştırabilir. Kaynak paketine ait `plugin.json` dosyası en yakın deponun indeksinde kayıtlı değilse üst dizindeki başka deponun HEAD'i pakete bağlanmaz. Git yoksa commit ve dirty alanları null, Git ölçümü NOT_RUN ve attestation UNVERIFIED'dır. Git komutu hatası ayrıca ERROR kaydedilir; testler ve kaynak hash'leri kendi gerçek sonuçlarıyla kalır. Görülen HEAD yalnız temel commit bağlamıdır; test edilen değişmiş baytların commit onayı değildir. Tarihsel migration testlerinin ihtiyaç duyduğu değişmez denetim kaynağı bulunamazsa ilgili koşu NOT_RUN/AUDIT_REFERENCE_UNAVAILABLE olarak kapanır.

Alt test sürecinin makbuzu CHILD_TERMINAL_ONLY aşamasındadır. Ana koşucu kaynak eşliği, komut ve ortam bilgilerini tamamladığında receipt_phase=FINAL yazar. Tek başına alt süreç PASS'ı tamamlanmış koşu veya yayın kabulü değildir; yayın kapısı BLOCKED kalır.


## Windows ani süreç kaybı fixture sözleşmesi

Sentetik hard-crash noktaları yalnız tests/process_fixtures.py içindeki abrupt_exit yordamını kullanır. Windows'ta GetCurrentProcess pseudo-handle'ı ile TerminateProcess çağrılır; başka PID/handle hedefi yoktur. Diğer platformlarda os._exit korunur. Beklenen9/17/19/27/29/31/37/91çıkış kodları değiştirilmez, herhangi bir native hata kodu başarı sayılmaz. Guard/recovery/ledger testlerinin gerçek süreç ölümü, izin tüketimi, tek etki ve no-replay şartları aynı kalır.

Windows3.14.8/DuckDB1.5.6 ortamında bağlantıyı açıp kapattıktan sonra CRT os._exit(19), ürün kodu yüklenmeyen küçük deneyde0xC0000005 verdi. Bu nedenle CRT teardown, bu testin amaçladığı kontrol edilebilir ani süreç kaybı için kullanılmaz. Bu gözlem DLL içindeki kesin hata mekanizmasını veya normal ürün kapanışında hata olduğunu kanıtlamaz. Önceki FAIL ve ham iz korunur. Yeni gerçek alt süreç regresyonu fsync edilmiş başlangıç kanıtının kalmasını, finally/atexit'in çalışmamasını ve bütün planlı çıkış kodlarını kontrol eder.

[Windows süreç sonlandırma sözleşmesi](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess), [ExitProcess DLL kapanış davranışı](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-exitprocess), [Python3.14 hata izi](https://docs.python.org/3.14/library/faulthandler.html). Bu test yordamı üretim koduna eklenmez; Word/K29 kapıları değişmez.

0.1.2: `test_automatic_setup` indirme hatasını, yanlış indirme/önbellek hashini, yarım eski kurulumun korunmasını ve boş kullanıcı profilinde yayımlanmış gerçek kurucunun otomatik çalıştırılıp native READY ile doğrulanmasını sınar. Native testte ağ taşıması sabit yayımlanmış EXE kopyasıyla ikame edilir; gerçek kurucu/ortam/başlatıcı kullanılır. Bu, çevrimiçi indirme veya Business host kabulü değildir; bunlar ayrıca ölçülür.
