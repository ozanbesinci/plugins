# Kabul, pilot ve kontrollü kurtarma

> **Yalnız geliştirici/BT kabulü:** Bu dosyadaki terminal komutları normal personel
> kullanım akışının parçası değildir. Son kullanıcı Güncelleyici'yi ChatGPT Desktop
> Work/Codex sohbetinden kullanır; yerel komutları ajan kendi aracıyla çalıştırır.

## Testleri çalıştırma

Python testleri geçici klasör ve sahte paketler kullanır; ağ, program kurulumu ve
canlı kullanıcı ayarı değiştirmez. `pypdf` zaten kuruluysa PDF fixture okuma testi de
çalışır; test koşucusu bağımlılık kurmaz.

```powershell
& "<Python>" -B -m unittest discover -s "<SKILL>\tests" -p "test_*.py" -v
powershell.exe -NoProfile -File "<SKILL>\tests\test_windows.ps1"
```

İkinci komut bütün PowerShell dosyalarını gerçek PowerShell parser'ıyla denetler,
sonra gerçek kurucuları çağırmadan fixture'larla plan/kilit/sonuç akışını sınar.
Onun geçmesi de gerçek kurulum kabulü değildir.

## Gerçek Windows kabul matrisi

| Aşama | Ortam / senaryo | Başarı koşulu |
|---|---|---|
| Sözdizimi ve birim test | Windows PowerShell 5.1, normal kullanıcı | Python testleri ve test_windows.ps1 geçer |
| Temiz kurulum | İzole test bilgisayarı veya geri alınabilir VM; x64; normal kullanıcı | Yedi bileşenin bağımlılık sırası, iki aşamalı tarama ve sonuçları doğru |
| Var olan ortam | Eski/güncel sürüm, makine geneli kurulum, PATH önceliği | Yetkisiz ikinci kopya/üzerine yazma yok; gerçek son konum doğru |
| Ağ ve bütünlük | Çevrimdışı, proxy, geçersiz TLS, değiştirilmiş hash/paket | Hedef uydurulmaz; kurulum başlamaz; hassas bilgi sızmaz |
| Arıza enjeksiyonu | Dosya kilidi, PATH/ayar yazımı hatası, düşük disk, süreç kesilmesi | Eski çalışan durum korunur veya kurtarma gereği açık, kalıcı kayda dönüşür |
| MCP | Özel env/args/TOML alanları, açık/kapalı istemci, bozuk JSON | Özel alanlar kaybolmaz; belirsiz kayıt korunur; her istemci bağlantısı ayrı doğrulanır |
| Excel | Gerçek masaüstü Excel + pywin32 | Kullanıcının açık Excel'i korunur; yalnız teste ait süreç kapanır |
| Teklif | Şema 1/2/3, yerel değiştirilmiş dosya, snapshot hazırlığı | Yalnız teklif ağacı değişir; bütünlük ve geri dönüş doğru |
| PDF | Gerçek motor/sürüm/platform + metin ve tablo test belgeleri | Native imza/LOAD testi ve gerçek belge kabulü geçer; eşleşme kaydedilir |

Önce tek BT test cihazı, sonra iki temsilî personel cihazı ile pilot önerilir.
Tüm kritik kabul koşulları geçmeden genel dağıtım yapma. Bu tablo test planıdır;
çalıştırılmamış satırlar PASS olarak işaretlenmez. Yeni GitHub Release, sürüm etiketi
ve eklenti genel dağıtımı kullanıcıdan ayrıca açık yayın yetkisi gerektirir.

## Yarım işlemde davranış

1. Yeni `apply` veya kör onarım başlatma. `active-transaction.json`, ilgili session
   raporu, teklif/PDF alt günlükleri ve yedek yollarını koru.
2. BT, hangi işlem ve çocuk süreçlerin hâlâ çalıştığını belirlesin. Güncelleme kilidi
   dosyalarını sırf eski göründüğü için silme. İlgisiz kullanıcı süreçlerini kapatma.
3. Yerel sürüm, dosya hash'i, PATH ve etkilenen istemci ayarlarını oku. Yedeklerin
   hangi işlemden geldiğini ve bütünlüğünü kontrol et.
4. Yalnız doğrulanmış önceki sürüme/ayara kontrollü dönüş ya da onaylanmış yeni
   kurulum kararı ver. Kısmi pip değişikliğinin kendiliğinden geri alındığını varsayma.
5. Gerçek işlev kontrolleri başarılı olduktan ve operatör kararı kaydedildikten sonra
   ilgili günlük için kontrollü kapatma işlemi yap. Bu adayda otomatik “kilit temizle”
   komutu özellikle yoktur; kaydın kaldırılması sessiz/otomatik olmamalıdır.

Kurtarma geçmişini kurulumla aynı loga ekle; yeni testin eski başarısız kaydı gizlemesine
izin verme. Dosya yedeği varlığı, ortamın geri döndüğü anlamına gelmez.
