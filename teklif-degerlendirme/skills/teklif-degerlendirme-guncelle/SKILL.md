---
name: teklif-degerlendirme-guncelle
description: Teklif değerlendirme paketinin kararlı sürümünü kontrol eder; açık kurulum/güncelleme isteğinde eski yönetilen sürümü doğrulanmış yeni paketle tamamen değiştirir. Ana skill ve güncelleyicinin bağımsız sürümlerini izler. Salt sürüm kontrolünde dosya değiştirmez.
metadata:
  version: "1.1.0"
---

# Teklif Değerlendirme Güncelle

Resmî depo `ozanbesinci/teklif-degerlendirme`. İki skill birlikte dağıtılır fakat
sürümleri bağımsızdır. Güncel güncelleyici sürümü **v1.1.0**; bağımsız hat v1.0.0 ile başladı. Eski
3.0.1 etiketi ortak paket sürümüydü. İşlem deterministiktir; alt ajan/model gerekmez.

## Yetki ve akış

1. Sürüm kontrolü → yalnız `check`; kur/güncelle → iki yönetilen skill'i yenileme
   yetkisi. Aynı güncellemenin adımlarında yeniden onay isteme.
2. Fiziksel ortak skill kökünü çöz; keşif junction'larını değiştirme.
3. `python <bu-skill>/scripts/guncelle.py check --root "<fiziksel-skills>"`.
   Ağ/kimlik hatası “güncel” değildir; yayımlanmamış sürümü var sayma.
4. Açık güncellemede `python <bu-skill>/scripts/guncelle.py update --root
   "<fiziksel-skills>"`. Yeni paket indirilip doğrulanır; eski iki skill ağacı
   **tamamen** yenileriyle değiştirilir. Dosyaları üst üste ekleyip eski scriptleri bırakma.
5. `verify --root "<fiziksel-skills>"` ile dosyaları ve iki ayrı skill sürümünü
   doğrula. Başarıda eski ağaçlar silinir; kaldırıldığını ve yeni sürümleri bildir.

Yeni paket doğrulanmadan eski sürümü silme. Geçişte eski ağaçlar yalnız geri alma
için geçici tutulur; başarılı kurulumda eski sürüm kopyası kalmaz. Yakalanan hatada
önceki sürüm geri konur. Güç kesintisinde kalan işlem günlüğü/kilidi incelemeden silme.

## İlk kurulum ve yerel geliştirme

Resmî Release'teki `teklif-degerlendirme-vX.Y.Z.zip` ve `.zip.sha256` kullanılır.
X.Y.Z paket etiketidir; manifestin `skill_versions` alanı bağımsız sürümleri taşır.
Yalnız güncelleyici değişirse paket etiketi ilerletilebilir; ana skill zorla artırılmaz.

```text
python guncelle.py install --root "<skills>" --archive "<paket.zip>" --sha256 "<64-karakter-hash>"
python guncelle.py verify --root "<skills>"
```

Açık kaynak geliştirme isteğinde test edilmiş yerel aday paket aynı `install`
yoluyla kurulabilir; henüz yayımlanmamış sürümü GitHub'dan çekmeye çalışma.
Yerel kurulum ve çevrimiçi yayın ayrı durumlardır.

Henüz yayımlanmamış aynı sürüm yerel adayını açık geliştirme kapsamında yeniden
kurmak gerekirse `install --replace-local` kullanılabilir. Önceki ağaç yine tam
doğrulanır; paket ve iki bileşen sürümü aynı olmalıdır. Normal `update` bu seçeneği
kullanmaz; yayımlanmış sürüm içeriği değiştirilmez, yeni sürüm numarası çıkarılır.

Yönetimsiz kurulum otomatik silinmez. Paketle tam aynı kaynak kurulumunda
`register --root ... --archive ... --sha256 ...` yalnız envanteri kaydeder.
Yerel değişikliği `register` ile aşma. Şema 1'in eş-sürümlü paketinden şema 2'ye
bir kerelik bağımsız numaralandırma geçişi desteklenir; sonraki bileşenler düşürülemez.

## Güvenlik ve yayın sınırı

- Yalnız resmî HTTPS Release; ZIP/hash/dosya manifesti doğrulanır. Hash yayıncı imzası değildir.
- Teklif, fiyat, rapor, anahtar, sohbet ve hafıza dışarı gönderilmez.
- Yalnız iki fiziksel skill ağacı yönetilir. Yerel değişiklik/bilinmeyen dosya veya
  bağlantı üzerine yazılmaz; başka skill ve kullanıcı dosyası silinmez.
- Eski global analiz kilidi, güncelleme kilidi veya yarım işlemde dur. Yeni analiz
  kendi değişmez snapshot'ında sürer; güncelleme sırasında yeni snapshot hazırlanmaz.
- ZIP yol kaçışı, bağlantı, çakışan ad, aşırı boyut ve sürüm tutarsızlığı reddedilir.
- Ana skill v4 paketinde zorunlu çalışma modülleri ve requirements.txt eksik/boşsa kurulum reddedilir; yalnız metadata taşıyan paket eski çalışan ağacın yerine geçemez.
- Windows geçici dosya kilidinde ağaç değiştirme sınırlı aralıklarla yeniden denenir; kalıcı hatada önceki sürüme dönülür. Paket kütüphane veya Python kurulumu yapmaz.
- Sandbox/onay atlama, global ayar değişikliği, otomatik periyodik işlem ve indirilmiş
  kurulum kodunu çalıştırma yoktur.
- **GitHub yayını ayrı yetkidir:** geliştirme/yerel kurulum bittikten sonra push,
  tag, Release veya yükleme öncesinde kullanıcı onayı al ve bekle. Model
  değiştireceğini söylediyse o aşamada dur; “güncelle” talebini yayın onayı sayma.

Paketleme: `../teklif-degerlendirme/KURULUM.md`. Yeni skill sonraki turda keşfedilir.
