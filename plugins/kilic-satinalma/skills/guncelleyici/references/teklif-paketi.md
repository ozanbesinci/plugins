# Teklif paketini doğrulama ve güncelleme

Kaynak depo `ozanbesinci/teklif-degerlendirme` olarak korunur. Paket etiketi ile
bileşen sürümü farklı olabilir. Şema 1/2 eski çift-skill paketleri okunur; birleşik
güncelleyici yalnız `teklif-degerlendirme` ağacını yerleştirir. Şema 3 tek-skill
paketini destekler. Eski güncelleyici ağacı tekrar kurulmaz.

Normal kullanıcı yolu `sohbet.ps1 scan/apply`dır. Python mevcut olduğunda tarama
`teklif-guncelle.py prepare` ile tüm manifesti doğrular; indirilen ZIP uygulamada
aynı hash ile kullanılır. Uygulama sırasında yeni Release seçilmez.

Paket; ZIP SHA-256, kaynak, sürüm, dosya hash'leri, Windows ad/yol kuralları,
Unicode/case çakışmaları, bağlantılar, dosya/dizin çakışması, boyut ve dosya sayısı
sınırlarıyla doğrulanır. Ana skill giriş dosyası `oturum_kontrol.py` gerektiriyorsa
bu dosyanın varlığı da zorunludur. Bu kontroller, bütün Python işlevlerinin işletim
sisteminde başarıyla çalıştığı anlamına gelmez; kabul testi ayrıca gerekir.

Yönetimsiz kurulum veya dosya değişikliği saptanırsa üzerine yazılmaz. Yeni kayıt
`.guncelleyici-teklif-install.json`; eski kayıt `.teklif-install.json` okunabilir.
Kayıttaki sürüm gerçek VERSION dosyasıyla da karşılaştırılır. Hazırlık, değişim,
kayıt yazımı ve geri dönüş denetlenir. Başarıdan sonra önceki ağaç yedekte tutulur.
Temizlik sorunu, başarılı kurulumu hatalı şekilde yok saymak yerine uyarı verir;
inceleme gerektiren günlük korunur.

## Açık teknik bakım komutları

`<skills>` fiziksel ortak skill kökü, `<Python>` desteklenen yorumlayıcıdır.

```powershell
& "<Python>" "<SKILL>\scripts\teklif-guncelle.py" probe --root "<skills>"
& "<Python>" "<SKILL>\scripts\teklif-guncelle.py" verify --root "<skills>"
& "<Python>" "<SKILL>\scripts\teklif-guncelle.py" prepare --root "<skills>" --cache "<geçici önbellek>"
```

`update` artık parametresiz rolling güncelleme yapmaz; daha önce doğrulanmış ZIP,
SHA-256, paket sürümü ve beklenen bileşen sürümü gerekir. Kullanıcının açık bakım
onayı olmadıkça bu yolu çağırma:

```powershell
& "<Python>" "<SKILL>\scripts\teklif-guncelle.py" update --root "<skills>" --archive "<doğrulanmış ZIP>" --sha256 "<hash>" --release "<X.Y.Z paket>" --expected-version "<X.Y.Z bileşen>"
```

`register --archive ... --sha256 ...`, mevcut ağacın tam eşleştiğini denetleyen
ayrı geliştirme bakımıdır; dosya kurmaz. `--replace-local` yalnız aynı sürümde açık
kullanıcı geliştirme yetkisiyle kullanılır. Yerel değişikliği gizlemek için kullanılmaz.

Güncel v4 analiz koşusu kendi skill kopyasını kullanabilir. Bununla birlikte ortak
Python paketlerini veya kullanıcı ayarlarını aynı anda değiştirmek otomatik olarak
güvenli değildir. Eski analiz kilidi ve yarım günlüğü silme. `verify` yalnız dosya
bütünlüğünü doğrular; gerçek satınalma kararının veya Excel üretiminin testi değildir.
