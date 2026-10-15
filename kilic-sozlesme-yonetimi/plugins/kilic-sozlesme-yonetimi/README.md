---
title: Kılıç Sözleşme Yönetimi ürün paketi
created: 2026-10-04
modified: 2026-10-15
type: project
status: 🟢 0.1.0 kararlı sürüm
tags: [is, sozlesme]
tazele: 2026-10-14
---

# Kılıç Sözleşme Yönetimi ürün paketi

Kararlı sürüm 0.1.0: plugin/beceriler 0.1.0, çekirdek 0.2.0, P6 sonuç p6-1.2, Güncelleyici 2.3.0. Bileşen ve build kimliği [component-identity](references/component-identity.md) sözleşmesine bağlıdır. Yayın kararı 2026-10-15'te satınalma direktörü tarafından verildi. Bu karar şu kayıtlara dayanır: aynı baytlarda tam test koşusu, temiz kurulum, Claude Code ve Codex'te gerçek kullanıcı cümlesiyle deneme, uzman incelemesi ve kurum kullanım kararı. Özel kanıtlar ürün paketinin ve deponun dışında tutulur. Kullanım kapsamı satınalma ve ithalat personelinin sözleşme ön incelemesidir; çıktı hukuki görüş değildir.

Normal üretim Word çıktısı 0.1.0'da kurum kararıyla kapalıdır (CONFIG_REQUIRED); hedef sürüm 0.2.0. K29 yalnız sohbet taslağı; e-posta gönderme veya mailbox taslağı oluşturma yoktur. Teknik başarı iş/uzman/şirket onayı sayılmaz. Kaynak değişikliği, erişim kaybı, eski revizyon, yetersiz zorunlu kanıt ve bütçe aşımı kapalı ret üretir; sohbet yanıtı eksik eki, eski kaynağı veya bütçe aşımını ayrı ve somut söyler. K27 portföy ölçümü `portfolio-overview` ile yalnız açıkça listelenen case'leri ayrı ayrı denetler; okunamayan case dışarıda kalır, ölçümler pay/payda ile verilir. Okuyucu profili değişince `context-rebind` kaynak düğümlerini yalnız birebir aynı metinle güncel okumaya taşır; eşleşmeyeni raporlar.

Host başlangıcı `scripts/contract_cli.py`; PowerShell girişi `scripts/beceri-baslat.ps1`. [Başlangıç sözleşmesi](references/cli-startup-contract.md), [istek/audit/beyan](references/request-audit-lifecycle.md), [okuyucu kaynak bütçesi](references/reader-process-budgets.md), [Windows nesne sınırı](references/windows-source-object-boundary.md) ve [işleme kilidi](references/processing-lock-phases.md) geçerli teknik kapsamı anlatır.

Güncel test altyapısı [product-test-strategy](references/product-test-strategy.md), koşucu `scripts/run_product_tests.py`, kapsam manifesti `tests/manifest.json`. Bir test makbuzu olmadan mevcut baytlar PASS kabul edilmez. Farklı kaynak digest'lerinin sonuçları birleştirilmez. Tarihsel P1–P7 belgelerindeki345 ve diğer PASS sayıları eski fazlara aittir; güncel kabul değildir. Native kurulum, gerçek host, kurumsal ayrı kimlik, uzman ve ekip pilotu kendi gerçek kayıtlarıyla doğrulanır.

Kaynak depo [ozanbesinci/plugins](https://github.com/ozanbesinci/plugins), proje `kilic-sozlesme-yonetimi/`. [Proje README](../../README.md) sabit kaynak/kurulum kayıt koşulunu açıklar. Yerel geliştirme ağacı yayımlanan kaynağın üzerine kopyalanmaz; 001–006 migration ve vendor baytları korunur. [Bilinen sınırlar](KNOWN_LIMITATIONS.md) ve eski faz belgeleri tarihsel kanıt olarak kalır.
