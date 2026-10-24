# Bileşen kimliği

Plugin ve 30 beceri 0.1.2, çekirdek 0.2.1, P6 sonuç p6-1.2 olarak sürümlenir. component-identity.json v2, runtime_profile=sozlesme-win-cp314-embedded-v1 taşır. Eski vendor sürümü artık kimliğin parçası değildir. CLI tool_version çekirdek sürümüdür; components gerçek davranış kaynak digest'ini ve REGISTERED/DEVELOPMENT yürütüm profilini ayrı verir. Bunlar kararlı kabul kaydı değildir.

Kurulu pakette bağımsız commit attestasyonu yoksa source_commit null/UNVERIFIED'dır. Test koşucusu checkout commit'ini ve dirty kaynak snapshot'ını ayrıca kaydeder. Dışarıdaki BUILD.json, installer SHA-256 ile paket manifest SHA-256'sını bağlar; yayıncı imzası ayrıca gerekir. İç manifest kendi başına yayıncı kimlik doğrulaması değildir.

Reader profili kod/şema/pin/gerçek dependency/Python ABI ve patch sürümüne bağlıdır. EML'nin dolaylı worker/common bağımlılığı bütün setle kapsanır. Kaynak belge hash'i ürün build kimliğinden farklıdır. Aynı süreçte reader kod/şema değişirse PAKET_DEGISTI olur. Metadata veya parser değişimi eski audit kaydını silmez; context-rebind yalnız aynı kaynak ve birebir aynı metni taşıyan düğümleri yeni okumaya bağlar.
