# Host giriş sözleşmesi

Work girişi kullanıcı profilindeki KilicPython/launcher/sozlesme.exe'dir; prepare, run ve cli kipleri [runtime-integration.md](runtime-integration.md) içindedir. Bütün çekirdek komutları aynı kayıtlı Python'a bağlanır. Kurulum ve güncelleme iş komutunun parçası değildir.

Başlatıcı, sabit runtime kaydı/kimliği ve dosya hash'lerini kontrol eder. scripts/contract_cli.py çekirdek JSON zarfını normalleştirir; doğrudan wrapper ve modül çağrısında da kayıtlı ortam kapısı vardır. Eksik site bağımlılığı CONFIG_REQUIRED, argüman hatası CLI_ARGUMENT_ERROR, eksik kayıt SETUP_REQUIRED olur. Native giriş hataları @@SONUC ile açık teknik engel döndürür. Kurulmamış ortamda vaka oluşturulmaz.

skill-evaluate yalnız run girişinin aynı request hash'i/runtime/vaka/kaynak kökleriyle bağlı, tek kullanımlık kaydıyla yürütülür. cli kipinden bu komut verilirse REQUEST_ENTRY_REQUIRED olur. Doğrudan çekirdek çağrısı kayıtsız yürütüm üretemez. SOZLESME_DEVELOPMENT=1 yalnız test/geliştirme içindir; sonuç components.execution_profile=DEVELOPMENT taşır. Native giriş bu değişkeni temizler.

Normal çekirdek sonucu aynı operation_id/components ile aktarılır; technical_status/business_status/business_acceptance ayrı alanlardır. P6 exit0+TEKNIK_ENGEL veya BILGI_GEREKLI iş tamamlandı sayılmaz; output_ids boşsa dosya teslim iddiası yoktur. --help iş makbuzu değildir. Stdlib zarfın stdout sınırı64MiB, başlatıcı sonucunun sınırı4MiB'dir; bunlar host token ölçümü değildir.

Gerçek sözleşme eklentisinin Work masaüstü/web bağlantısı, standart kullanıcı kurulumu ve bağımsız iş kabulü ayrı kanıt gerektirir. K29 yalnız sohbet taslağıdır; normal üretim Word kapısı CONFIG_REQUIRED olarak kalır.
