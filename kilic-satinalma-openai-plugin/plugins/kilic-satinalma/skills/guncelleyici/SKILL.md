---
name: guncelleyici
description: Windows araç sürümlerini tarar, seçimi ve somut planı kullanıcıya gösterir; yalnız açık uygulama onayıyla sabitlenmiş Güncelleyici motorunu çalıştırır. Güncelleyiciyi çalıştırma, programları güncelleme veya kurulum işlev kontrolünde kullan; teklif analizi otomatik kurulum çağrısı değildir.
---

# Güncelleyici

## Kurumsal dil

[Kurumsal Dil ve Yayın Standardı](../../EDITORIAL-POLICY.md) uygulanır. Kullanıcı soruları ve bütün çıktı metinleri resmî ve nesnel dille hazırlanır; kişisel hitap ve sohbet geçmişine atıf kullanılmaz.

## Her çağrıda başlangıç bildirimi

Bu beceri fiilen çalışmaya başladığında, ilk kullanıcı mesajında ortak okuyucunun ürettiği satırı aynen göster. Kendi paketindeki `../../scripts/skill_startup.py --skill guncelleyici` komutunu kendi fiziksel skill klasöründen çalıştır; başka plugin'in aynı adlı skill'ini genel adla çağırma. Okuyucu gerçek beceri adını ve o çağrıdaki VERSION dosyasını kullanır:

**[Beceri adı] skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: [gerçek sürüm]**

Köşeli alanlar yalnız şablondur; kullanıcıya gösterilmez. Ad veya sürüm kaynağı eksik/bozuk/çelişkiliyse hatayı bildir ve becerinin asıl işlemini başlatma. Plugin sürümünü skill sürümü yerine yazma.

Ana akış bir alt skill'in görevini başlatacaksa ana ajan o alt skill'in gerçek satırını kullanıcı kanalında **görev dispatch'ından önce** gösterir. Alt ajan kullanıcıya ayrı mesaj göndermez ve görev JSON'una bildirim öneki eklemez. Yalnız bir referansı okumak veya sıradaki adım olarak bir skill'den bahsetmek bildirim gerektirmez. Başka bir gerçek çağrı başladığında tekrar göster.

## Motor ve yetki

Bu pakette tek seçilebilir Güncelleyici girişi burasıdır. Birebir korunan2.3.0motor [vendor/guncelleyici/SKILL.md](../../vendor/guncelleyici/SKILL.md) içindedir. Başlangıç sürümü doğrudan motorun VERSION dosyasından okunur, buradaki VERSION eşlik kontrolüdür. Araç uygulamasında `<SKILL>` gerçek `vendor/guncelleyici` klasörüdür; komut/başvuru yolları o dosyanın klasörüne göre çözülür.

Python bulunmaması Güncelleyici bildirimi için kurulum ön koşulu değildir. Bu durumda yerel PowerShell'de salt okunur `Get-Content -LiteralPath "<aktif-paket>/vendor/guncelleyici/VERSION" -Encoding UTF8` ve girişin `VERSION` dosyasını oku. İki sürüm açık ve aynıysa gerçek beceri adı “Güncelleyici” ile yukarıdaki tam cümleyi kullanıcıya göster. Eksik, geçersiz veya farklı sürümde dur. Bildirim için Python kurma veya sürüm varsayma; bundan sonra motorun mevcut PowerShell tarama/kurulum yolunu kullan. Komutları arka planda ajan yürütür, kullanıcıya komut kopyalatılmaz.

Başlangıçtan sonra motor SKILL.md'nin tarama/seçim/açık plan onayı/bakım/verify/kurtarma yönergelerini uygula. Bu wrapper kurulum, automatic-update, istemci ayarı, süreç kapatma veya güvenlik politikası yetkisini genişletmez. Kullanıcı yalnız teklif analizi istediğinde Güncelleyici kendiliğinden başlamaz.
