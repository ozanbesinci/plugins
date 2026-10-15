# Bileşen kimliği

Plugin, core, P6 sonuç şeması ve vendor ayrı sürümlenir. Plugin0.1.0 / core0.2.0 / P6p6-1.2 / vendor2.3.0 ilişkisi `component-identity.json` içindedir. Bu bir kararlı kabul kaydı değildir. CLI tool_version core sürümüdür; components alanı bileşenleri ve gerçek davranış kaynak digest'ini ayrı verir.

Kurulu pakette bağımsız commit attestasyonu yoksa source_commit null/UNVERIFIED'dır; dosya digest'i commit yerine kullanılmaz. Test runner kendi checkout commit'ini ve dirty kaynak snapshot'ını ayrıca kaydeder. Release son commit/paket digest bağı haricî attestasyonda kurulacaktır; kendi commit/hash'ini kendi içinde türeten döngü yoktur.

Reader profili kod/şema/pin/gerçek dependency/Python ABI ve patch sürümüne bağlıdır. EML'nin dolaylı worker/common bağımlılığı bütün setle kapsanır. Kaynak belge hash'i bu ürün build kimliğinden farklıdır. Aynı çalışan süreçte reader kod/şema değiştirilirse PAKET_DEGISTI olur; restart olmadan hot-reload geçerli kabul edilmez. Metadata veya parser değişimi eski audit kaydını silmez; yeni namespace gerekir.
