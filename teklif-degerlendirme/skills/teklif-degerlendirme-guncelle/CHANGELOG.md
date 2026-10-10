# Güncelleyici sürüm geçmişi

## v1.1.0 — 2026-09-26 — yerel canlı test adayı

- Ana skill v4 arşivinde zorunlu çalışma modülleri ve requirements.txt tamlığı doğrulanır; yalnız sürüm/metadata içeren eksik paket kurulamaz.
- Windows geçici dosya kilitlerinde ağaç değiştirme sınırlı yeniden denemeyle yapılır; kalıcı hatada geri alma davranışı korunur.
- Ana skill ve güncelleyici bağımsız sürümlenir; paket kütüphane kurucusu içermez.
- Canlı kabul ve GitHub yayını bu sürüm kaydıyla tamamlanmış sayılmaz.

## v1.0.0 — 2026-09-21

- Ana skill'den bağımsız sürüm hattı; eski ortak 3.0.1 etiketi tarihsel paket sürümüdür.
- Şema 2 bileşen sürümleri ve eski şema 1 kurulumdan kontrollü geçiş.
- İki yönetilen ağacın tam değişimi; başarıda eski dosyalar kaldırılır, hatada geri alınır.
- Yerel kurulum ile GitHub yayını ayrı; yayın öncesi kullanıcı onayı gerekir.
- Windows geçici klasörünün özel izinlerini kurulu skill'e taşımayan hazırlık alanı;
  açık geliştirmede doğrulanmış aynı sürüm yerel adayını değiştirme desteği.
