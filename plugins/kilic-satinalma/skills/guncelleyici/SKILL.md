---
name: guncelleyici
description: Python, Python kütüphaneleri, Node.js, pnpm, DuckDB, Power BI Modeling MCP ve teklif-degerlendirme skill sürümlerini sohbet tablosunda karşılaştırır; kullanıcının seçtiklerini günceller. "Güncelleyiciyi çalıştır", "programları güncelle" veya "teklif skill'ini güncelle" isteklerinde kullan.
---

# Güncelleyici

## Tek giriş: sohbet içi seçim

Yerel Windows ortamında `scripts/sohbet.ps1` dosyasını PowerShell 5.1 ile
çalıştır. `<SKILL>`, bu dosyanın bulunduğu klasörün tam yoludur. Tabloyu
PowerShell penceresinde açma; `@@SONUC` JSON kaydındaki `rows` verisini **sohbette
Markdown tablosu** olarak göster. Bu akış masaüstü Work ve Codex'te aynıdır.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL>\scripts\sohbet.ps1" -Action scan
```

Kullanıcı **Güncelle** dedikten sonra eski `program-guncelle` /
`program-guncelleme` skill kurulumu
standart kullanıcı skill yollarından kaldırılır. Junction ise yalnız bağlantı
kaldırılır; fiziksel eski skill doğrulandıktan sonra kullanıcı alanındaki
karantinaya taşınır. Yeni `guncelleyici` ve hedef skill ağacına bu temizlikte
dokunulmaz.

Tarama bilgisayardaki yüklü sürümleri ve çevrimiçi güncel kararlı
sürümleri salt okuma seçenekleriyle denetler. `teklif-degerlendirme` sürümü
GitHub'daki doğrulanmış Release paketinin manifestinden okunur. İnternet
doğrulaması yapılamayan satır “Kontrol edilemedi” gösterir; sürüm uydurulmaz.
Bu durumda satırın durum sütunu ağ erişimi engelini belirtir; ayrıntılı hata
`ayrinti` alanında ve işlem sonucunda korunur. Gerçekten yüklü olmayan bileşenin
yüklü sürüm hücresi **Yüklü değil** olur; seçilirse güncel kararlı sürüm kurulur.
Eksik ve eski bileşenler **varsayılan seçili** gelir (`secili: true`); kullanıcı
seçimleri sohbetten değiştirebilir. Güncel veya güncelliği doğrulanamayan
satırlar seçilmez.
Tüm bileşenler yüklüyse ve hedef sürümlerle eşleşiyor veya onlardan ilerideyse
tablo gösterilmez: yalnız **Güncelsiniz.** denir ve bitirilir. Bir satırın kontrolü
başarısızsa bu kısa çıkış kullanılmaz.
Python kütüphaneleri bir set olarak
listelenir; o satır seçilirse 12 desteklenen paket birlikte kurulur ve sınanır.
Power BI MCP de aynı varsayılan seçim kuralına tabidir. Başka bir
başlangıç onayı veya ayrı Power BI sorusu sorma.

`status: selection_required` geldiğinde yedi satırı şu sırada göster: Python,
Python kütüphaneleri, Node.js, pnpm, DuckDB, Power BI Modeling MCP,
teklif-degerlendirme. Tablo sütunları **Seçim / Bileşen / Yüklü / Güncel /
Durum** olsun. `secili: true` için `☑`, diğerleri için `☐` yaz. Kontrol
edilemeyen satırın `ayrinti` bilgisini tablonun altında belirt. Ardından
“Varsayılan seçimlerle güncellemek için **Güncelle** yazın; değiştirmek için
bileşen adlarını, vazgeçmek için **İptal** yazın.” de. Kullanıcı yanıtını
bekle. Varsayılan seçimler kendi başına kurulum yetkisi değildir.

Kullanıcı **Güncelle** dediğinde veya yeni seçimini açıkça bildirdiğinde yalnız
seçili satırların `key` değerlerini, tarama kaydındaki `fingerprint` ile birlikte
ver. Örnek:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL>\scripts\sohbet.ps1" -Action apply -Keys "python,libraries,duckdb" -Fingerprint "<scan fingerprint>"
```

Kullanıcı **İptal** derse `apply` çağırma. Bağımlılık seçimini kullanıcı
kaldırabilir: Python gerektiren
satırlarda Python yoksa veya pnpm için Node.js yoksa ilgili satırın sonucu
açık hata olur. Betiğin tamamlanmasını bekle; çıkan `@@SONUC` JSON kaydındaki
`results` ve `rows` ile **sohbette sıralı son durum tablosu** göster. Seçilmeyen
adaylar “Atlandı · seçilmedi” olarak kalır.
Güncel, yayından yeni ve kontrol edilemeyen satırların durum bilgisi korunur.
Komutu izlenemeyen bağımsız bir süreç olarak bırakma; doğrudan çalıştır veya
`Start-Process -Wait` ile çıktısını al. `status: stale` dönerse sürümler taramadan
sonra değişmiştir; gelen yeni `rows` ile tabloyu yenile, yeniden seçim bekle.
`status: busy` dönerse eşzamanlı başka kurulum var; bunu bildir. Betiklerin
nihai `@@SONUC` kayıtları, süreç çıkış kodu ve kurulum sonrası sürüm sonucu
belirler. Kullanıcı adına **Güncelle** kararı verme.

Kurulumlar yalnız kararlı yayınları kullanır. Var olan betiklerin imza, SHA-256,
geri dönüş, kullanıcı alanı, süreç engeli ve IT raporu kuralları korunur.
Uygulama ayrıntıları: [program ve ortam](references/program-kurulumu.md),
[teklif paketi](references/teklif-paketi.md).

Sonraki sürüm değişiklikleri ve GitHub yayınları ayrı kullanıcı talimatıyla
yapılır; yerel geliştirme kayıtları `CHANGELOG.md` içinde “Yayımlanmamış”
altında tutulur.
