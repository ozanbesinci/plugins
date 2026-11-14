# Kararlı sürüm 0.2.0 — iç çalışma taslağı Word

K28 iç çalışma taslağı üretimi açıldı: ayrı iki aşamalı yapısal/native/görsel QA ve kaynak/sürüm bağı. Çekirdek 0.4.0, P6 p6-1.4, migration008. Şirket imzası/kurumsal onay verilmez; P4/P5 genel üretim eylemleri ve e-posta gönderimi kapalıdır. [Kullanım ve sınırlar](references/internal-drafts.md). Önceki sürüm kayıtları aşağıda tarihseldir.

# Yerel EGM düzeltme adayı 0.1.3-dev.1

14 önemli bulguya yönelik kaynak/sürüm/bağlam ve test güvencesi düzeltmeleri. Çekirdek 0.3.0-dev.1, P6 sonuç p6-1.3, migration 007. Word üretimi kapalıdır. Bu aday yayımlanmış veya kurumsal kabul almış sayılmaz. Yeni veri şemasını eski çekirdek SEMA_DRIFT ile güvenli reddeder; otomatik downgrade yok. Ayrıntılar [EGM düzeltmeleri](references/egm-fixes-0.1.3.md).

Aşağıdaki önceki sürüm açıklamaları tarihsel bağlamdır.

---
title: Kılıç Sözleşme Yönetimi ürün paketi
created: 2026-10-04
modified: 2026-10-22
type: project
status: 🟢 0.1.2 otomatik Windows kurulumu
tags: [is, sozlesme]
tazele: 2026-10-24
---

# Kılıç Sözleşme Yönetimi ürün paketi

Work sürümü 0.1.2: plugin ve 30 beceri 0.1.2, çekirdek 0.2.1, P6 sonuç p6-1.2. Güncelleyici becerisi/motoru kaldırıldı. Ayrı Windows EXE’si, Python ve 13 sabit paketi kullanıcı alanına kurar. Work bütün komutları kayıtlı ortam üzerinden yürütür. Kullanıcıdan terminal/Python komutu beklenmez. Kurucu imzasızdır; ikinci gerçek Windows cihazında kurulum kabulü açık kalır. Dev.2 aynı bilgisayarda masaüstü/Bulut ve web bağlantı kontrolünü geçti; yeni sürümün kanıtı ayrıca kaydedilir. Kararlı sürüm numarası kurumsal yayın veya sınırsız iş kabulü anlamına gelmez. Ayrıntılar [runtime-integration](references/runtime-integration.md) ve [bileşen kimliği](references/component-identity.md) içindedir.

0.1.2 ilk kullanımda eksik Windows ortamını otomatik indirip kurar. Kurucu sabit boyut/SHA-256 ile doğrulanır, ardından gerçek native READY kontrolü yapılır. Kullanıcıya indirme bağlantısı veya kurma görevi verilmez; geliştiriciden kişisel izin istenmez. Uyumlu Windows kurucusu 0.1.1 olarak kalır.
