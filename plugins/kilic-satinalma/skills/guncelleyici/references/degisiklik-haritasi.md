# Değişiklik haritası ve açık sınırlar

## Uygulanan kaynak değişiklikleri

Bu paket 2.1.0 giriş davranışı, program kaynakları, 12 paket kilidi ve teklif arşivi
kuralları esas alınarak yayımlanmış **2.2.0 kaynak sürümüdür**. Native Windows kabulü
tamamlanmadığı için `production_approved=false` korunur. Çalışan kurulumun
birebir klonu veya yalnız metin düzeltmesi değildir: ortak `core.ps1` ve
`program-ortak.ps1` çıkarılmış, kurucu girişleri hash-bağlı hedef arayüzüne uyarlanmış,
bazı eski kod yolları değiştirilmiştir. Dolayısıyla yeni Windows regresyon testi şarttır.

| Denetim konusu | Kaynakta yapılan |
|---|---|
| Kullanıcı onayı | Seçim değişimi/uygulama ayrıldı; `-ConfirmApply` olmadan apply reddedilir; yan etkiler planın `effects` alanlarında görünür |
| TOCTOU | Hedefler taramada sabit; kilit altında yerel yeniden doğrulama; uygulamada rolling latest yok; operasyonel scripts/config/references/SKILL/BUILD parmak izine bağlı |
| MCP ayarı | JSON/TOML alan koruma, byte yedeği, doğrulama; açık istemcide erteleme; Claude Code için kendi CLI'sı |
| Sürüm/sağlık | Sürüm güncelliği ayrı; işlev makbuzu, pending, NOT_RUN; açık verify/repair |
| Geri dönüş | Node/pnpm son konum testi; PBI yeni klasör; teklif/PDF günlük ve yedek; belirsiz kısmi değişimde durma |
| Rapor | Session planı, seçilenler, eski skill temizliği, son gözlem, alt sonuçlar ve kurtarma gereği |
| PDF | İsteğe bağlı ayrı satır, motor/platform/hash eşleşmesi, imzasız mod yok |

## Bilinçli davranış farkları

Eski GUI kapatıldı; GUI testlerinin yerine `test_windows.ps1` geldi. Eski test
senaryoları yeni Python paket/ayar/işlem fixture'ları ve Windows orkestrasyon testinde
yeniden kapsanır; eski test dosyalarının hepsinin değişmeden korunduğu iddia edilmez.

Python kurulumunun winget alternatifi bu adayda kullanılmaz; doğrudan doğrulanan
python.org kurucusu seçilir. Bu, onaylanan kurucu hash'inden farklı winget artefaktı
ve otomatik sözleşme kabulünü önler. Özel pnpm/Corepack veya .cmd-only Claude Code
kurulumları otomatik yeniden yazılmaz; açık uyarı/erteleme verilir. İlk kurulumda
bağımlı bileşenler için ikinci tarama gerekebilir. Eski `on-kontrol.ps1` yerine
güvenlik ayarını değiştirmeyen, Excel'i başlatmayan dar ön kontrol vardır; ayrıntılı
çalışma testi `verify` altında açık istekle yapılır.

## Kalan / ayrıca doğrulanacak işler

- Gerçek Windows PowerShell 5.1, native kurucular, Authenticode, Excel COM ve native
  DuckDB PDF testi bu hazırlama ortamında çalıştırılmadı.
- Python venv'e otomatik taşınmadı. Ortak paket ortamı için bakım kısıtı var; dış
  süreçlerin sonradan başlamasını OS düzeyinde engellemez. Tüketici skill'le birlikte
  yorumlayıcı/venv geçişi ayrı entegrasyon ve kabul gerektirir.
- Şirket onaylı sürüm kataloğu, merkezi dağıtım sunucusu, bağımsız paket imzası/PKI,
  otomatik yedek saklama politikası eklenmedi. Upstream kararlı sürüm işlem başına
  sabitlenir; kurumsal onaylı olduğu ileri sürülmez.
- PDF'nin Türkçe OCR / gerçek teklif tablosu doğruluğu ölçülmedi. Smoke testi bunu
  yerine geçmez. Community eklentisi OS sandbox içinde çalıştırılmıyor.
- Kurulu ChatGPT eklentisi, yerel personel bilgisayarları ve GitHub depoları bu
  dosya teslimiyle güncellenmiş değildir; paket yalnız geliştirme çıktısıdır.
