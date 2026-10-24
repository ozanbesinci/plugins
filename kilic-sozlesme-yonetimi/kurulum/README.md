# Ayrı Windows kurulumu

Bu klasör yalnız sözleşme eklentisinin kurucusunu üretir. Work 0.1.2 ajanı eksik ortamda tek EXE'yi otomatik indirip doğrular ve çalıştırır; kullanıcı terminal, Python veya pip kullanmaz. Kurucu asInvoker ile kullanıcı alanına yazar. Mevcut Python, paketler, PATH, Windows ilkeleri ve hizmetler değiştirilmez.

Paket CPython 3.14.8 embedded x64, requirements-win-cp314.lock içindeki 13 wheel ve sabit Microsoft VC++ DLL'lerini içerir. İndirme yalnız derleme sırasında resmi adreslerden, sabit SHA-256 kontrolüyle yapılır. Kullanıcı kurulumu çevrimdışıdır. Dosya içindeki lisans/NOTICE metinleri taşınır. Microsoft yeniden dağıtım koşulları ve kurumsal dağıtım kabulü yayın sorumlusunun ayrı incelemesidir.

Geliştirici Windows x64 ve .NET Framework csc.exe ile build_installer.py --output <proje-dışı-yeni-klasör> çalıştırır. --refresh-only yalnız ürün bootstrap manifestini yeniler. Klasör önceki derlemenin üzerine yazılmaz. İndirilen doğrulanmış dosyalar üst klasörde download-cache altında tekrar kullanılabilir.

Çıktılar KilicSozlesmeKurulum-0.1.1.exe ve BUILD.json'dur. 0.1.1 kararlı sürümün kurucusu **imzasızdır**. İmza sertifikası varmış gibi davranılmaz; SmartScreen veya şirket uygulama politikası atlatılmaz. İmzalama ve temiz standart kullanıcı kabulü tamamlanmadan tüm Business üyeleri için dağıtıma hazır denmez. Work gerçek görev kabulü ayrıca kaydedilir.

Kurucu yeni ortamı benzersiz klasöre açar, dört gerçek okuyucuyu sınar ve ancak başarıdan sonra sabit JSON kaydını atomik değiştirir. Eşzamanlı kurulum dosya kilidiyle engellenir. Tekrar çalıştırma sağlam ortamı kullanır; hatalı yeni ortam eski çalışma kaydını ezmez. Eski ortamlar ve günlükler otomatik silinmez.

Önkoşul Windows 10/11 x64 ve .NET Framework 4.x; ARM64 kapsam dışıdır. `--quiet`, Work 0.1.2 otomatik ilk kurulumunda ve sentetik testlerde kullanılır; aynı gerçek kurulum/doğrulama yolunu çalıştırır, yalnız etkileşimli bilgi kutularını göstermez. Ajan `scripts/ortam-hazirla.ps1` ile sabit yayımlanmış 0.1.1 EXE'sini indirip hash/boyut kontrolünden sonra çalıştırır ve native READY sonucunu doğrular. Geliştirme testleri izole USERPROFILE klasörü kullanır, gerçek kullanıcının sözleşme kaydına yazmaz.
