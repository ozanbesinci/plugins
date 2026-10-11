# 5.1.1 — 2026-10-12 (kararlı yama adayı)

- Teyitli elemelerden sonra kalan uygun tekliflerin benzersiz tedarikçileri sayılır. İki aktif firmadan biri elendiğinde tek tedarikçi durumu XLSX ve PDF'de doğru gösterilir.
- Aynı uygun firmanın iki alternatifi rekabetçi iki firma sayılmaz; teyitsiz eleme uygun kümeyi daraltmaz. Kaynak teklif/firma envanteri, eleme kayıtları, NO_DECISION ve boş sıralama korunur.
- Üç yeni regresyon, üç profilde iki çıktı ve iki gerçek motorla sınanır. Önceki 530 PASS yeni kaynak sonucu sayılmaz; son tam koşu ve yayın kabulü ayrı sürümlü kanıtlardadır.

# 5.1.0 — 2026-10-11 (kararlı aday)

- Her profilde tek formüllü XLSX ve çok sayfalı PDF; iş karar engelinde güvenli ön rapor ve kaynak bütünlüğü bildirimleri.
- Immutable resmî/ön rapor çifti; dosya doğrulaması ve tek metadata transaction; fiziksel arızada bağımsız PDF/dizin yolu.
- Kaynak bağlı şartname durum matrisi ve bağımsız sayımlar.
- Konum/ifade bağlı güvenli formüller; mavi kullanıcı girdileriyle yeni ön rapor; kaynak/resmî karar/kapalı koşu korunumu.
- Çok adımlı ödeme, KDV geri kazanımı, sabit veya yıl bazlı yaşam gideri/kalıntı NBD; bilinmeyen girdiler korunur.
- 48 tekil maliyetli bağımsız tarihli nakit defteri: ayrı tür/para/tarih/projekte kur ve kapsam; spot kur/vadeli nakit karışımı ve çift kimlik reddi.
- Python/Excel ortak Gregoryen tarih doğrulaması; yerel DATEVALUE yorumundan bağımsız hesap, gerçek 1900 gün farkı.
- Gerçek motor kimliği ve taze sayaçlı ayrı test koşuları; Windows Unicode yol çıktısı; Excel izole kopya/süre sınırı.
- Yeni PDF bağımlılıkları gereksinimlere eklendi; başlıkların ilk içerikle aynı sayfada kalması düzeltildi. Önceki test sayıları bu adayın kabulü değildir; sürümlü gerçek kanıt release varlıklarındadır.

# 5.0.29 — 2026-10-09 (kararlı)

- Ana beceri ve beş alt beceri aynı sürüme alınmıştır. 5.0.29-dev.10 kabul adayının çalışma kodu ve konfigürasyonu bayt bayt korunmuştur.
- Kullanıcı teyidi/düzeltmesi, bilinmiyor yanıtı, çok alanlı soru kapanışı ve satır bazlı miktar/maliyet girdisi değerlendirme, karar ve son kontrol kapılarında birlikte uygulanır. Özgün kaynak gözlemleri ayrı korunur.
- Kanıt/soru kimlik kapsamı, firma–hesap kimliği, dar soru kanıtı ve uygulanan miktar düzeltmesi tutarlı bağlanır; gerçek ret geçmişi korunur.
- Excel/PDF geçerli ödeme ve geçerlilik bilgisini aynı hesap dayanağından gösterir. Yalnız maliyet puanı varsa hesaplanmamış toplam puan açıkça belirtilir.
- Üç gerçek XLSX/33satır, gerçek Excel/PDF95sayfa ve mevcut küçük soru–cevap kabulü VERIFIED. SQLite/nativeDuckDB399/399PASS. Güncelleyici2.3.0 korunmuştur.

## Geçmiş geliştirme kayıtları

Aşağıdaki kayıtlar ilgili tarihli geliştirme adımının kapsamını açıklar; güncel kararlı kabul sonucu yukarıdaki kayıttır.

# 5.0.29-dev.10 — 2026-10-09 (yerel talimat adayı)

- Açık kullanıcı beyanı ilgili değerlendirme girdisinde öncelikli kanıt olarak ana ve beş alt beceriye, ortak sözleşmelere ve paket politikasına işlendi. Özgün belge ve teknik kontrol sonuçları ayrı korunur.
- Python çalışma kodu değiştirilmedi; tarih girdisi ve karar kapısı entegrasyonları açık kalır. Bu kayıt gerçek kabul veya yayın onayı değildir.

# 5.0.26-dev.1 — 2026-10-08 (yerel geliştirme adayı)

- Ayrı model görevlerinin aynı yerel kanıt, kapsam, soru, gereksinim veya istisna etiketini kullanması önceki belgenin kaydını değiştirmez. Çakışan kimlik görev kapsamına bağlanır; olgu ve kapsamın kanıt referansları aynı kimliğe yönlendirilir. Kaynak ve sayı doğrulama kapıları korunur.

# 5.0.25-dev.15 — 2026-10-08 (yerel geliştirme adayı)

- Kanıt alıntısındaki yan yana tablo sayılarını ayrı ayrıştır; miktar ve fiyat doğrulaması bitişik hücreleri yanlış birleştirmez. Kritik sayı için kaynak kanıtı zorunluluğu korunur.

# 5.0.25-dev.14 — 2026-10-08 (yerel geliştirme adayı)

- Teklif alanı görev paketindeki izinli alan listesi, o görevde gerçekten istenen alanlarla sınırlandı. Görevde olmayan KDV alanı veya başka bir alan modele izinli gibi gösterilmez.
- Görev sonucu tam alan kapsamı açık yazıldı; fazladan alanlar kabul veritabanına geçmez ve gerçek ret makbuzu korunur.

# 5.0.25-dev.12 — 2026-10-08 (yerel geliştirme adayı)

- Görsel kaynak yolları şartname çıkarımı, teklif alanı çıkarımı, uygunluk ve istisna görevlerine de eklenir; taranmış kaynak metin yok diye görünmez kalmaz.
- Kaynak görselinin hash'i görev paketinde bulunur; yalnız kaydı listelenen sayfalar açılır.

# 5.0.25-dev.11 — 2026-10-08 (yerel geliştirme adayı)

- ZIP kapsayıcısı ayrı teklif sayılamaz; açılan üyeler bağımsız belge olarak kalır ve aynı baytlı tekrarlar pasif izlenir.
- Arşiv veya e-posta eki çıkarma hatası sessizce geçilmez; koşu hata ile durur. Windows kısa/uzun geçici yol eşitliği düzeltilmiştir.

# 5.0.25-dev.10 — 2026-10-08 (yerel geliştirme adayı)

- Metin katmanı boş PDF'nin rol sınıflandırması görsel göreve yönlendirilir; görev paketi yalnız ilgili sayfaların render yollarını ve SHA-256 değerlerini taşır.
- PDF render'ı kaynak dosya tanıtıcılarını kapatır. Görsel kanıt eksikken taranmış belgeye kesin teklif/şartname rolü verilmez.

# 5.0.25-dev.9 — 2026-10-08 (yerel geliştirme adayı)

- Koşu başında kanıtlı klasör-firma beyanı uygulanır; belge zaten teklif olarak okunmuşsa yalnız firma kimliği için model görevi açılmaz. Bilinmeyen belge rolü yine modele/incelemeye gider.
- Beyan dosyası ve SHA-256 koşu sözleşmesine kaydedilir; hukuki unvan doğrulanmış sayılmaz.
- Ayrıştırıcı önbelleği e-posta eki/mükerrerlik gibi belgeye özgü durumu taşımayı bırakır.

# 5.0.25-dev.8 — 2026-10-08 (yerel geliştirme adayı)

- E-posta ekleri güvenli sınırlarla ayrı kaynak belge olarak alınır; özgün/ZIP/e-posta içeriği aynı SHA ise çocuk kayıt denetim iziyle pasif kalır.
- İç içe teklif klasörlerinde kullanıcı tarafından bildirilen firma yolu en uzun eşleşen klasörden alınır; hukuki unvan doğrulaması sayılmaz.

# 5.0.25-dev.7 — 2026-10-08 (yerel geliştirme adayı)

- Bağımsız okuma filtresi, görevdeki document_ids listesini kullanır; listedeki bütün belgelerin otoritesi açık değilse görevi bekletir.

# 5.0.25-dev.6 — 2026-10-08 (yerel geliştirme adayı)

- Geçerli revizyon sorusu açıkken yalnız bağımsız ve kontrol edici kaynakların okuma görevleri sürdürülebilir; sorular aynı yanıtta görünür ve karar/çıktı kapalı kalır.

# 5.0.25-dev.5 — 2026-10-08 (yerel geliştirme adayı)

- Kaynak otoritesi firma içindeki bağımsız kalemlerle açık revizyon zincirlerini ayrı değerlendirir; geçerli sürümü tahmin etmez.
- Bu koşuya özgü kullanıcı klasör→firma beyanı, hukuki unvan doğrulaması sayılmadan denetimli girdiye bağlanır.
- Semantik çıkarım sürerken türetilmiş karşılaştırma soruları kullanıcıya erken sunulmaz; açık kaynak/revizyon soruları korunur.
- Yüksek güvence PDF görsel QA paketleri en çok üç sayfadır; boş kayıt işareti okunaklıdır.

# 5.0.25-dev.4 — 2026-10-07 (yerel geliştirme adayı)

- r6: REVIEW, REPORT veya QA geçişinde yeni kritik iş sorusu açıldığında aynı çağrı `NEEDS_USER_INPUT` ve soru listesi döndürür; bağlı teslim durur.
- r5: PDF görsel QA beklerken rapor dosyalarının `ready` kaydı teslim edilebilirlik sayılmaz. Durum çıktısı son doğrulama ve kapanış bütünlüğü tamamlanmadan `deliverable_artifacts=false` bildirir.
- Kritik iş belirsizliğinde kaynak ve teklif kapsamlı soru `NEEDS_USER_INPUT` ile gösterilir; bağlı karar özeti ve Excel/PDF ilerlemez.
- Kullanıcı yanıtı mevcut olay günlüğüne ve hash bağlı dosyaya kaydedilir. Geçerli yeni girdi ayrı koşuda yeniden hesaplanır; eski görev, snapshot ve QA onayı aktarılmaz.
- Soru ve yanıt metinleri kurumsal dil standardına tabidir. Güncelleyici çalıştırılabilir dosyaları değişmedi. Gerçek belge kabulü ve GitHub yayını yapılmadı.

# 5.0.24 — 2026-10-07

- Bağımsız fiyat kümesi tam kaynak maliyetlerinden yeniden kurulur; kayıp türetilmiş maliyet satırı ortak yanlış PASS üretmez.
- Gerçek eksik kaynak için fiyat ve ağırlıklı kriter kümeleri ayrı korunur; toplam kabul doğrulanmamış kalır. Eski hesap çağrılarının finans girdileri korunur.
- Ana hesap, politika, DB şeması ve görev sonuç şeması değişmedi. Şema iç sürümü 5.0.23 kalır. Yerel yazılım kabulü gerçek teklif teslimi veya yayın onayı değildir.

# 5.0.23 — 2026-10-07

- Meşru karşılaştırma bastırması dokuz koşul ve aktif teklif sayısından bağımsız doğrulanır; sahte statü, gerekçe, sıralama ve uygun teklif üyeliği reddedilir. Eksik maliyet ve karar kapıları korunur.
- Ödeme planının ratio/amount/days alan sözleşmesi görev şeması, paket ve kayıt öncesi doğrulama boyunca açık hale getirildi; kapsam kanıt statüsü maliyet rolünden ayrıldı.
- Sonlu olmayan ödeme tutarı/iskonto oranı sahte PV üretmez; tutarla belirtilmiş teslim sonrası ödeme günü doğrulanmış teslim süresine bağlanır.
- Görev sonuç şeması 5.0.23; DB şeması ve politika baytları değişmedi. Yerel adayın test kabulü gerçek belge teslimi veya yayın onayı değildir.

# 5.0.21 — 2026-10-06

## 5.0.22 — 2026-10-06

- Bağımsız hesap, uygun teklif kümesini ham kanonik kayıtlardan yeniden doğrular; elenen teklif puanlamaya dönmez.
- Ana skor girdisi ve fiyat/ağırlıklı sonuç listelerinde eksik, fazla ve tekrarlı kimlikler reddedilir; fiyat ve ağırlıklı skorun ayrı kapsamları korunur.
- 0/1 uygun teklif ile eksik karşılaştırılabilir maliyet ayrı doğrulanır; geçmiş maliyetler ve bağımsız aritmetik korunur.


- Gerçek `BUDGET_EXHAUSTED` sonuçları, sonuç ve workflow davranışı korunarak yerel hata kaydına girer.
- Bağımsız teyit, yalnız açık ve bilinen KDV dahil/hariç eşanlamlarını ortak kanonikleştirir; bilinmeyen veya olumsuz ifadeleri çözülmüş saymaz ve ham kaynak alıntısını değiştirmez.
- Saf `independent_confirmation_required` issue'su yalnız bütün güncel değer/kanıt/hash bağları sağlandığında `IDARE`, `TUM_FIRMALAR` veya aynı teklifin kanonik `supplier_id` değerini taşıyan `FIRMA:<supplier_id>` sahibi için kapanır; sahibin değeri kapanış makbuzunda korunur.
- Görsel teyit paketinde issue sahibi seçenekleri ve firma anahtarı açıklanır. Ticari onay, yanlış/boş sahip ve eksik, çelişkili veya eski kanıt açık kalır. DB şeması, policy_version ve karar kapıları değişmedi.

- Karar, bağımsız yeniden hesap, maliyet köprüsü ve snapshot yalnız aktif teklif hesaplarını kullanır; linked_support/eski revizyon hesapları tarihçede kalır. Sahipsiz hesap sessizce düşürülmez, bütünlük hatasıdır.
- Yalnız reserved independent_confirmation_required türündeki saf teyit RFI, bütün bağlı görsel alanların mevcut değer/kanıt/hash eşleşmesiyle bağımsız teyidinden sonra denetlenebilir makbuzla kapanır. Ticari onay, ek koşul/kanıt, eksik veya eskimiş teyit kapanmaz; kapanış makbuzu snapshot ve koşu bütünlüğüne bağlıdır.
- Hatalar yerel UTF-8 JSONL kaydına yazılır; başarı/normal bilgi eksikliği, belge/sohbet içeriği, ham hata metni ve tam yollar kayda alınmaz. Kayıt sınırları ve sessiz hata toleransı vardır; yeni bağımlılık/ağ/model çağrısı yoktur. Ayrıntı references/error-logging.md.
- DB şeması değişmedi (5.0.18). Kapılar/puanlama/finans parametreleri gevşetilmedi; yerel aday, yayın/kurulum onayı değildir.

# 5.0.19 — 2026-10-06

- Görev seçimi evre sırasına uyar; son PREPARE sınıflandırması yanında erken EXTRACT context pinlenmez.
- Kaynak ilişkisi penceresi bütün sınıflandırmalardan sonra açılır ve ilk sınıflandırma dışı dispatch ile kapanır; geç değişiklik kanonik yazımdan önce reddedilir.
- Beş regresyon: öncelik/efor sınırı, geç ilişki atomik ret ve gerçek context üretimi/tekrar. Kalite ve değişmez context kapıları korunur. DB şeması değişmedi (5.0.18).

# Changelog
## v5.0.18 - 2026-10-06 - Yerel yayın adayı (RC19)

- Kabul edilmiş çok kalemli ayrıntı yenilemede korunur; kapalı kalem şeması, kendi kanıt ölçeği ve ayrı hesaplanan alt toplam Excel/PDF boyunca izlenir. Eksik miktar ve karma fiyat türü satınalma genel toplamı yapılmaz.
- Kapsam sınıfından bağımsız dahil/ek/belirsiz maliyet rolü eklendi; iki hesap motoru dahil tutarı ikinci kez eklemez ve teyitsiz ek bedeli kullanmaz.
- Aynı firmadaki bağımsız teklifler otomatik kapatılmaz. Açık beyanlı kaynak ilişkisi ve hash/para/miktar/birim/kapsam/tarih bağlarına dayalı dar görsel teyit eklendi; piksel sayısı alt kalem veya ek maliyet üzerinden teyit kapısını aşamaz.
- Koşu yürütme manifesti, değişmez dispatch, kontrollü cache yeniden okuma, ön/son denetimli DB dönüşümü ve yeni koşuda prepare sözleşmesi eklendi.
- Tamamlanmış koşuya next/validate yeniden girişi kaynak/arşiv/yanıt/context/makbuz/snapshot/çıktı/QA kapanış kanıtını salt okunur doğrular; eksik veya değişmiş kanıt eski VERIFIED sonucunu taşımaz.
- Geliştirme regresyonları iki motorda sınanır; yayın kabulü ayrıca donmuş ZIP üzerindeki tam suite ve gerçek/sentetik belge teslimi gerektirir. Kalite kapıları gevşetilmedi.

## v5.0.17 - 2026-10-05 - Yerel yayın adayı (RC17)

- Yinelenen teklif/alan veya teklif/şartname kimlikleri kanonik kayıttan önce reddedilir; farklı model fact_id değerleri satırları sessizce ezemez.
- Teklif alan adları ve görev kapsaması kayıt öncesi doğrulanır. Görsel paketler kanonik alan listesini ve gerçek görsel kaynak birimlerini taşır. Çok kalemli miktar/kapsam/teslim tek alanda tüm kalemleri ve belirsizlikleri korur.
- Yazım öncesi reddin fact/evidence/model makbuzu yaratmadığı ve görev tamamlamadığı iki motorlu regresyonlarla sınanır.
- Yazım öncesi tekillik, kanonik alan adı ve görev alan kapsama kontrolleri sıkılaştırıldı; hesaplar değiştirilmedi.

## v5.0.16 - 2026-10-05 - Yerel yayın adayı (RC14)

- Sınıflandırmada doğrulanan firma adı canonical tedarikçi kimliğine taşınır; geçici dosya adı kimlikleri bağımsız tedarikçi gibi kalmaz.
- Her formal kaynak ayrı teklif kaydı taşır; doğrulanmamış revizyon/kapsamlar tek fiyat içinde birleştirilmez. Revize etiketleri gözlenir, tarih/dosya adından geçerli sürüm seçilmez.
- Geçici firma kimliği sınıflandırma/RFI kapısından geçer; mevcut tek-kaynak teklif/fact ilişkileri aynı atomik kayıt içinde düzeltilir, ortak eski teklif sessizce yeniden bağlanmaz.
- Tedarikçi ve revizyon otoritesi regresyonları eklendi; kaynak koruma/şema/hesap kapıları gevşetilmedi.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.15 - 2026-10-05 - Yerel yayın adayı (RC13)

- DOCX revizyon algılama gerçek OOXML namespace/öğe adlarını kullanır; tablo kenarlıkları `insideH`/`insideV` artık yanlış değişiklik izleme sayılmaz.
- Gerçek ekleme/silme, taşıma ve özellik revizyonları hedefli regresyonlarla korunur; parser cache sürümü yeni okuyucu davranışını ayırır.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.14 - 2026-10-05 - Yerel yayın adayı (RC12)

- Teklif alan görevi yalnız teklif düzeyindeki kayıtlara bakar ve yalnız deterministik aşamadan kalan çözülmemiş alanları ister. Gerçek sette şartname uygunluk kayıtları (`requirement_compliance`) ve modelin zaten "eksik" diye yanıtladığı alanlar her turda yeni bir alan görevi açıyordu; gereksiz model maliyeti ve döngü riski vardı. Modelin yanıtladığı boşluk RFI ve bağımsız kontrolle taşınır.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.13 - 2026-10-05 - Yerel yayın adayı (RC11)

- Kanıt doğrulayıcı, tablolu PDF'lerde birebir doğru alıntıları reddediyordu: yapısal içerik JSON metni olarak aranıyordu ve JSON satır sonlarını kaçışlı yazdığı için çok satırlı bir tablo hücresinden alınan alıntı hiç eşleşmiyordu (gerçek sette fiyat tablosu, ödeme planı ve kapsam listesi). Artık alıntı hücre metinlerinde, hücreleri boşlukla birleştirilmiş satırlarda ve satır sırasıyla tüm tabloda aranır. Kaynakta olmayan metin yine reddedilir; model paketleri değişmedi.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.12 - 2026-10-05 - Yerel yayın adayı (RC10)

- Deterministik para birimi yalnız açık bir toplam satırında ("genel toplam", "son toplam", "toplam fiyat" vb.) bir tutarla birlikte geçiyorsa doğrulanmış sayılır. Gerçek sette tamamı USD olan bir teklifte "devreye alma 500 € gün × adam + KDV bedel" maddesi para birimini doğrulanmış EUR yapıyordu; artık böyle satırlar teyit bekler ve teklif para birimi model görevinde gerçek toplamdan çözülür. "son toplam" açık toplam etiketi olarak tanınır.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.11 - 2026-10-05 - Yerel yayın adayı (RC9)

- Gerçek belge kabulünde model sonuçlarının çoğu doğru okunduğu halde kanıt kapısında reddedildi: kaynak okuyan görev paketleri, kaydedicinin uyguladığı kanıt kurallarını modele söylemiyordu. Artık her kaynak okuyucu pakette `evidence_contract` var: alıntı birebir ve tek parça; doğrulanmış metin/sayı kendi alıntısında geçer; yorum ve özet `normalized` alanına; tek bir alıntıyla desteklenmeyen değer doğrulanmış değil teyit beklemede kalır. Kapı gevşetilmedi.
- Para birimi kanıtı: yalnız sembol veya yerel adı içeren alıntı ($, €, £, TL, ₺, dolar, avro) ilgili ISO kodunu destekler; başka bir para biriminin sembolü reddedilir. Deterministik çıkarım €, ₺ ve £ sembollerini de tanır.

## v5.0.10 - 2026-10-05 - Yerel yayın adayı (RC8)

- İlk gerçek belge kabulünde (3 teklif + teknik şartname) bulunan deterministik çıkarım hataları düzeltildi:
  - Toplam: satırda yalnız "toplam" geçmesi yetmez; yüzdeler asla tutar sayılmaz, para birimi yoksa yalnız binlik ayraçlı veya en az 1000 olan değerler aday olur. Avans/iptal/ödeme/fatura maddelerindeki ve açık toplam etiketi olmayan adaylar doğrulanmış değil, teyit bekleyen olarak kalır. (Gözlenen: bir avans maddesindeki %20, toplam olarak "verified" oluyordu.)
  - Para birimi: yüksek güven yalnız aynı satırda gerçek bir tutar varken; ödeme/kur/kambiyo maddesindeki para birimi düşük güvenli kalır.
  - Belge rolü: dosya adındaki teklif/şartname sözcüğü sınıflandırmaya katılır; metindeki sertifika ifadesi bir teklifi "destek belgesi" yapmaz.
  - Revizyon etiketi yalnız ASCII kod olarak okunur (`_rev01` → `01`); "REVİZE" kelimesinden "İZE" etiketi üretilmez.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.9 - 2026-10-04 - Yerel yayın adayı (RC7)

- RC6 görsel kabulündeki tek bulgu düzeltildi: baskıda sütuna gerçekten sığan tek kelime artık tahmini sarma genişliği yüzünden bölünmez (`Belirtilmedi` → `Belirtilme` / `di` yok). Sütuna sığmayan uzun belirteçler eskisi gibi bölünür; sayıların tam sayı basamakları birlikte kalır.
- Boş tablo satırı (`Kayıt bulunmuyor.`) diğer hücrelerine `Belirtilmedi` yazılmadan boş kalır.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.8 - 2026-10-04 - Yerel yayın adayı (RC6)

- RC5 regresyonu düzeltildi: baskıda satır içi değişken bant listesini ezdiği için çok bantlı tablolarda başlık `Sütun grubu 2/1` gibi yanlış sayıyordu ve bant sayfa adı tekilliği riske giriyordu. Bant sayacı ve adları artık hücre içeriğinden bağımsız; çok bantlı regresyon testi eklendi.
- Kayıt listeleri (ör. doğrulama ifadeleri, maliyet köprüsü bileşenleri) kayıt başına boş satırla ayrılır; baskıda bir kayıt (kaynak, yol, karşılaştırma, değer, tolerans) devam satırları ve sayfalar arasında bölünmez. 20 satırı aşan tek kayıt satır bazına düşer.
- `≈` işareti değerle bölünmez boşlukla bağlanır.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.7 - 2026-10-04 - Yerel yayın adayı (RC5)

- RC4 PDF görsel kabulündeki iki bulgu düzeltildi (Hesap Detayı sayfaları RC4'te geçmişti):
  - Yapısal ayrıntı sütunlarında (Maliyet Köprüsü bileşenleri, bağımsız hesap ayrıntısı, kontrol değerleri) 6'dan fazla ondalık basamaklı aritmetik hassasiyet kalıntıları `≈ -1632.26` biçiminde yuvarlanmış ve açıkça işaretlenmiş gösterilir; kanonik değer reviewed snapshot'ta tam kalır. Kısa sayılar ve metin değişmez.
  - Baskıda uzun hücre devam satırlarına bölünürken bir mantıksal satır (etiket ve değeri) ayrılmaz; devam satırının kimlik hücresi `(devam)` ile işaretlenir. Satır başına 20 satır sınırı ve 11 punto korunur.
- Kalite kapıları, şema, hesap ve görev sonuç sözleşmeleri değişmedi.

## v5.0.6 - 2026-10-04 - Yerel yayın adayı (RC4)

- PDF/Excel Hesap Detayı okunur biçime geçti: her hesap kalemi ayrı satırda (Firma, Teklif, Hesap, Kalem, Değer, Birim, Durum). Tutarlar ve puanlar metin değil sayısal hücre; baskıda rakamlar bölünmez, para birimi ayrı sütunda görünür. Puanlama satırları her teklifin maliyet ölçüsü, fiyat puanı ve maliyet sırasıyla aynı blokta, maliyet sırasına göre listelenir. Değer hücreleri hesap kimliğine bağlanır.
- Baskı düzeninde uzun sayılar artık tam sayı basamaklarının arasından bölünmez; gerekirse yalnız ondalık noktadan sonra devam eder. Kanonik hesap JSON'u, reviewed snapshot ve kalite kapıları değişmedi; yazı tipi küçültülmedi.
- Eksik çalışma ortamında artık plugin'de bulunmayan güncelleyiciye yönlendirme yapılmaz. `environment_check.py` ve `workflow.py prepare` `BLOCKED_ENVIRONMENT` (çıkış kodu 3) döndürür, somut `missing_components` listesi ve Türkçe `user_message` verir; analiz başlamaz, hiçbir şey kurulmaz. `UPDATER_REQUIRED`/`RUN_GUNCELLE_RUNTIME_REPAIR` ve `runtime_handoff.py` sözleşmesi kaldırıldı. `resume_request.json` korunur: bileşenler elle kurulup kontrol `READY` olunca aynı istekle devam edilir.
- Şema, hesap ve görev sonuç sözleşmesi sürümleri (5.0.5) değişmedi; bu sürüm yalnız sunum ve ortam duruşu değişikliğidir.

## v5.0.5 - 2026-10-04 - Yerel yayın adayı

- İkinci yerel aday: PDF Elemeler alt tablosunun başlığı ayırt edilir; hücre kenarında boşluk korunur. Kanonik kaynak/değer ve kalite kapıları değişmez.

- Önceki PDF bulgularının yalnız güncel sayfa hash'leriyle kapanması ve denetim kaydı.
- Görsel belge kimliklerinin teklif kaynaklarına eksiksiz eklenmesi.
- Yönetici özetinin normal görev akışında sınırlı yeniden üretimi; geçmiş iddiaların korunması, aktif soyun doğrulanması.
- Güncelleyicinin ayrı v5 paket sözleşmesi ve kurulum yapmayan runtime devri.
- Bu kayıt yerel adayı tanımlar. Paket kabul kanıtı dış rapordadır; GitHub yayını ve canlı plugin kurulumu yapılmadı.

## v5.0.4 - 2026-10-03

- Pro bağımsız denetimindeki P0/P1 bulguları fail-closed regresyonlara dönüştürüldü; yanlış `VERIFIED` üreten yollar kapatıldı.
- Hesaplanmamış XLSX formülü artık sayı gibi ayrıştırılmıyor; cached değer yoksa kritik alan doğrulanmış sayılmıyor ve çelişen toplam adayları `conflicting` oluyor.
- Model kanıt kayıtlarında belge/teklif/görev sahipliği, gerçek locator çözümü, kaynak alıntısı ve sayısal/metinsel değer desteği doğrulanıyor; başarısız sonuçlar tek transaction ile rollback oluyor.
- Comparability contract ürün/kapsam kimliği ile açık miktar birimini zorunlu tutuyor; satır toplamı-genel toplam uyuşmazlığı kritik veri-kalitesi bulgusu oluyor.
- Ödeme planında oran+tutar+anapara mutabakatı, negatif/aşan değerler ve teslime bağlı vade bazı doğrulanıyor; incomplete maliyet hesabı bağımsız kontrolde/karar kapısında geçemiyor.
- Sayısal yönetici claim'leri deterministik assertion olmadan doğrulanmıyor; serbest metindeki sayılar exact passing assertion ile bağlanmadıkça unsupported oluyor.
- Reviewed snapshot içerik-adresli/idempotent hale getirildi; tamamlanmış koşunun değişmeden yeniden çağrılması yeni snapshot üretmiyor.
- FX cost bridge yalnız aynı yerel para birimi veya kaynak+tarihli ortak base currency üzerinden pairwise fark üretiyor.
- Context packet final serialized byte/character sınırını fail-closed uyguluyor; eksik token makbuzu başarılı model sonucu olarak kaydedilemiyor ve geçmiş unknown kullanım bütçeyi durduruyor.
- Native Excel date/datetime değerleri JSON-safe normalize ediliyor; final workbook formula-free ve untrusted `=` metni literal olarak escape ediliyor.
- Bağımsız scoring kontrolü weighted score/ranking/weight total/top gap/distinguishing ratio dahil yeniden hesaplıyor.
- Legacy Excel/Word COM açılışında makrolar/event/link update kapatılıyor; ZIP intake duplicate/path traversal/symlink/şişme limitlerini reddediyor.
- Runtime resume handoff bütün analysis/financial/scoring parametrelerini `resume_request.json` içinde koruyor. CLI `PRELIMINARY`/`UPDATER_REQUIRED`/`BLOCKED` durumlarını non-zero exit code ile ayırıyor.
- Yüksek güvence PDF QA artık parent hash yanında aktif tedarikçi etiketlerini ve kritik snapshot sayılarını gerçek PDF metninde mekanik olarak doğruluyor.
- Toplam otomatik test sayısı 55'e çıkarıldı; v5.0.4 denetim regresyonları 27 negatif/sertleştirme senaryosu içeriyor.

## v5.0.3 - 2026-10-03

- Rapor öncesi immutable `reviewed_snapshot.json` ve SHA-256 parent lineage eklendi; Excel/PDF/decision snapshot aynı frozen veri kümesinden türetiliyor.
- `comparison_contract.py` kapsam/miktar/birim/döviz/base-date/ödeme/KDV/Incoterm bazlarını eşitlemeden ranking/scoring'i karar verisi saymıyor.
- `independent_recompute.py` kritik maliyet/NPV/TCO/scoring hesaplarını ana hesap motorundan bağımsız formülle yeniden hesaplıyor.
- `cost_bridge.py` tedarikçi maliyet farklarını bileşenler + residual olarak mutabıklaştırıyor.
- `grain_integrity.py` duplicate canonical grain ve JOIN/genişleme risklerini ayrı kontrol katmanı olarak kaydediyor.
- `scope_ledger.py` beklenen kaynak/tedarikçi/analiz/çıktı kapsamını pre-output ve final aşamada denetliyor.
- `claim_registry.py` yönetici iddialarını observation/calculated/assumption/hypothesis/recommendation olarak sınıflandırıp fact/calculation/evidence desteğine bağlıyor.
- `artifact_bindings` ile Excel/PDF/özet bileşenleri canonical fact/requirement/calculation/claim ve snapshot hash'ine bağlandı.
- `provenance_survival.py` değer dışında status/source/locator/caveat/claim sınıfı ve lineage'ın export boyunca korunmasını doğruluyor.
- Cross-output consistency canlı DB yerine reviewed snapshot'ı kaynak gerçek kabul ediyor.
- Final validation ve coverage; comparability, independent recompute, cost bridge residual, claim support, snapshot lineage, provenance survival, scope completeness ve grain integrity kapılarıyla genişletildi.
- v5.0.3 özel kabul testleri eklendi; regression + yeni kontroller toplam 28 otomatik testte doğrulandı.

## v5.0.2 - 2026-10-03

- Dis tedarikci belgeleri icin untrusted-reader guven zarfi eklendi; source-reading gorevleri write/shell/updater/workflow-control yetkisi alamaz.
- Her LLM sonucu DuckDB'a yazilmadan once strict JSON Schema ile dogrulaniyor ve validation receipt tutuluyor.
- `source_authority` katmani eklendi; birden fazla teklif/sartname revizyonunda dosya adi veya tarihten otomatik controlling source secilmiyor.
- Canonical store icin deterministic data-quality gate eklendi: evidence hash, orphan, duplicate grain, kritik validity ve source-shape kontrolleri.
- ChatGPT Data validation deseninden revision-aware coverage record ve `0/N != full verification` semantigi eklendi.
- Excel/PDF/decision ciktisi ile canonical facts arasinda `cross_output_consistency.py` mutabakati eklendi.
- `xlsx_formula_audit.py` ile cached Excel errors, external workbook links, hidden content, formula-pattern anomaly ve pasted-over formula kontrolleri eklendi.
- `skill_selfcheck.py` ile surum, JSON/schema, Python compile, requirements ve SKILL reference kontrolleri eklendi.
- Final `validate_run.py` schema receipts, structural data-quality, cross-output ve coverage gaplerini teslim kapisina dahil ediyor.

## v5.0.1 - 2026-10-03

- Teklif analizinden önce zorunlu runtime preflight eklendi.
- `requirements.txt` paketleri ve sürüm aralıkları, DuckDB ve DuckDB PDF extension doğrulanır.
- Eksik ortamda analiz başlamaz; `teklif-degerlendirme-guncelle` skill'i `repair-runtime` için otomatik devralır.
- Başarılı onarımdan sonra preflight yeniden çalışır ve aynı teklif analizi otomatik devam eder.
- Otomatik release/GitHub güncellemesi kapalı kalır; otomasyon yalnız çalışma ortamı onarımı içindir.
- `workflow.py prepare` başlangıç kontrolünü kod seviyesinde de zorunlu kılar.

## 5.0.0

- Replaced LLM-centered orchestration with deterministic Python + DuckDB workflow state.
- Added format adapters for PDF, XLSX/XLSM/XLS, CSV/TSV, DOCX/DOC, images, EML/MSG, text and safe ZIP intake.
- Added canonical evidence locators and content-hash extraction cache.
- Added early decision-sufficiency gate to stop expensive final analysis when critical information is open.
- Added deterministic finance, cost, TCO, FX, VAT, hard-gate and scoring helpers.
- Added primary/secondary evidence comparison and disagreement-only adjudication.
- Added bounded context packets; full-context rereads are forbidden by default.
- Added high-assurance secondary PDF path using an already-installed compatible DuckDB PDF extension when available.
- Added first-release full visual QA plus page-hash delta QA for revisions.
- Added source-traceable Excel output and final VERIFIED/PRELIMINARY/BLOCKED validation.
- Preserved v4 procurement/domain rules in `references/legacy-v4/` while v5 execution rules take precedence.
- Model routing is capability-based and runtime-catalog-resolved rather than pinned to one model version.
- Added mandatory model/effort receipts for completed model tasks and receipt-based token budget accounting with explicit user override.
# 5.0.25-dev.13 — 2026-10-08 (yerel geliştirme adayı)

- Görselden çıkarılan şartname kanıtı görsel okuma yolu ile kaydedilir; kritik sayısal şartlar bağımsız teyit olmadan doğrulanmış sayılmaz.
- Görsel şartname görevinde gerçek görsel birim konumu kullanılır; bulunmayan sayfa numarası üretilmez.


## 5.0.29-dev.10

Kaynak/soru/hash kapsamlı tarih yanıtı uygulaması ve açık bilinmeyen cevabın tekrarsız, seçimsiz ön karar raporu. Karar paketi ve çıktı kapısında ortak kapsam ön kontrolü. Öneri hücresinde kanonik firma ve düz metin; ayrı ödeme oranı/vade sayılarının ayrıştırılması. Özgün kaynak durumları ve tüm hesap/QA kapıları korunur.


## 5.0.29-dev.10

Etkin kullanıcı kanıtının hesap, soru kapanışı, karar ve kabul kapsamına tutarlı uygulanması. Çok alanlı soruların alan bazında kapanışı; bilinmeyen teklif tarihinin güncel geçerlilik kanıtı ile karar etkisinin ayrılması. Özgün kaynak eksiklikleri korunarak ayrı değerlendirme kanıtı; karma birimlerde kaynak satırı uzlaştırması ve gerekçeli uygulanmaz kaydı. Kaynak, hesap ve görsel kalite kapıları korunmuştur.


## 5.0.29-dev.10

Kaynak alanındaki eksiklik gözlemi için tam durum iddiası doğrulaması. Eksiklik kanıtı olumlu fiyat veya firma önerisi kanıtına dönüşmez; hatalı durum, eksik bağ ve hesap kontrolleri korunur. Karar paketinde kullanıcı dayanağı ve özgün kaynak eksikliği iddialarının ayrı bağlanması açıklanmıştır.


## 5.0.29-dev.10

Karar paketindeki sayısal iddia açıklaması mevcut sözleşmeyle uyumlu hâle getirildi. Her sayısal iddia için tam bağlı ve doğrulamayı geçen assertion gerekliliği korunmuştur. Hesap, kaynak ve öneri kanıtı kontrolleri değiştirilmemiştir.


## 5.0.29-dev.10

Cevaplanmış kapsam sorusunda açık soru kanıtı ile geniş ürün kapsamı kanıtı ayrıldı. Karar paketinde firma adı her hesap satırına teklif kimliğiyle bağlandı; dizi sırasına göre isim eşleştirmesi yasaklandı. Kaynak ve hesap kontrolleri korunmuştur.


## 5.0.29-dev.10

Geçerli kullanıcı ödeme ve geçerlilik bilgileri ana karşılaştırmada hesap kanıtına bağlı gösterilir. Kaynak durumu ayrı etiketlenir; uygulanmayan toplam puan gerekçesi açık yazılır. Tutarlılık ve kaynak kontrolleri korunur.
