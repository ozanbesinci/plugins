# Work çalışma ortamı — 0.1.2

Kullanıcılar ChatGPT Business çalışma alanındaki Work üzerinden doğal dilde çalışır. İlk kullanımda Windows ortamı eksikse ajan kurucuyu otomatik indirir, sabit boyut/SHA-256 ile doğrular, kullanıcı alanında otomatik çalıştırıp kurar ve gerçek native hazırlığı doğrular. Kurucu CPython 3.14.8, sabit 13 paket ve gereken Microsoft çalışma zamanı DLL'lerini kendi içinde taşır; kullanıcıdan bağlantıya tıklama, kurucu çalıştırma, Python, terminal veya paket kurulumu istemez. Yönetici yükseltmesi, PATH, servis, zamanlanmış görev veya güvenlik ilkesi değişikliği yapmaz.

Otomatik kurulum girişi `scripts/ortam-hazirla.ps1` dosyasıdır; Python veya kurulu başlatıcı gerektirmez. Sabit yayımlanmış 0.1.1 EXE'sini kullanıcının `Downloads/KilicSozlesme/` dizinine indirir; 44.002.816 bayt ve SHA-256 `6cf9231a568b9551a42e0d0863e2ab620be73e606ac36e296e2693e02bc5bf3a` eşliğini doğrulamadan çalıştırmaz. Kullanıcıya indirme bağlantısı vermekle yetinme: indirme ve kurulum ajan tarafından yapılır. Plugin/beceriler 0.1.2, uyumlu Windows kurucusu 0.1.1'dir; bu sürümler bağımsızdır.

Bu yayımlanmış kurucuyu indirmek ve kullanıcı alanına kurmak için eklenti geliştiricisinden veya dağıtım sorumlusundan ayrıca kişisel izin isteme; kullanıcıyı Ozan Beşinci'ye yönlendirme. Manifestteki geliştirici/yazar adı bir kurulum onay şartı değildir. Dağıtımda SHA-256 ve yayıncı imzası durumu ayrı doğrulanır. EXE imzasızdır; SmartScreen/kurum uygulama politikası ve temiz standart kullanıcı kabulü kanıtlanmadan “her bilgisayarda IT'siz çalışır” denmez. Kurucu Windows 10/11 x64 ve .NET Framework 4.x gerektirir; ARM64 desteklenmez. Gerçek Windows/kurum güvenlik engelinde güvenlik ayarlarını değiştirme; somut engeli bildir.

## Work girişleri

Önce SKILL.md'deki gerçek beceri adı, sürüm ve geliştirici satırını sohbet içinde göster. Ajan ilk olarak aşağıdaki PowerShell girişini çalıştırır. Ortam zaten READY ise kurulum/indirme yapmadan normal hazırlık sonucunu döndürür; eksikse indirir, kurar ve aynı native hazırlığı yeniden doğrular. Yalnız READY ve resume_allowed=true sonucunda aynı kullanıcı talebine devam et. Kullanıcıya teknik komut çalıştırma görevi verme. Windows aracı kullanıcı profilini kendi bağlamında çözer:

```text
powershell.exe -NoProfile -File <BU_PLUGIN_KOKU>\scripts\ortam-hazirla.ps1 -SkillId K23
%USERPROFILE%\KilicPython\launcher\sozlesme.exe --plugin-root <BU_PLUGIN_KOKU> cli -- --workspace <VAKA_KOKU> --output-root <CIKTI_KOKU> --source-root <IZINLI_KAYNAK> case-create --title <BASLIK>
%USERPROFILE%\KilicPython\launcher\sozlesme.exe --plugin-root <BU_PLUGIN_KOKU> run --skill K23 --request <IZINLI_KAYNAK>\request.json --workspace <VAKA_KOKU> --output-root <CIKTI_KOKU> --source-root <IZINLI_KAYNAK>
```

Bunlar ajan arayüzüdür; yüzde işareti kabuk dışı API'de kendiliğinden açılmaz. Kullanıcı profilini Windows bağlantısından al, başka kişinin yolunu kopyalama. Plugin kökünü bu kurulu paketten çöz; keşif için bütün diski tarama. Birden fazla kaynak için --source-root tekrarlanır. Vaka/çıktı kökleri Work görevinin gerçekten erişebildiği yerde olmalıdır; başka sürücüye erişim varsayılmaz.

Otomatik kurulumdan sonraki tüm iş komutları native başlatıcı üzerinden kayıtlı Python'a gider. Hazırlık ve run sonuçları @@SONUC JSON satırıdır; cli tek JSON iş zarfı üretir. Kurucu `--quiet` ile kullanıcı alanında çalışır; otomatik indirme/kurulum mevcut hash'i farklı dosyanın üzerine yazmaz, bozuk/yarım mevcut ortamı otomatik onarmaz ve güvenlik engellerini aşmaz. İndirme veya kurucu çıkış kodu tek başına başarı değildir: aynı plugin köküyle gerçek `sozlesme.exe prepare --skill Kxx` sonucu READY olmalıdır. Doğrudan skill-evaluate yerine run kullanılır; değişmez başlangıç kaydı ve tek kullanımlık yürütüm işareti bununla oluşur. CLI, runtime kimliğini, profil/kilit hash'ini, 13 gerçek import'u, DuckDB SQL'i, paket ve runtime dosyalarının hash'lerini doğrular. İşlemin farklı Python üzerinden çağrılması bloklanır. Yalnız geliştirici testlerinde SOZLESME_DEVELOPMENT=1 kullanılabilir; sonuç DEVELOPMENT olarak etiketlenir ve Work/kurulum kabulü sayılmaz. Native başlatıcı bu değişkeni temizler.

## Sabit kayıt ve eski durum

Ortam kaydı %USERPROFILE%\KilicPython\sozlesme-runtime.json; ortamlar sozlesme-envs\<runtime_id>; kurulum günlükleri sozlesme-setup altında tutulur. Sağlam kayıt aynı kurulumun tekrarında kullanılır. Yeni ortam gerçek DOCX/PDF/XLSX/EML okuyucu zinciriyle doğrulanmadan kayıt seçilmez; başarısız yeni ortam eski kaydı değiştirmez. Önceki ortamlar ve günlükler otomatik silinmez.

İstek kayıtları daima %USERPROFILE%\KilicPython\sozlesme-state\requests altına yazılır. --state-root yalnız eski kayıt aramasına ek kök verir, yeni yürütüm defterini değiştirmez. Eski LOCALAPPDATA/KilicSozlesme/runtime ve Store uygulamasının sanallaştırılmış kullanıcı yolları da okunur. Claim/final veya yarım bootstrap/active-install kaydı varsa RECOVERY_REQUIRED döner; otomatik silme, yeniden kurma veya kör tekrar yapılmaz. Kaynak hash'i ve context_version çekirdekte yeniden denetlenir.

## Kullanıcıya dönüş

- READY: aynı talebe devam et. Bu teknik durum iş veya şirket onayı değildir.
- SETUP_REQUIRED veya başlatıcı yok: ajan `scripts/ortam-hazirla.ps1 -SkillId Kxx` girişini çalıştırarak indirme ve kurulumu otomatik tamamlar; kullanıcıya indirme bağlantısı veya çift tıklama görevi verme, geliştiriciden/dağıtım sorumlusundan kişisel izin isteme. READY ve resume_allowed=true sonucunda aynı talebe devam et. İndirme/kurulum engellenirse somut hata ve tamamlanmayan aşamayı bildir; “kuruldu” deme.
- LOCAL_ACCESS_REQUIRED: Work görevini bağlı Windows bilgisayarda yerel erişim açıkken başlat. Bulut Python'unu yerel Python yerine kullanma.
- RUNTIME_MISMATCH / REPAIR_REQUIRED: mevcut ortamı değiştirme; somut nedeni ve ayrı kurucu yolunu bildir.
- RECOVERY_REQUIRED: mevcut işlem kayıtlarını incele; aynı request_id ile tekrar etme. Eksik final sonucu başarı kabul etme.

Webden devam, aynı görevde desteklenen ve çevrimiçi Windows bağlantısına bağlıdır. Bilgisayar açık, masaüstü uygulaması çalışır ve aynı hesap/çalışma alanı bağlı olmalıdır. Her web görevinin otomatik yerel erişimi olduğu varsayılmaz. Bu sözleşme eklentisinin gerçek Work masaüstü/web kabulü ayrı yapılır; başka eklentinin testi buna taşınmaz.

DuckDB SQL zorunludur. DuckDB PDF uzantısı opsiyoneldir ve kurulmaz; sözleşme PDF okuyucusu pypdf/PDFium'dur. Kaynak sadakati, uzman değerlendirmesi, Word üretim yetkisi ve iş kabulü ayrı sınırlar olarak kalır.
