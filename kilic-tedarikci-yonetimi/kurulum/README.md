# Teklif Python ortamı kurulumu

`Kur.cmd` dosyasını açın. Kurucu standart kullanıcı profilinde `%USERPROFILE%\KilicPython` altında ayrı bir ortam hazırlar. Bu yol uygulamalar arasında ortaktır; MSIX masaüstü uygulamaları LOCALAPPDATA yolunu kendi önbelleğine yönlendirebildiği için ortam oraya bağlanmaz. Uyumlu kullanıcı Python 3.14/64 bit varsa temel olarak kullanır; paketlerini değiştirmez. Yoksa resmî hash sabitli Python kurucusunu kullanıcıya özel, launcher/PATH/yönetici kurulumu olmadan çalıştırır. Kurumsal çalıştırma politikası engeli atlatılmaz.

23 doğrudan/dolaylı paket tam sürüm, SHA256 ve yalnız hazır Windows wheel dosyalarıyla kurulur. Sözleşme eklentisi ön koşul değildir. `runtime-profile.json` ve `requirements-win-cp314.lock` birlikte korunmalıdır. Yeni profil yayımlamak kurulum bakım işidir; eklenti analiz sırasında kurulum yapmaz.

Kurulum pip bağımlılık kontrolü, gerçek DuckDB ve Excel/Word/PDF okuma-yazma kontrollerinden sonra `teklif-runtime.json` kaydını yayımlar. Önceki kayıt başarısız kurulumda korunur. Bu smoke kontrolleri gerçek Excel formül hesabı veya Work bağlantı kabulü değildir. DuckDB PDF uzantısı isteğe bağlıdır; kurucu uzantı kurmaz.

Kur.cmd, Windows'un yerleşik curl/certutil araçlarıyla hash doğrulanmış Python'u hazırlar; ardından kurulum motorunu Python ile çalıştırır. PowerShell betik çalıştırma ilkesini değiştirmez. Varsayılan Restricted ayarında da PS1 dosyası çalıştırmaz.

Teknik çevrimdışı kabul için CMD penceresinde KILIC_BASE_PYTHON ve KILIC_WHEELHOUSE ortam değişkenlerini tanımlayıp Kur.cmd'yi açın. Kur.ps1 yalnız isteğe bağlı eski giriş uyumluluğudur.

Kurucu kullanıcı profilindeki KilicPython/teklif-python.exe başlatıcısını Python/pip'in standart Windows konsol giriş yöntemiyle hazırlar; distlib lisans metni yanında tutulur. Eklenti bu girişe kendi scripts/runtime_launcher.py yolunu ve komut argümanlarını verir. Seçici kayıt kimliğini ve paket profilini doğruladıktan sonra analizi kayıtlı sanal ortama aktarır. Analiz argümanları CMD üzerinden aktarılmaz; PowerShell'de dosya yolundaki & gibi karakterler komuta dönüşmez.

Son kullanıcıda varsayılan çevrimiçi kurulum için yalnız Kur.cmd gerekir. IT'siz kabul gerçek standart kullanıcı testiyle doğrulanır.

Python'un çalıştırıcı, standart kitaplık ve pip bileşenleri kurulur; geliştirme başlıkları, IDLE/Tcl-Tk ve çevrimdışı Python kılavuzu kurulmaz. C/C++ derleme yapılmaz; kilitli wheel dosyaları kullanılır.

Temiz Windows'ta PDF kütüphanesinin ihtiyaç duyduğu Microsoft C++ DLL'leri de hazırlanır. Kurucu sürüm14.44.35211.0 resmî Microsoft paketini sabit URL/SHA256 ile indirir; EXE veya MSI çalıştırmadan yalnız x64 çalışma DLL'lerini ve lisans metnini açar. Her DLL ayrıca hash ile doğrulanıp yalnız yeni sanal ortama yazılır. Sürece özel DLL dizini Python'un os.add_dll_directory API'siyle tanımlanır; sistem klasörleri, PATH ve temel Python değiştirilmez. Yeni ortamın canlı belge kontrolleri geçmeden kayıt yayımlanmaz.

Çevrimdışı teknik kabulde KILIC_NATIVE_RUNTIME_PACKAGE, aynı hash kilitli Microsoft paketinin yerel dosya yolunu gösterebilir. Yerel DLL seti ayrı kurucunun kilitli bakım kapsamındadır; eklenti analiz sırasında indirme veya güncelleme yapmaz.

## Tam otomatik yerel hesap motoru

`Kur.cmd` ayrıca LibreOffice 26.8.1.1 hesap motorunu hazırlar. Mevcut kayıtlı Python ortamına yalnız motor eklemek için `Kur-Hesap.cmd` kullanılır. Resmî paketin SHA-256 özeti ve açılan dosyaların tamamı sabittir. MSI veritabanı salt okunur açılır; dosyalar `%USERPROFILE%\KilicPython\calculation` altına çıkarılır. MSI kurulum işlemleri, yönetici izni, PATH, servis ve Office kayıt değişikliği yoktur. Ayrı hesap kaydı ancak gerçek formül hesabı geçince yayımlanır. Önceki kayıt başarısızlıkta korunur.

Bu motorun Microsoft Excel ile eşdeğerliği sürüm kabulünde ayrıca sınanır. Kurucu küçük hesap kontrolünü gerçek Work veya kapsamlı Excel karşılaştırması gibi sunmaz. Teknik çevrimdışı kabulde `KILIC_CALCULATION_PACKAGE` aynı hashli resmî MSI dosyasını gösterebilir. Dağıtım klasöründeki `kurulum/` ve `plugins/kilic-satinalma/` birlikte korunmalıdır.
