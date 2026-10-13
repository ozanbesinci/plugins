# Kullanıcı Kanıtı ve Değerlendirme Önceliği

Kullanıcının doğrudan verdiği bilgi **yetkili kullanıcı kanıtıdır**. Açık olgu, teyit, düzeltme ve karar, ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir. Bu kural eklentinin bütün becerilerinde uygulanır.

## Uygulama

- Bilgiyi özgün kullanıcı mesajı, tarih, firma, teklif, alan ve varsa soru kimliğiyle kaydet. Gerçek kullanıcı mesajına bağlanmış açık beyan, kullanıcı kaynaklı doğrulanmış girdidir; yalnız tedarikçi belgesinde yazmadığı için reddedilmez. Belgenin doğrulandığı iddiası bundan çıkarılmaz.
- Açık kullanıcı düzeltmesi değerlendirmede esas alınır. Eski belge değeri ve kanıtı korunur; raporda belge değeri ile kullanıcı teyidine dayalı geçerli değer ayrılır. Aynı kapsamda son açık düzeltme önceki beyanın yerini alır. Tek firmaya verilen cevap diğerlerine yayılmaz; açıkça bütün firmaları kapsayan cevap bütün belirtilen firmalara uygulanır.
- Miktar, para birimi, fiyat geçerliliği, ödeme, garanti, firma ve revizyon teyidi dahil her açık iş girdisi bu öncelikle ele alınır. Kullanıcı tarafından giderilen belge–beyan farkı aynı sorunun yeniden sorulmasına yol açmaz.
- “Bilinmiyor” gerçek ve tamamlanmış kullanıcı cevabıdır. İlgili değer bilinmiyor olarak kalır; tarih, sayı veya koşul uydurulmaz. Aynı soru sebepsiz tekrarlanmaz. Varsayım, soru veya alıntı doğrudan olgu beyanı sayılmaz.
- Değişen girdi bağlı hesap, bağımsız kontrol, karar, Excel/PDF ve QA'ya taşınır. Teknik olarak uygulanamayan kullanıcı cevabı **yazılım entegrasyonu eksikliği** olarak bildirilir; kullanıcı bilgisi geçersiz veya cevap verilmemiş gibi gösterilmez.

## Kanıt ve kontrol ayrımı

Kullanıcı beyanının önceliği, hesap sonucunun doğruluğu ve yazılım testinin sonucu ayrı kayıtlardır. Kullanıcı bilgisi geçerli girdi olur; aritmetik, kaynak bağı, şema, bütünlük ve çıktı okunurluğu mevcut kontrollerle doğrulanır. Çalıştırılmamış veya başarısız kontrol PASS olarak yazılmaz. Kullanıcı mesajı belge alıntısı, model tahmini veya bağımsız inceleme sonucu gibi gösterilmez.

Bu sözleşme değerlendirme girdisinin otoritesini belirler. Ham kaynak dosyaları ve önceki kabul kayıtları korunur; mevcut yürütme kodunda bir giriş türünün bulunmaması bu talimatın uygulandığını kanıtlamaz. Motor uyumu ayrıca doğrulanır.

## Sorunun yanıtına bağlı bekleme

Kritik bilgi, isteğe bağlı netleştirme, tercih veya onay için kullanıcıya soru sorulmadan önce sorunun kimliği/kapsamı ve cevabını bekleyen ajan/görevler kaydedilir. Yalnız bu cevaba bağlı ajanlar ve işler durur; soru sorulduğunda çalışan ve cevaba ihtiyaç duymayan ajanlar çalışmaya ve sonuçlarını kaydetmeye devam eder. Tüm ajanları topluca durdurma.

Bekleyen ajan yanıt gelene kadar hiçbir yeni araç/model çağrısı, belge okuma, hesaplama, dosya yazımı, rapor veya kontrol yapmaz; arka planda çalışmaz ve periyodik sorgulama yapmaz. Bekleme için süre sınırı yoktur. Sessizlik, seçili varsayılan veya sürenin dolması cevap/onay değildir. Kısmi veya ilgisiz yanıtta yalnız açık kalan alan sorulur ve ilgili bekleme korunur. Tek başına “devam” eksik iş bilgisini ya da onayı tamamlamaz. Önceden cevaplanan soru veya verilmiş izin aynı kapsamda sebepsiz tekrarlanmaz.

Ana ajan, alt ajan ve paralel görevlerin cevap bağımlılığını açıkça bağla. Cevaba bağlı bir ajan zaten çalışıyorsa, soruyu göstermeden önce o ajanı güvenli sınırda beklemeye al; bağımsız çalışan ajanları kesme. Sonradan başlatılacak bir iş aynı cevaba ihtiyaç duyuyorsa onu da beklet. Bir görev birden çok soruya bağlıysa gereken bütün yanıtlar tamamlanmalıdır. Bekleme kalıcıdır; yeniden başlatma veya süre geçmesi kaldırmaz. Yanıt yalnız ilgili soru kapsamını açar; veri değişmişse mevcut yeni-koşu/yeniden doğrulama yolunu kullan. Bu kural satınalma veya kurulum onayı üretmez.
