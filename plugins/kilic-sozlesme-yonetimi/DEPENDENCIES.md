---
title: Sözleşme Yönetimi bağımlılık incelemesi
created: 2026-10-04
modified: 2026-10-05
type: development
status: 🟡 devam ediyor
tags: [is, sozlesme, bagimlilik]
tazele: 2026-11-04
---

# Bağımlılıklar

Kurulum yapılmadı. P0 mevcut ortamı ölçtü; çekirdek sürümleri `requirements-core.txt`, P2 okuyucu sürümleri `requirements-readers.txt` içinde sabitlendi. Tam binary dağıtım/SBOM/NOTICE kabulü henüz yok; aşağıdaki lisanslar kurulu paket metadata ve lisans dosyası envanterine dayanır.

| Bileşen | Ölçülen sürüm | Statü / lisans |
|---|---|---|
| Python x64 | 3.14.8 | Mevcut runtime; PSF. Python kurucusu paketlenmedi. |
| DuckDB | 1.5.6 | Çekirdek; MIT classifier ve LICENSE hash'i ölçüldü. |
| jsonschema | 4.26.0 | Çekirdek; MIT; 2020-12 + UUID/tarih format kontrolü gerçek testli. |
| attrs | 26.1.0 | jsonschema bağımlılığı; MIT. |
| jsonschema-specifications | 2025.9.1 | MIT. |
| referencing | 0.37.0 | MIT. |
| rpds-py | 2026.5.1 | MIT. |
| typing-extensions | 4.16.0 | PSF-2.0. |
| unittest / msvcrt | Python stdlib | Test düzeneği ve Windows OS kilidi; yeni paket yok. |
| pypdf | 6.13.2 | P2 PDF metin/envanter; BSD-3-Clause. Okuma sadakati PARTIAL. |
| pypdfium2 | 5.10.1 | P2 render ve aynı text layer ikinci okuma PASS; BSD/Apache ve PDFium alt lisans/NOTICE incelemesi dağıtımdan önce gerekir. |
| pdfplumber | 0.11.10 | Mevcut aday; P1 bağımlılığı değil, belge doğruluğu testi NOT_RUN. |
| openpyxl | 3.1.5 | P2 sheet çapraz envanteri; MIT. Formül hesap motoru değildir. |
| et_xmlfile | 2.0.0 | openpyxl bağımlılığı; MIT; sürümü sabit. |
| Pillow | 12.2.0 | PNG render desteği; MIT-CMU metadata'sı paket raporunda; yeniden dağıtım incelemesi ayrı. |
| python-docx | 1.2.0 | Mevcut aday; MIT; revizyon içi okuma için tek kaynak olamaz. |
| lxml | 6.1.3 | P2 ana OOXML okuyucusu; BSD-3-Clause. DTD/entity, ağ ve büyük XML reddi gerçek testli. |
| pywin32 | 312 | Word yetenek ve P5 native AI accept/reject probe'unda kullanıldı; PSF metadata. |
| Microsoft Word | 16.0.20430.20140 | Kurulu ticari uygulama; kurucu/lisans dağıtılmadı. Sentetik create/render ve P5 native revizyon accept/reject, yükseltilmiş yetkide PASS. |
| pytest | Yüklü değil | Gerekmiyor; stdlib test düzeneği kullanıldı. |
| DuckDB pdf extension | Ürün yolunda kapalı | Kurulu ortam envanteri ayrı; LOAD/INSTALL veya paket içine kopyalama yok. GPL/Türkçe OCR/Windows kabul kapısı açık. |

Çekirdek bağımlılık graph'ı ve lisans metadata'sı `reports/package-check.json`; kurulu lisans dosyalarının hash'leri `reports/p0-environment.json` içinde. `jsonschema[format]` gibi opsiyonel extras alınmadı. Kod üçüncü taraf repodan kopyalanmadı; yalnız belgelenmiş mimari ve mevcut paket API'leri kullanıldı.

Sentetik Word fixture'ı documents skill'in workspace dependency loader'ıyla bulunan bundled Python'da üretildi. Bu runtime'da pywin32 metadata'sı bulunmadı; Word COM karşılaştırması mevcut ölçülmüş Python/pywin32 ile ayrı izin yükseltilmiş probe olarak yürütüldü. Yeni runtime/paket kurulmadı. Ürün hostunda Word izin yolu hâlâ NOT_RUN.

P2 kontrol kaydı yeni bağımlılık eklemedi; hedef PDF PNG için mevcut sabit PDFium/Pillow kullanılır. DuckDB TIMESTAMPTZ'nin Python nesnesi olarak alınması eksik pytz hatası verdi; UTC VARCHAR dönüşümüyle kayıt zamanı karşılaştırıldı, pytz kurulmadı. Sonraki 102 test PASS. Render profilinde PDFium/Pillow sürümü, okuma profilinde ilgili parser sürümleri bulunur; sürüm farkı geçmiş kontrolü NEEDS_REVIEW yapar.

P3 bağlam da yeni paket, embedding servisi, model API'si veya tokenizer eklemedi. Mevcut Python/JSON/jsonschema ve aynı kilitli DuckDB erişimi kullanılır. Bütçe gerçek context UTF-8 baytlarını sayar; host/model token ölçümü değildir. Güncel 140 sentetik test ve 70 metadata kontrolü PASS; pin dosyaları değişmedi.

P4 izin kaydı için Python stdlib hmac/hashlib ve mevcut jsonschema kullanılır; paket/kurulum, kimlik servisi, gerçek anahtar veya gönderim bağlantısı eklenmedi. Test yayını aynı NTFS alanında os.link ile mevcut hedefi değiştirmeden yapılır. Test anahtarı fixture verisidir; üretim anahtar yönetimi değildir. P4 güncel sonuçları [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/TEST_STATUS]] içindedir; sürüm pinleri değişmedi.

P5 motoru mevcut lxml/zipfile/hashlib/UUID ile yazıldı; üçüncü taraf helper kodu kopyalanmadı. Sentetik kaynak bundled Python 3.12.14'te oluşturuldu. Bundled runtime'da duckdb/jsonschema yoktu; Store ve gerçek Word QA sabit Python 3.14.8/pywin32 ile koştu. `render_docx.py` mevcut ortamda LibreOffice/soffice bulunmadığından başarısız oldu; rapor korundu, kurulum yapılmadı. Native Word PDF dışa aktarımı ve sabit PDFium ile dört görüntü üretildi. Yeni bağımlılık, Word global seçenek değişimi veya pin değişikliği yok; ürün hostundaki izin/QA yolu açık.
## P6 geliştirme yapılandırma doğrulaması

İki seçilmiş Python runtime'da PyYAML olmadığı için skill-creator quick_validate çalışamadı. Paket kurulmadı. Mevcut Microsoft365 CLI node_modules içindeki `yaml` paketi yalnız 30 SKILL ve UI YAML dosyasını gerçekten parse eden geliştirici kontrolünde kullanıldı; ürün ZIP'ine parser kodu/bağımlılığı kopyalanmaz. Tam sürüm/path `reports/p6-skill-configuration.json` içinde. Para/tarih modülleri stdlib Decimal/datetime/calendar kullanır.

Canonical Agent Plugins 1.0.0 JSON Schema sabit URL'den indirildi; SHA256 0a4aad95…ab883 ve mevcut jsonschema ile gerçek doğrulama PASS. Node/Python kontrol betikleri ve Claude strict manifest doğrulaması host kurulumu/iş kabulü değildir. Hiçbir yeni program, Python paketi veya plugin kurulmadı.


## Dev.2 otomatik bağımlılık hazırlığı

Güncelleyici2.3.0 kaynak motoru vendor/guncelleyici altında upstream manifest hash'leriyle birebir gömüldü. Önceki “helper kopyalanmadı” kayıtları önceki fazlara aittir; bu dilimde kullanıcının yayımlanmış motoru gömüldü.13 sabit runtime paketi yalnız yeni private venv'de; DuckDB PDF6535c81 engine1.5.6 için imza kontrolü açık özel dizinde gerçek kurulup test edildi. BinaryZIP'e konmaz; motor referansı GPL-2.0-or-later lisansını açık tutar, genel lisans onayı iddia edilmez. Ortak Python/paket/PDF envanteri değişmedi. Yeni ana Python kurucusu ve genel personel kabulüNOT_RUN. Eski tablo “ürün yolunda kapalı” dev.1 envanteridir; dev.2 ön kontrol LOAD/API kullanır, PDF sözleşme okuyucusu hâlâ pypdf/PDFium'dur. [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/RUNTIME_AND_STARTUP]].
