# Windows kaynak nesnesi sınırı

İzinli yol kontrolü symlink/junction/reparse ve hardlink sayısı1 dışındaki normal dosyaları reddeder. Kaynak/hash okumalarında CreateFileW salt-okunur, yalnız FILE_SHARE_READ ve OPEN_REPARSE_POINT ile açılır. Açılan handle'da gerçek son yol, dosya/dizin/reparse türü ve link sayısı okumadan önce/sonra kontrol edilir; doğrulanamayan nesne kapalı kalır. Okuma sırasında başka yazma/silme/rename isteği Windows tarafından reddedilir. Kaynak dosyasını değiştirme, ACL genişletme veya yönetici hesabı kullanma yok.

Bu kontrol aynı Windows kullanıcısının genel yetkisini kaldırmaz. Ayrı kurumsal kimlik, ACL/saklama onayı ve host izinli erişim testi NOT_RUN; CONS-022/024 bütünüyle kapanmış değildir. Kullanıcı veya başka uygulama yazma handle'ı tutuyorsa KAYNAK_MESGUL ret sonucu beklenir; dosya kapatılmadan güvenli okuma iddia edilmez. Varsayılan akış birincil kaynağı değiştirmeden snapshot'a alır, son hash/revizyon kontrolünü korur.

API anlamı: [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew). Native testler normal Unicode kaynak, hardlink, junction, handle açıkken yazma/rename reddi ve byte limitini ayrı sınar.
