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
