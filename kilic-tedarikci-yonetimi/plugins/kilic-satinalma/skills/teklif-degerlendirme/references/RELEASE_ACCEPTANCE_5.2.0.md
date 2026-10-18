# 5.2.0 kabul durumu — 18 Ekim 2026

Bu sürüm 1.4.0 eklentisinin 5.2.0 kararlı beceri sürümüdür. Son açık indirme kontrolü, kullanıcının tarayıcıdan kaydetme teyidi ve normal adlı ZIP dosyasının bağımsız bayt kontrolüyle kapandı. Dev.12 üzerinde tamamlanan teknik kabulün üstüne sürüm bilgisi ve resmî Work/Library dosya teslim talimatı eklenmiştir. Çalıştırılabilir kod, şema, hesap profili, kilitler ve kurucu değiştirilmemiştir. Önceki tam testleri yeni kaynak hashinde tekrar çalışmış gibi gösterme; kabul kaydı içerik farkını bağlar.

Dev.12 kaynak kimliği: `0fc5eb44f6760d1cbcd5c6ddaa766d76323f8f4d104c3fd18d3564d8666b399e`.

| Kontrol | Gerçek sonuç |
|---|---|
| SQLite / gerçek DuckDB | 669 + 669 test; hata/atlama yok |
| Microsoft Excel referansı | Aynı kaynakla 16.136 formül eşliği |
| Temiz kullanıcı kurulumu | Python olmayan, yönetici olmayan Windows Sandbox hesabında 663,82 saniye PASS |
| Gerçek Work yeni analiz | VERIFIED; 39 Excel sayfası, 2288 otomatik hesaplanan formül, 12 PDF sayfası |
| Yeni Work çıktısının Excel referansı | Ayrı kopyada Excel16.0 ile 2288/2288 eşliği; özgün çıktı değişmedi |
| Aynı sohbet web devamı | Aynı runtime/snapshot/revizyon; 58 güncel + 129 eski kapalı dosya değişmedi |
| Gerçek çıktı erişimi / görsel | Normal kullanıcı özgün dosyaları doğrudan okudu; PDF12 sayfa görsel kontrolü geçti |
| Library web önizleme | Excel ve PDF açıldı; Windows sandbox bağlantısı yerine resmî Library kullanıldı |
| Library tekil PDF | 12 sayfa metin/görüntü aynı, fakat dosyaya ek veri nedeniyle SHA farklı; özgün teslim için ZIP gerekir |
| Tarayıcı normal dosya indirme tamamlanması | PASS; kullanıcı tarayıcıdan kaydettiğini teyit etti. Masaüstündeki normal adlı ZIP 179.860 bayt; arşiv ve üç üyenin SHA256 değerleri özgün dosyalarla aynı |

Gerçek Work hızlı profilindeki formal görsel görev uygulanmadı; dış görsel kontrol onun makbuzu değildir. Host görev token bilgisi sunulmadı, NULL/host_unavailable korundu. PDF üretim anındaki QA metni ile son validate manifesti farklı zamana aittir; kapanmış PDF değiştirilmedi.

Yerel analiz için Windows bilgisayarı ve bağlı ChatGPT masaüstü uygulaması açık olmalıdır. Aynı uygun görevin web devamı doğrulandı; her yeni web sohbetinin kendiliğinden yerel erişimi olduğu iddia edilmez. Fiziksel kesinti kanıtı önceki koşuya aittir; aynı sohbetten yeni mesajla güvenli dönüş gözlendi, eski komutun kendiliğinden devam ettiği iddia edilmez.

İlk teknik kabul sırasında şirket genelindeki eklenti 1.3.3 olarak korunmuştu. 1.4.0 GitHub/Business dağıtımı aynı kabul edilmiş kodu kullanır; yayın sonucu dağıtım kaydında ayrıca doğrulanır. Ayrıntılı kaynaklar geliştirme çalışma alanındaki `outputs/teklif-140-20261017/work-calc-v10/dev12/` ve `rc1/` kabul kayıtlarıdır.

18 Ekim 2026 indirme kanıtı: `Teklif_Raporlari.zip`, SHA256 `c8209d5e9d39556bafbde2a8a09e8a82d13265585c6f7c4254b1ca20cfb2f162`. Tarayıcı olayını ajan doğrudan görmedi; kullanıcı teyidi ile gerçek kaydedilmiş dosya ayrı kanıtlardır. Kararlı geçiş yalnız sürüm bilgileri ve kabul belgelerini değiştirir; hesap kodu, yapılandırma ve kurucu RC1/dev.12 ile aynıdır.
