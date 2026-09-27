# Teklif değerlendirme skill'i — sürüm kontrolü ve güncelleme

Resmî depo `ozanbesinci/teklif-degerlendirme`. Birleşik `guncelleyici`, eski
Release paketlerini de okur; ZIP içindeki eski güncelleyici ağacını **kurmaz**.
Yalnız `teklif-degerlendirme` ağacı yönetilir. Program kurucuları bu işlemde
çalışmaz. Yerel aday ile yayımlanmış sürümü karıştırma.

## Sohbet akışı ve bakım komutları

Normal kullanımda birleşik güncelleyici sürüm tablosunu sohbette gösterir.
GitHub'daki en son kararlı Release paketinin SHA-256 değerini doğrulayarak
`teklif-degerlendirme` bileşen sürümünü ilk tabloda gösterir. Yalnız bu satır
seçildikten ve kullanıcı **Güncelle** dedikten sonra aşağıdaki `update` ve
ardından `verify` çalışır. Yerel aday yayımlı sürümden ileriyse sürüm düşürülmez.

Doğrudan bakım veya tanı gerektiğinde komutlar:

`<SKILL>` birleşik skill klasörü, `<skills>` fiziksel ortak skill köküdür:

```powershell
& "<Python yolu>" "<SKILL>\scripts\teklif-guncelle.py" check --root "<skills>"
& "<Python yolu>" "<SKILL>\scripts\teklif-guncelle.py" update --root "<skills>"
& "<Python yolu>" "<SKILL>\scripts\teklif-guncelle.py" verify --root "<skills>"
```

`check` sonucunda `latest` doğrulanmış bileşen sürümüdür; `release.version`
paket etiketidir. Sohbet tablosu ve `update` aynı bileşen sürümüne göre karar verir.
`update` yalnız bileşen sürümü ileriyse çalışır; karar için doğrulanan paket
kurulumda yeniden indirilmeden kullanılır.

Betik yeni paketin SHA-256 ve dosya manifestini, ZIP yollarını, bileşen
sürümlerini ve v4 çalışma dosyalarının varlığını doğrular. Önceki teklif ağacı
paket kaydıyla eşleşmiyorsa üzerine yazmaz. Güncelleme kilidi/analiz kilidi
ve yarım işlem günlüğü varsa durur; kendiliğinden temizleme. Başarısız değişimde
eski ağaç geri konur. Çıktıda `status: error` varsa güncel sayma.

Eski `.teklif-install.json` kaydı yalnız teklif ağacı için okunur; yeni kayıt
`.guncelleyici-teklif-install.json` içinde tutulur. Eski paket formatında
güncelleyici ve ana skill bağımsız sürümlüdür. Yeni tek skill paket formatı
şema 3'tür; yeni Release yayımlanması ayrı yetki gerektirir.

Yerel geliştirme adayını kayda almak gerektiğinde, mevcut teklif ağacıyla
birebir eşleşen şema 3 paketini `../teklif-degerlendirme/scripts/paket_olustur.py`
ile hazırla ve hesaplanan SHA-256 ile şu komutu kullan:

```powershell
& "<Python yolu>" "<SKILL>\scripts\teklif-guncelle.py" register --root "<skills>" --archive "<paket.zip>" --sha256 "<64-karakter-özet>"
```

`register` yalnız dosyalar paket manifestiyle birebir eşleşirse kayıt yazar;
paketin içeriğini kurmaz ve dosya değişikliğini gizlemez.
Kaydedilmiş aynı sürüm yerel adayında açık geliştirme değişikliği yapıldıysa
paketi yeniden oluşturup yalnız bu komuta `--replace-local` ekle. Yeni paket
mevcut ağaçla birebir eşleşmeli; sürüm değişimine bu seçenek izin vermez.

Kaynak dosyaları `scripts/teklif-guncelle.py` ve
`scripts/teklif_paket_legacy.py`. Ortam Python/kütüphane kurulumu isteği bu
belgenin kapsamı dışındadır; program akışını kullan.
