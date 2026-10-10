# Kaynaklar ve doğrulama sınırı

## Esas alınan kaynak

- 2.3.0: yayımlanmış 2.2.1 temeli `ec37678d8f031f0b253c327592dc4984b02aaf31`; pnpm native düzeltmesi ve teklif yönetimi kaldırma değişiklikleri. Güncel ölçümler: `RELEASE_TESTS_2.3.0.json`. Aşağıdaki 2.1/2.2 kaynak izi tarihsel kökendir.
- Kurulu `kilic-satinalma/guncelleyici` skill'i; 2.1.0 giriş ve betik davranışları.
- Bağlı GitHub üzerinden okunmuş `ozanbesinci/guncelleyici`, `skills/guncelleyici`.
  İnceleme sırasında görülen ağaç kimliği: `d1ec8ffdd38b087775cd1fddcd87324b21885553`.
  Bu kimlik kaynak izidir; teslim edilen değiştirilmiş ağacın hash'i değildir.
- Mevcut 12 paket setinin sürüm/hash kayıtları korunmuştur. Her wheel'in yeniden
  indirilerek çalıştırılması bu ortamda yapılmamıştır.

## Harici teknik belgeler — 3 Ekim 2026 kontrolü

- DuckDB PDF katalog: https://duckdb.org/community_extensions/extensions/pdf
- Community güvenlik / imza sınırı: https://duckdb.org/community_extensions/
- Kurulum dizini ve süreç yenileme: https://duckdb.org/docs/lts/extensions/installing_extensions
- Yerel extension dosyasından kurulum: https://duckdb.org/docs/lts/extensions/advanced_installation_methods
- İmza doğrulaması: https://duckdb.org/docs/lts/extensions/extension_distribution
- Claude Code MCP CLI: https://code.claude.com/docs/en/mcp

Bu bağlantılar kaynak davranışını açıklar; adayın Windows'ta test edildiğini göstermez.
Paket içine GitHub geçici erişim tokenı veya provider kimlik bilgisi konulmaz.
