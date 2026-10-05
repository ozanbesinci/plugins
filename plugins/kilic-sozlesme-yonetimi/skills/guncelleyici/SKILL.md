---
name: guncelleyici
description: "Güncelleyici 2.3.0: Windows'ta Python ve araç sürümlerini tarar ve yetkili kurulumları uygular. Sözleşme becerileri için eksik Python, gerekli kütüphane, DuckDB ve PDF eklentisini otomatik hazırlar; doğrulama sonrası aynı talebe dönülür."
metadata:
  version: "2.3.0"
  engine: "guncelleyici-2.3.0"
---

# Güncelleyici

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Güncelleyici skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 2.3.0**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Bu plugin'in yayınlanmış 2.3.0 motoru [vendor/guncelleyici](../../vendor/guncelleyici/SKILL.md) içindedir. VERSION ve motor hash'leri denetlenir; ortak vault skill'i veya başka plugin kurulumu değiştirilmez.

## Sözleşme bağımlılıkları için otomatik giriş

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Kullanıcının plugin talimatı, yalnız eksik sözleşme bağımlılıklarının kurulması ve asıl isteğe dönülmesi için önceden yetki verir. Ajan `scripts/beceri-baslat.ps1` girişinde `-AutoInstallMissing` kullanır. Son kullanıcıya terminal/JSON formu açtırma.

Bu otomatik yol Güncelleyici 2.3.0'ın signed Python kurucusunu, indirme/doğrulama/kilit araçlarını ve signed DuckDB PDF yükleme/işlev testini kullanır. Gerekli paketler plugin'e özel yeni venv ortamına kurulur; mevcut ortak Python paketleri güncellenmez/düşürülmez. Node/pnpm/Power BI, eski skill temizliği ve istemci ayarı bu yolun kapsamı değildir. Python eksikse önce kullanıcı kapsamındaki signed Python kurulumu, sonra yeniden tarama yapılır. Çalışan ortak Python/Node işi varsa Python kurulumu durur; süreçler kapatılmaz.

Kurulum/LOAD/işlev testi başarısızsa, yarım işlem kaydı/kilit varsa veya kaynak/istek değişmişse asıl beceri devam etmez. Hata açıkça raporlanır; kör tekrar yapılmaz. Yerel Windows shell yoksa kurulum yapıldığı söylenmez. Bu yol model çıktısından şirket yetkisi veya bakım onayı çıkarmak için kullanılmaz.

## Doğrudan güncelleme isteği

Kullanıcı Güncelleyici'yi doğrudan çağırırsa [orijinal 2.3.0 talimatını](../../vendor/guncelleyici/SKILL.md) oku ve motorun `scripts/sohbet.ps1` scan/apply/verify yolunu kullan. Genel güncelleme/onarım için orijinal açık plan ve bakım onayı kuralları geçerlidir. Sözleşme eksiklerini otomatik hazırlama yetkisini tüm bilgisayar programlarını güncelleme yetkisi sayma.

Motor BUILD.json kabul sınırları korunur: kaynak yayını tam personel/üretim kabulü değildir. Ayrıntılar [runtime entegrasyonunda](../../references/runtime-integration.md).
