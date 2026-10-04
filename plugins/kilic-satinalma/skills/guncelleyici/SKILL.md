---
name: guncelleyici
description: Windows'ta Python, sabit Python paket seti, Node.js, pnpm, DuckDB, Power BI Modeling MCP sürümlerini kontrol eder; yalnız açık kullanıcı onayıyla sabitlenmiş planı uygular. İsteğe bağlı DuckDB PDF eklentisi, işlev kontrolü ve onarım planı sunar. "Güncelleyiciyi çalıştır", "programları güncelle", "DuckDB PDF eklentisini ekle" veya bu kurulumları doğrulama isteklerinde kullan. Bir skill'i inceleme/geliştirme isteğini canlı kurulum yetkisi sayma.
---

# Güncelleyici

## Durum ve sınır

`BUILD.json` sürümün yayın ve kabul durumunu gösterir. `VERSION` kaynak sürümdür;
GitHub'da yayımlanmış olması personel genel dağıtım/üretim onayı anlamına gelmez.
[Windows kabul kontrollerindeki](references/kabul-ve-kurtarma.md) çalıştırılmamış
aşamaları PASS sayma. Kaynak yayın, canlı kurulum, istemci ayarı değiştirme ve
üretim dağıtım onayı farklı yetkilerdir.

Yerel Windows PowerShell 5.1 ve gerçek kullanıcı dosya sistemi olmadan kurulum
başlatma. Bulut/Linux oturumunu kullanıcının bilgisayarı gibi gösterme. Bu durumda
paketi/sonucu ver; yerel kurulum yapılmadığını belirt. Yönetici yükseltmesi, güvenlik
politikası atlatma, imzasız eklenti veya kullanım sözleşmesi kabulü yapma.
Komutlar mevcut Windows çalıştırma politikasını devralır. Politika yürütmeyi
engelliyorsa BLOCKED bildir; otomatik Bypass veya politika değişikliği uygulama.

## Tek giriş: sohbet tablosu

Son kullanıcı yüzeyi yalnız **ChatGPT Desktop Work veya Codex sohbetidir**. Kullanıcıdan
Terminal/PowerShell açmasını, komut kopyalamasını, script çalıştırmasını veya teknik
çıktı toplamasını isteme. Bu dosyadaki PowerShell komutları kullanıcı talimatı değildir;
Work/Codex bunları kendi yerel shell/terminal aracıyla arka planda çalıştırır. Yerel Windows
hostunda komut çalıştırma yeteneği yoksa kurulumu kullanıcıya devretme; "yerel yürütme
kullanılamıyor" diyerek dur. Geliştirici/BT kabul testi açıkça istenmişse bu kuralın
test komutları için istisnası vardır.

`<SKILL>` fiziksel skill klasörüdür. Başlangıçta başka kurucu çağırma; eski GUI
`panel.ps1` artık doğrudan çalışmaz. Scan kurulum/ayar/sağlık kaydı yazmaz; yalnız
geçici plan ve doğrulanacak paket önbelleği oluşturabilir.

Work/Codex'in yerel aracında çalıştırılacak iç komut:

```powershell
powershell.exe -NoProfile -File "<SKILL>\scripts\sohbet.ps1" -Action scan
```

Son `@@SONUC` JSON'unu oku. `rows` ve `global_effects` verisini **Seçim / Bileşen / Yüklü / Hedef /
Durum** sütunlarıyla sohbet içinde göster. `secili=true` için ☑, diğerleri için ☐
kullan. İlk altı satır eski sıradadır; isteğe bağlı PDF satırı yedincidir.
Sürüm/tarih/hash uydurma; `blocked`, `pending`, `health` ve hata ayrıntılarını gizleme.
`up_to_date`, yalnız sürüm uygunluğudur: **"Sürüm kontrolü güncel; bu taramada işlev
testi çalıştırılmadı."** de. Önceki başarısız kontrol/bağlantı varsa onu da göster.

PDF kullanıcı tarafından istenmişse taramaya `-IncludePdf` ekle. PDF varsayılan
seçili değildir. Kullanıcının açık PDF kurulum talebi seçim niyetidir; gösterilen
paketin uygulanması için yine plan onayı al. [PDF kuralları](references/duckdb-pdf.md).

## Seçim ve uygulama yetkisi

Seçim değiştirmek kurulum değildir. "Yalnız Python seçili olsun" tablodaki seçimi
değiştirir; `apply` çağırma. "Güncelle", "bu seçimleri uygula" gibi açık uygulama
onayı bekle. Bağımlılıkları gizlice kurma; eksik Python/Node varsa önce gerekli
kurulumu planla, ardından yeniden tara. Çözülemeyen satır seçilemez.

Tek onay mesajında yalnız seçili satırların `effects` kayıtlarını ve `global_effects` etkilerini göster: seçili paketler ve sürümler,
Python paket setindeki **paket adı + eski sürüm → hedef sürüm** düşürmelerini tek tek, eski skill bağlantılarının kaldırılması/
fiziksel klasörlerin karantinaya alınması, Power BI'nin kurulu istemcilerdeki
`powerbi-modeling` kaydına bağlanması ve yeniden başlatma ihtiyacı.

Python/kütüphane/Node/pnpm/DuckDB değişecekse kullanıcıdan aktif işleri tamamlayıp
bakım penceresini doğrulamasını aynı onayda iste. Bunu varsayma. Gerçek kullanıcı
programlarını otomatik kapatma. Çalışan Python/Node iş yükü bulunursa kurulum durur.

Work/Codex'in yerel aracında, yalnız açık uygulama onayından sonra çalıştırılacak iç komut:

```powershell
powershell.exe -NoProfile -File "<SKILL>\scripts\sohbet.ps1" -Action apply -PlanFile "<scan plan_file>" -Fingerprint "<scan fingerprint>" -Keys "node,pnpm" -MaintenanceWindow -ConfirmApply
```

`-Keys` sadece kullanıcının onayladığı seçimi içerir. `-ConfirmApply` yalnız kullanıcının açık **Güncelle / bu seçimleri uygula** yanıtından sonra verilir; yalnız seçim düzenleme yanıtında bu bayrağı verme ve `apply` çağırma. `-MaintenanceWindow` yalnız
kullanıcı bakım durumunu teyit etmişse verilir. Yalnız Power BI/PDF için bu
parametre gerekmeyebilir. Plan dosyasını düzenleme, yeniden hash üretip eski onayı
kullanma veya installer hedefini değiştirerek engeli aşma. Hedefler uygulamada yeniden
"latest" olarak seçilmez. Süresi dolmuş veya değişmiş plan için yeniden seçim al.

`İptal` yanıtında `apply` çağırma. `stale` veya kilit hatasında tekrar tekrar deneme;
yeni tarama ya da gerekli bekleme durumunu bildir. İşlemi izlenemeyen arka süreç
olarak bırakma. Nihai süreç kodu, JSON ve yerel son durum sonucunu birlikte kullan.
Sıfır olmayan kod veya `error` başarı değildir. `warning` ve seçilmeyenleri göster.

## Sonuç ve kurtarma

`results`, `rows`, `maintenance`, `report`, `recovery_required` alanlarını oku.
Tam ayrıntıyı logda tut; sohbette kısa hata kodu/açıklaması ve rapor yolunu göster.
Temizlik veya bağlantı uyarısını kurulum başarısızlığıyla karıştırma; ikisini ayır.
`recovery_required=true` veya işlem günlüğü varsa yeni kurulum başlatma, kilit/günlük
silme, körlemesine tekrar çalıştırma. [Kurtarma prosedürünü](references/kabul-ve-kurtarma.md)
kullan; doğrulanamayan çalışır durum hakkında olumlu iddiada bulunma.

## İşlev kontrolü ve açık onarım

Sürüm taraması kurulum doğrulaması değildir. Kullanıcı "çalışıyor mu kontrol et"
dediğinde paket kurmadan aşağıdaki yolu kullan. Excel/MCP kontrolünün geçici test
dosyası ve kendisine ait süreç başlatacağını belirt; bunlar kullanıcı verisi değildir.

Work/Codex'in yerel aracında çalıştırılacak iç doğrulama komutu:

```powershell
powershell.exe -NoProfile -File "<SKILL>\scripts\sohbet.ps1" -Action verify -Keys "libraries,duckdb"
```

Aynı sürümde yeniden kurma/onarım gerektiğinde `scan -RepairKeys "libraries,duckdb"`
ile **yeni** plan çıkar. Kullanıcı onayı olmadan zorla yeniden kurma. Python ana
kurucusu için aynı sürüm zorla üzerine yazma desteklenmez.

Power BI sunucusu çalışsa bile açık Codex/Claude istemcisinin ayarlarını değiştirme;
bağlantıyı ertelenmiş göster. Kapalı istemcide ayrı açık bağlama isteği için
[program kurulum referansındaki](references/program-kurulumu.md) `-BindOnly` yolunu kullan.

## Başvuru

Program ayrıntıları: [program-kurulumu.md](references/program-kurulumu.md).
Tasarım değişiklikleri ve ertelenen işler: [degisiklik-haritasi.md](references/degisiklik-haritasi.md).
Harici teknik kaynaklar: [kaynaklar.md](references/kaynaklar.md).