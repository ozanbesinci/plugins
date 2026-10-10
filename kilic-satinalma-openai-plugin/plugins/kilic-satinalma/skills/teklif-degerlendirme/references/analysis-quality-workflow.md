# Kaynaktan karara kalite yöntemi

## Öncelikli kullanıcı kanıtı

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir. [Ortak kullanıcı kanıtı sözleşmesi](../../../USER-EVIDENCE-POLICY.md) uygulanır. Kaynak belge ile kullanıcı beyanı ayrı tutulur; kullanıcı cevabını uygulayamayan kod, teknik entegrasyon engeli olarak bildirilir.


Bu yöntem mevcut kanonik kayıtları, hesap motorunu ve kalite kapılarını kullanır. Görevinle ilgili bölümü oku; bütün bölümleri her model paketine ekleme. Bounded alt görev yalnız izinli context/schema/görselleri görür. Buradaki kontrol başlıkları yeni JSON alanı veya yeni görev tipi değildir; sonucu mevcut şemanın izinli alanlarına, koordinatörün inceleme notunu ise iş kaydına yaz. Kapalı şemaya kontrol listesi ekleme.

## Kaynak ve soru

Belge/Kaynak ile Kapsam/Ticari bölümleri bu yöntemi kaynaklar çeliştiğinde veya kararı etkileyen bilgi eksik olduğunda kullanır.

1. Önce kararın konusu ve karşılaştırılan mal/hizmet kapsamını mevcut talep ve kullanıcı yanıtından belirle. Bilinen firma, miktar, profil ve para birimini yeniden sorma. Belgeye bağlı olgu, kullanıcı iş beyanı ve inceleme yorumu ayrı kalır.
2. Çelişen alanı belge/teklif/revizyon + locator + değer + kanıt durumu ile yan yana tut. Kaynağın o alan için yetkisini, kapsadığı teklifi ve açık teyit/revizyon bağını incele. Yeni dosya tarihi, daha büyük REVİZE numarası veya aynı isim tek başına yetki değildir. Teslimi açıklayan yazışmayı fiyatı değiştirme yetkisi sayma; kullanıcının firma klasörü kuralı revizyon seçimi değildir.
3. Açık yetki ilişkisiyle çözülebilen farkı kaynak atfıyla çöz. İlişki belirsizse iki kaydı koru; birini silip temiz toplam üretme. Şartname yokluğu ile okunmamış/ulaşılamayan şartname farklıdır: mevcut dosyalarda bulamadığını, hangi incelemenin yapılmadığını belirt.
4. Önce yalnız mevcut paket ve önceki kayıt kapsamındaki kanıtı kontrol et. Sonucu değiştiren açık için ana kanala kısa soru hazırla: hangi firma/dosya, hangi alan, hangi karar/hesap bekliyor? Aynı aşamanın ilişkili eksiklerini bir blokta sor. Yanıt bir firmaya/teklife verilmişse diğerine uygulama. Varsayılan seçenek, sessizlik veya “devam” cevabı kritik iş girdisi değildir.
5. Eksik finans yöntemini/oranı, kuru, vergiyi, vade başlangıcını veya geçerli revizyonu tahmin etme. Bağımlı hesap/karar bekler; bağımsız envanter sürdürülebilir. Yanıt teknik kanıt teyidinin veya QA'nın yerine geçmez. Yeni yanıt pinned context'e yazılmaz; mevcut uyumluluk ve yeniden doğrulama yolu kullanılır.

## Analiz birimi ve üyelik

Belge/Kaynak ve Maliyet, kaynakları birleştirmeden veya toplulaştırmadan önce; Bağımsız Kontrol, beklenen sonucu ayrı kurarken uygular.

- Önce bir satırın neyi temsil ettiğini belirle: belge, teklif revizyonu, teklif kalemi, kapsam farkı veya uygunluk değerlendirmesi. Firma adı tek başına teklif/kalem anahtarı değildir. Aynı dosyanın kopyası, farklı revizyon ve bağımsız alternatif ayrı ilişkilerdir; metin benzerliğiyle otomatik birleştirme yapma.
- Beklenen kimlikleri kaynak ve kanonik kapsamdan kur. JOIN/filtre/hesap öncesi-sonrası kimlik kümesi, kayıp/fazla kimlik ve bunların kaynak bağını karşılaştır. Adet ve toplam eşitliği doğru üyeliği kanıtlamaz. Aynı anahtarda iki kayıt varsa tekilleştirmeden önce nedenini ve doğru grain'i çöz; ham kaydı silme.
- `NULL`, boş metin, okunamayan değer, açık sıfır, kapsam dışı ve çelişki aynı değildir. Sıfır kendi kaynak kanıtıyla geçerlidir. Eksik kalem/tutar toplamdan sessizce düşmez; ilgili hesap tamamlanmamış kalır. Birim fiyat, satır toplamı ve genel toplamı birlikte toplayıp iki kez sayma.
- Alanlar arası uyumu kontrol et: miktar/birim, para birimi, fiyat tabanı, KDV, indirim, vade başlangıcı ve ortak değerleme tarihi. Kapsama dahil bedel yeniden eklenmez; bağımsız ilave yalnız kendi tutar/para/kanıtıyla taşınır.
- Her hesap için üyeliği ayrıca kur: fiyat karşılaştırması uygun ve karşılaştırılabilir maliyeti tam teklifleri; ağırlıklı kriter hesabı uygun ve gerekli kriterleri tam teklifleri kullanır. Maliyeti eksik fakat kriterleri tam bir teklifin iki hesapta farklı üyeliği meşru olabilir. Tek ortak filtreyle farkı silme.

Mevcut kontroller `grain_integrity`, `data_quality`, `comparison_contract` ve kapsam/otorite kapılarıdır. Bir bulguyu “kalite düşük” diye özetleme; kayıp/fazla kimlik, kaynak kanıtı, etkilenen hesap ve karar etkisini göster. Teknik arızayı kullanıcı ticari cevabıyla kapatma.

## Bağımsız kontrol ve iz

Bağımsız Kontrol, ana hesabı onaylamak için aşağıdaki sırayı kullanır. Ana sonuç yalnız karşılaştırma hedefidir; beklenen kimlik/değer listesi ana hesabın eleme veya sonuç tablosundan türetilmez.

1. Güncel kaynak/fact/evidence ve şartlardan üyeliği ayrı belirle. Sonucun doğru tutarı yanlış teklife/kaleme bağlamadığını da kontrol et. Aynı toplamı veren farklı üyeler PASS değildir.
2. Kritik hesapları mevcut bağımsız hesap yoluyla doğrula. Ana hesap helper'ını tekrar çağırmak veya iki modelin aynı rakamı söylemesi bağımsız hesap değildir. Ortalama/ağırlıklı puanın pay, payda, ağırlık, para birimi ve karşılaştırma tabanı doğru olmalı. Kurallarda tanımlı hassasiyet ve yuvarlama sınırları dışında yaklaşık eşleşme kabul edilmez.
3. Önemli sonuç için izi iki yönde incele: kaynak belge/locator → kanonik fact/kalem → hesap kimliği ve girdileri → reviewed snapshot → çıktı bağlaması/Excel hücresi/PDF sayfası. Çıktı henüz yoksa kalan adımı yapılmış sayma. Aşağıdaki inceleme notu mevcut kanıt ve QA kayıtlarına işaret eder; ikinci hesap motoru veya DB değildir.

| Sonuç / kimlik | Beklenen ve dayanağı | Gözlenen | Kontrol sonucu / açık nokta |
| --- | --- | --- | --- |
| İlgili kritik tutar/üyelik | Kaynak ve bağımsız hesap referansı | Hesap/çıktı referansı | Uyuşuyor, fark var veya henüz doğrulanmadı |

4. Örnek kayıt izi, bütün kritik kontrollerin yerine geçmez. Uygulanabilir kritik birimler mevcut coverage sözleşmesiyle doğrulanır; incelenmeyen birim açık kalır. Kaynak brüt tutarı tutarken PV/TCO, kapsam farkı veya fiyat kümesi yanlış olabilir; her iddiayı kendi tabanında sınama.
5. Bulguları satınalma kararına etkisine göre sırala. Sayı/üyelik/kaynak/karar güvenilirliğini bozan bulgu kapıyı durdurur. Kozmetik öneri kritik arıza gibi sunulmaz; zorunlu mevcut görsel/coverage kapısı da “kozmetik” denerek atlanmaz. Çalıştırılmayan kontrolü PASS yazma.

## Karar ve görünür çıktı

Karar/Rapor, yalnız mevcut kanonik paket ve snapshot izinleri içinde uygular. Bu bölüm ham belgeleri canonical-only modele verme izni değildir; kaynak izinin mevcut kapılarda doğrulandığına ilişkin kayıtları kullanır.

- Önce kararı taşıyan iddiaları belirle: seçilen firma/kapsam, bedel ve para, vade, ilave/eksik kapsam, temel risk ve önerilen sonraki adım. Her sayısal iddia kendi kaynak/hesap/claim bağına dayanır. Raporda iki fiyat görünmesi yeni bir tasarruf hesabını kendiliğinden kanıtlamaz.
- Kanıt tamken tek gerekçeli satınalma eylemi öner. Rapor öncesi durum ile nihai teslim durumunu ayır: çıktı/QA/validate yapılmadan VERIFIED yok. Yanıt bekleyen kritik iş sorusunu dipnota taşıyıp karar raporunu bitirme. Teknik BLOCKED'ı satınalma tercihiyle aşma.
- Excel/PDF/özet aynı reviewed snapshot'a dayanır. Toplam doğru olsa bile para birimi, ölçü birimi, net/brüt/PV başlığı, geçerli teklif kimliği veya koşul yanlışsa çıktı yanıltıcıdır. Caveat ve belirsizlik, sınırladığı iddiaya görünür yakınlıkta olmalı; yalnız uzak bir kanıt sekmesinde bulunması ana öneriyi kesinleştirmez.
- Mekanik kontrollerden sonra gereken son renderları incele: kesilen tutar/sütun, satır ile firma eşleşmesi, devam sayfası başlıkları, okunamayan sayı, gizlenen koşul/dipnot, renk ve lejantın karar durumuyla uyumu. Metin çıkarımı veya dosyanın açılması görsel QA değildir. Profilin gerektirdiği sayfa/sekme kapsamını daraltma.
- Kaynak/yanıt/snapshot ya da çıktı değişmişse ilgili bağımlılığı yeniden doğrula. Sadece aynı dosya adı, aynı toplam veya değişmemiş bir sayfa görüntüsü eski genel QA onayını taşımaz; mevcut hash/parent/coverage sözleşmesi belirleyicidir. Son validate_run gerçek sonucu teslim statüsünü belirler.

## Kaynak ve kapsam

7 Ekim 2026’da incelenen özgün desenler, bu projenin Türkçe satınalma kurallarına uyarlanmıştır. Dış beceriler kurulmaz veya çalışma sırasında yüklenmez. Kullanıcının kritik belirsizlikte soru/cevap bekleme şartı ve mevcut kalite kapıları, genel örneklerin varsayım/koşullu paylaşım önerileriyle gevşetilmez. Erken kullanıcı bekleme motorunun mevcut OPEN sınırı ana SKILL'de geçerlidir.

- [skill-creator](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.system/skill-creator/SKILL.md): ihtiyaçta ayrıntı yükleme ve dar görev tanımı.
- [gather-business-context](https://github.com/openai/plugins/blob/5fd93af4cd0c623e020d0cc7e9ce178b4ac1f70f/plugins/data-analytics/skills/gather-business-context/SKILL.md): yetki/kapsam/çelişki ve kaynaklı karar bağlamı.
- [analyze-data-quality](https://github.com/openai/plugins/blob/5fd93af4cd0c623e020d0cc7e9ce178b4ac1f70f/plugins/data-analytics/skills/analyze-data-quality/SKILL.md): analiz birimi, anahtar, eksik/mükerrer değer ve ilişki kontrolleri.
- [validate-data](https://github.com/openai/plugins/blob/5fd93af4cd0c623e020d0cc7e9ce178b4ac1f70f/plugins/data-analytics/skills/validate-data/SKILL.md): ayrı yeniden hesap, kayıt izi, iddia ve görsel kontrolü.
- [pdf](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/pdf/SKILL.md): nihai render üzerinden görsel inceleme.

Plugin manifesti/katalog düzeni mevcut paketleme denetiminde korunur; [plugin-creator](https://github.com/openai/plugins/blob/5fd93af4cd0c623e020d0cc7e9ce178b4ac1f70f/.agents/skills/plugin-creator/SKILL.md) bu geliştirme için paketleme referansıdır, teklif çalıştırma adımı değildir.
