# Teklif Değerlendirme

Satınalma tekliflerini kapsam, maliyet, ticari koşul ve risk açısından karşılaştırır.

## Kararlı sürüm: v4.0.5

Ana skill **4.0.5**, kullanıcının açık kararıyla kararlı dağıtıma alınmıştır.
[ZIP ve SHA-256 doğrulama dosyası](https://github.com/ozanbesinci/teklif-degerlendirme/releases/tag/v4.0.5)
GitHub Release üzerinden dağıtılır. Uçtan uca canlı analiz kabulü ayrıca izlenir.

### Son değişiklikler

- Ana koordinatör ve bütün alt ajanlar **GPT-6.1 / High** kullanır.
- Analizin ilk adımı aktif oturumun gerçek model ve efor kontrolüdür. Seçim yanlışsa kullanıcıdan düzeltmesi istenir; her yeni yanıtında kontrol ve uyarı tekrarlanır. Doğrulandıktan sonra analiz devam eder.
- Teklif analizi başlangıcındaki otomatik güncelleyici çağrısı kaldırılmıştır; güncelleyici ayrıca kullanıcı tarafından çalıştırılabilir.
- Önceki 4.0.2 sürümündeki Excel ve PDF sunum düzeltmeleri korunur.

## Kurulum yapısı

Ana skill `skills/teklif-degerlendirme/` altındadır. Birleşik güncelleyici ayrı
[ozanbesinci/guncelleyici](https://github.com/ozanbesinci/guncelleyici) deposunda
yönetilir; ana skill paketi onu içermez. Depodaki eski
`teklif-degerlendirme-guncelle` ağacı tarihsel v3 kaynaklarıdır; v4 kurulumunda
ayrıca kurulmaz.

Paket manifesti şema 3'tür ve yalnız ana skill'in izinli kaynaklarını kapsar.
Kaynak depo ZIP'i doğrulanmış kurulum paketi yerine kullanılamaz.
Birleşik güncelleyici normal kullanımda en son kararlı Release paketini denetler.

## Doğrulama

Bu sürümün model, oturum ve koşu denetimlerini kapsayan **50 Python testi** geçti.
Dağıtım paketinin manifesti, dosya özetleri ve sürüm uyumu doğrulandı.
Yerel Work içinden gerçek teklif analizi kabulü ayrıca izlenir.

- [Kurulum ve çalışma kapsamı](skills/teklif-degerlendirme/KURULUM.md)
- [Sürüm geçmişi](skills/teklif-degerlendirme/CHANGELOG.md)
- [Kararlı sürümler](https://github.com/ozanbesinci/teklif-degerlendirme/releases)

## Veri sınırı

Bu depo yalnız skill kaynaklarını içerir. Gerçek teklifler, şirket belgeleri,
analiz çıktıları, sohbet/hafıza dosyaları ve kimlik bilgileri yayımlanmaz.

## Lisans

Henüz açık kaynak lisansı tanımlanmamıştır. Kaynakların görünür olması,
yeniden dağıtım veya türev eser izni verildiği anlamına gelmez.
