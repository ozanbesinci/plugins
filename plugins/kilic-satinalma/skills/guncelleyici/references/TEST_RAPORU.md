# Güncelleyici2.2.1 — Windows kabul ve paket durumu

4 Ekim2026 normal test hesabında gerçek Windows PowerShell5.1 x64. Native kaynak294cae9f831bcdade53fc1f87c446fb73a794fcbee02faab70e1db1926172deb;2.2.1 yayın metadata/dokümantasyonudur, scripts/tests/config byte'ları aynıdır.

| Kontrol | Sonuç |
|---|---|
| Native parser ve fixture | PASS:42Windows+29scan |
| Guest Python suite |108PASS;2NOT_RUN (Linux vakası, symlink yetkisi) |
| Gerçek Python3.14.8/Node24.21.0/DuckDB1.5.6/PBI1.0.0 server | PASS |
| Test MCP config koruma | PASS; gerçek istemciler NOT_RUN |
| Sabit12 kütüphane / pip-check /13 import-işlev kontrolü | PASS |
| Excel COM | FAIL: Sandbox'ta Excel yok; kütüphane healthFAIL |
| pnpm12.9.1 | FAIL: launcher ek binary download ister; mevcut koruma engeller |
| Teklif scan / kurulum | BLOCKED: TLS zinciri; kurulum NOT_RUN |
| Yeni apply engeli ve journal koruma | PASS |
| Genel Windows kabulü / üretim onayı | BLOCKED / false |

Kapsam/kimlik:[WINDOWS_KABUL_2026-10-04.json](WINDOWS_KABUL_2026-10-04.json). Paket testleri native kabul yerine geçmez. Aşağıdaki Pro raporu/tests-python.json tarihsel kayıttır.

---

## Tarihsel Pro raporu

# Güncelleyici — Pro denetimi uygulama ve doğrulama raporu

**Tarih:** 3 Ekim 2026  
**Kaynak sürüm:** 2.2.0  
**Yayın kimliği:** 2026-10-03-v2.2.0-source-release  
**Durum:** Kaynak sürüm 2.2.0 yayınlandı; native Windows kabulü ve personel genel dağıtım onayı tamamlanmadı.

## Son kullanıcı yüzeyi

- Normal personel Güncelleyici'yi yalnız ChatGPT Desktop Work veya Codex sohbetinden kullanır.
- PowerShell komutları ajan-içi yerel yürütme adımlarıdır; kullanıcıdan terminal açması, komut kopyalaması veya script çalıştırması istenmez.
- Yerel yürütme yeteneği yoksa teknik iş kullanıcıya devredilmez; akış durur ve bu sınırlama açıklanır.
- Power BI ertelenmiş bağlama, istemciler kapatıldıktan sonra sohbetten yeniden istenir; `-BindOnly` adımını Work/Codex çalıştırır.
- Bu sözleşme için 3 yeni regresyon testi eklendi; toplam çevrimdışı test sonucu **110/110 PASS**.

## Sonuç

Pro ikinci denetiminde bulunan yüksek öncelikli güvenilirlik sorunları kaynak koduna uygulandı.
Ek olarak seçim değişikliği ile gerçek kurulum yetkisini kod seviyesinde ayırmak için `-ConfirmApply`
zorunlu hale getirildi; planın kullanıcıya açıklanması gereken yan etkileri makine-okunur `effects`
kayıtlarına bağlandı ve operasyonel referans/config dosyaları da plan parmak izine dahil edildi.

## Pro bulguları — uygulama durumu

| Bulgu | Durum | Uygulanan kontrol |
|---|---|---|
| Y1 — Power BI MCP ayar kaybı | **UYGULANDI** | Codex TOML / Claude Desktop JSON'da yalnız yönetilen `command` değişir; bilinmeyen alanlar korunur; byte yedeği, atomik yazım, readback doğrulaması ve geri dönüş vardır. Açık istemcide bağlama ertelenir. |
| Y2 — Fingerprint / TOCTOU | **UYGULANDI** | Hedef sürüm/hash/yorumlayıcı/yerel durum plan içinde sabitlenir. Uygulama kilidi alındıktan sonra yerel durum yeniden doğrulanır; `latest` yeniden çözülmez. Scripts/config/references/SKILL/BUILD parmak izine bağlıdır. |
| Y3 — Sürüm ile sağlık karışması | **UYGULANDI** | `NOT_RUN/PASS/WARNING/FAIL` sağlık makbuzları ayrı tutulur; `up_to_date` yalnız sürüm sonucu olarak ifade edilir; `verify` ve açık `repair` yolu vardır. |
| Y4 — Rollback / yanlış son durum | **UYGULANDI + artık risk açık** | Node/pnpm yedek + son-konum testi; PBI yeni doğrulanmış klasör; teklif transaction journal/rollback; pip/Python kısmi mutasyonunda otomatik başarı iddiası yok, `recovery_required` ile zincir durur. |
| Y5 — Ortak Python `--user` etkisi | **KONTROLLÜ ARTIK RİSK** | Bakım penceresi, aktif Python/Node iş yükü engeli, paket bazında upgrade/downgrade etkileri ve kısmi pip hatasında kurtarma kapısı eklendi. Otomatik venv geçişi yapılmadı; teklif skill yorumlayıcısıyla birlikte ayrı entegrasyon gerektirir. |
| Y6 — Seçim ile kurulum onayının karışması | **UYGULANDI** | `apply` artık `-ConfirmApply` olmadan kod seviyesinde reddedilir. Seçim düzenleme yanıtı kurulum yetkisi değildir. |
| Y7 — Çalıştırılmayan/bozuk kontrolün başarı sayılması | **UYGULANDI** | Boş kontrol `PASS` değildir; MCP `tools/list` eleman tipi/ad/inputSchema doğrulanır; sıfır olmayan alt süreç kodu `ENGEL` olur. |

## Orta öncelikli bulgular

- **O1 scan yan etkileri:** kalıcı kurulum/sağlık kaydı yazmayan `LocalOnly/YalnizBul` yolları; yalnız geçici plan/önbellek.
- **O2 eşzamanlılık:** kullanıcı profilindeki dosya guard'ı + run token + teklif özel kilit/journal.
- **O3 supply-chain:** Python PSF imzası+hash, Node OpenJS imzası+hash, pnpm SHA-512, PBI Microsoft EXE imzası, teklif ZIP+manifest. Güven zincirlerinin aynı olmadığı dokümante edildi.
- **O4 teklif doğrulama tekrarı:** orkestrasyon `teklif-guncelle.py prepare/update` yoluna bağlandı; ayrı PowerShell release validator kullanılmıyor.
- **O5 sonuç sözleşmesi:** JSON sonucu ve süreç kodu birlikte değerlendirilir; `error/stale/busy` üst girişte sıfır olmayan kod döndürür.
- **O6 timeout:** yalnız başlatılan alt süreç ağacı PID üzerinden `/T /F` sonlandırılır; rastgele kullanıcı süreçleri isimle kapatılmaz.
- **O7 sürüm yönetişimi:** upstream stable ile “şirketçe onaylı” ayrılır. Kurumsal approved-version kataloğu henüz yapılandırılmadı ve paket bunu varmış gibi göstermez.

## İlave kontroller

- Windows amd64 / 64-bit Windows PowerShell çalışma kapısı tüm ana girişlerde erken uygulanır.
- Python sabit paket setindeki gerçek düşürmeler planın `effects` alanında `paket / eski → hedef / downgrade` olarak görünür.
- Her non-empty apply için eski `program-guncelle` temizliğinin yan etkisi `global_effects` içinde önceden görünür.
- Nihai audit kaydı `confirmation=explicit`, seçili yan etkiler, global etkiler, sonuçlar, temizleme, son durum ve `recovery_required` bilgisini içerir.

## Çalıştırılan kontroller

| Kontrol | Sonuç |
|---|---:|
| Toplam çevrimdışı regresyon | **110/110 PASS** |
| Python fixture / davranış testleri | **83 PASS** |
| Genel kaynak sözleşmesi testleri | **10 PASS** |
| Pro Y1–Y7 + O1–O7 isimlendirilmiş kontrat testleri | **14 PASS** |
| Python sözdizimi | **15 dosya PASS** |
| Skill quick validator | **PASS** |

Makine-okunur kanıt: `references/tests-python.json`.

## Windows kabul durumu

- İlk gerçek Windows PowerShell 5.1 parser koşusu **FAIL** oldu: `core.ps1` satır 145 içindeki tipografik `’` karakteri PowerShell tarafından string sonlandırıcısı sayıldı.
- Kaynak güvenli ASCII metne çevrildi. Tüm `.ps1` dosyalarında tipografik tırnak/apostrof yasağı ve UTF-8 BOM kontrolü için iki yeni regresyon testi eklendi.
- Düzeltme ve Work/Codex sohbet-yüzeyi korumaları sonrası çevrimdışı regresyon **110/110 PASS**. Gerçek Windows `tests/test_windows.ps1` koşusu yeni paketle **yeniden çalıştırılmayı bekliyor**.

## NOT_RUN — üretim öncesi hâlâ zorunlu

- Düzeltilmiş paketle gerçek Windows PowerShell 5.1 parser + `tests/test_windows.ps1` orkestrasyon fixture'ının yeniden çalıştırılması
- Python / Node.js / pnpm gerçek kurulumları ve Authenticode zinciri
- Excel COM / pywin32 gerçek masaüstü testi
- Power BI native MCP + Codex/Claude istemci bağlantı kabulü
- DuckDB PDF native eklenti LOAD / Türkçe metin-tablo kabulü

Bu kontroller çalıştırılmadığı için `BUILD.json` içindeki `production_approved=false` korunur.

## Bilinçli kalan mimari kararlar

1. **Dedicated venv otomatik devreye alınmadı.** Güncelleyicinin tek başına venv'e geçmesi,
   `teklif-degerlendirme` koşularının hangi Python yorumlayıcısını kullandığıyla uyumsuzluk yaratabilir.
   Bu nedenle ortak ortam riski gizlenmedi; bakım ve kurtarma kontrolleriyle sınırlandı.
2. **Şirket onaylı sürüm kataloğu/PKI eklenmedi.** Upstream kararlı hedef işlem başına sabitlenir.
   Kurumsal onaylı sürüm politikası ayrı bir yönetişim katmanıdır.
3. **Native Windows kabulü olmadan genel dağıtım yapılmamalı.**
