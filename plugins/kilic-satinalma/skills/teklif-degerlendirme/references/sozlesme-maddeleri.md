# Sözleşmesel Koşulların Karşılaştırılması

Tekliflerin ekindeki "genel satış şartları"/genel şartlar, teklif metnindeki tek satırlık
kayıtlar ve şartnamedeki sözleşme maddeleri karşılaştırılır.
**Fiyatı en iyi teklif, sözleşme maddeleriyle en pahalı teklif hâline gelebilir.**

Bu modül **hukuki danışmanlık değildir.** Riskli veya şartnameyle çelişen maddeler tespit
edilip işaretlenir; nihai değerlendirme ve sözleşme metni için hukuk müşaviri teyidi
gereklidir. Excel'de bu satırlar **"hukuk teyidi önerilir"** notuyla işaretlenir.

## Karşılaştırma tablosu — madde × firma

Her madde için: **şartnamenin istediği | firmanın teklifi | değerlendirme (uygun / sapma /
riskli / belirtilmemiş) | önem derecesi.**

Maddelerin bir kısmı dala özgüdür; ilgisiz madde tabloda "bu işte yok" olarak kalır.

### 1. Gecikme cezası (cezai şart)

- Oran (günlük/haftalık; sözleşme bedeli üzerinden mi, gecikilen kısım/kalem üzerinden mi)
- **Üst limit — en çok atlanan nokta.** "Toplam %5 ile sınırlıdır" maddesi uzun gecikmede
  cezayı sembolik yapar
- **Gecikmenin başlangıç anı:** sözleşme tarihi mi, avans ödemesi mi, onaylı imalat resmi
  mi, yer teslimi mi (firma "resim onayından itibaren" yazarak süreyi belirsizleştirebilir)
- Süre uzatım gerekçeleri: hava muhalefeti, proje revizyonu, işveren kaynaklı gecikme
  (yer teslimi, onay süreleri) — **tanımların genişliği firmanın ceza riskini fiilen
  sıfırlayabilir**
- Ceza dışında fesih, ikame tedarik ve işi başkasına yaptırma (nam-ı hesabına) hakkı var mı

**Ceza önerisi gerekiyorsa raporda hesabıyla açıkla:** teslim gecikmesi, performans
eksikliği, hizmet seviyesi (SLA) ihlali veya kusurun giderilmemesi için hangi yaptırımın
neden gerekli olduğunu işin süre/üretim/kalite etkisine bağla. Günlük/haftalık oranı
veya olay başına sabit tutarı; hesap matrahını (KDV dahil/hariç, toplam sözleşme mi
etkilenen kısım mı), para birimini ve toplam üst limiti yaz. Genel bir yüzde dayatma.
Oranı duruş kaybı, ikame tedarik süresi/maliyeti, işin kritikliği ve ölçülülükle gerekçelendir.

- Oranlı cezada `dönem cezası = matrah × dönem oranı`, `toplam ceza = min(dönem
  cezası × cezaya tabi dönem, üst limit tutarı)` hesabını göster. Üst limit başka
  matraha dayanıyorsa ayrı belirt. Uygun gecikme senaryolarında parasal sonucu yaz.
- Vade/teslim başlangıcı ile **cezanın işlemeye başladığı tarihi** ayır; takvim/iş günü,
  varsa ek süre, ihtar ve düzeltme süresi, bitiş/kabul anı, süre uzatımı ve istisnalar
  tanımlı olsun. SLA'da ölçüm yöntemi ve ihlal eşiğini de belirt.
- Birden çok cezanın aynı olayda birleşmesi, toplam tavan, mahsup, fesih ve ayrıca
  zarar talebi ilişkisini açıklığa kavuştur. Ceza ile tahmini zararı aynı maliyet gibi
  iki kez sayma; henüz doğmamış ceza tahsilatını KTM'den düşme.
- Önerilen maddeyi anlaşılır taslak olarak yaz; uygulanabilirlik/ölçülülük için hukuk
  teyidi gereken noktaları somutlaştır. Mevcut teklif hükmü ile öneri ayrı dursun.

### 2. Süre/teslim taahhüdünün bağlı olduğu koşullar

- Neye bağlı: yer teslimi, avans, proje/imalat resmi onayı, ruhsat, malzeme temini,
  "üretim programına göre"
- İş programı teslim yükümlülüğü ve güncelleme düzeni
- **Belirsiz koşula bağlanmış süre taahhüt sayılmaz** — RFI'da netleştirilir

### 3. Teminatlar ve çözülme takvimi

- Avans teminat mektubu, performans/kesin teminat oranı ve garanti dönemi teminatı.
  Avans varsa korunmamış avans riskini mutlaka incele; mektup veya eşdeğer güvencenin
  gerekliliğini açıkla. Şirket/şartname zorunluluğu ile ticari öneriyi ayır; avansın
  varlığını tek başına genel bir yasal zorunluluk olarak sunma.
- Yapım işinde hakediş teminat kesintisi oranı ve iade zamanı
- **Teminatın çözülme koşulları:** geçici kabul → kısmi çözüm; kesin kabul + **SGK
  ilişiksizlik belgesi** + vergi borcu yoktur → tam çözüm. İlişiksizlik şartı yazılmamışsa
  işveren SGK prim borcundan müteselsil sorumluluk riski taşır — **kırmızı çizgi adayı**
- Teminat süreleri iş/teslim + garanti veya kesin kabul dönemini kapsıyor mu; süresiz mi,
  uzatılabilir mi
- **Teminat vermeyi reddeden firma yüksek avans istiyorsa kırmızı çizgi**

**Gerekiyorsa avans ve kesin teminatı ayrı ayrı, tutar ve süreyle öner:**

- **Avans:** iade/mahsup edilmemiş avans riskini ve ödeme planını esas al.
  Başlangıç mektup tutarı önerisini korunacak avansla ilişkilendir; KDV dahil/hariç
  esasını ve para birimini yaz. `Korunacak bakiye = ödenmiş avans − teyitli avans
  mahsupları/iadeleri`; taksitli avansta sonraki ödeme öncesinde teminatın yeterli
  olduğunu kontrol et. İlave güvence öneriliyorsa gerekçesini ayrı göster.
- **Kesin/performans:** işi tamamlama, kusur giderme ve ikame yüklenici risklerine göre
  oran veya tutar öner. `Teminat tutarı = belirtilen sözleşme matrahı × önerilen oran`;
  matrah, para birimi ve hesap sonucu açık olsun. Neden bu tutarın seçildiğini kalan
  işin maliyeti, avans dışındaki risk ve tedarikçi yeterliliğiyle açıkla. Avans mektubunu
  kesin teminat yerine sayma; hakediş kesintisi ve garanti teminatıyla örtüşmeyi göster.
- **Süre:** başlangıç olayını, geçerlilik bitişini ve gerekçeli talep/işlem payını
  belirt. Avans güvencesi için tam mahsup/iade, performans için ilgili kabul ve
  yükümlülüklerin bitişi, gerekiyorsa garanti dönemi güvencesine geçiş ayrı gösterilir.
  Tarihler belliyse tarih ver; değilse olay + süre ve eksik takvim girdisini yaz.
  İş uzarsa teminatın uzatılması/yenilenmesi ve süre dolmadan kontrol tarihi yer alsın.
- Düzenleyen banka, lehtar, ilk talepte ödeme koşulları, belge/itiraz şartları,
  azaltma/iade koşulları ve kabul edilebilir mektup metni için teyit gereken noktaları
  belirt. İade için SGK/vergi belgelerinin uygulanabilirliğini işin kapsamına göre
  doğrula; bütün mal/hizmet alımlarına otomatik taşıma.
- Mektup **nominal tutarını** banka komisyonundan ayır. Komisyonu kimin taşıdığı ve
  süre/ücret dayanağı `finansal-degerlendirme.md` ile değerlendirilir; teminatın yüz
  tutarı satınalma gideri olarak KTM'ye eklenmez.

### 4. Fiyat sabitliği: eskalasyon / fiyat revizyon maddesi

- Madde varsa: endeks (TÜİK inşaat maliyet, çelik piyasa+kur formülü, hammadde endeksi),
  taban ayı, eşik, kapsam (tüm bedel mi malzeme payı mı), tavan
  → **teklif sabit fiyatlı değildir, Özet'te uyarı**
- Madde yoksa ve iş uzunsa: gizli risk primi veya revizyon talebi riski notu
- **Kur maddesinde hangi kur** (TCMB DSK mı) ve **hangi tarih** (fatura, sevk, ödeme) esas
  alınıyor — bu tek kelime ciddi tutar farkı yaratır

### 5. İş artışı ve eksilişi (yapım işi ağırlıklı)

- Artış/eksiliş sınırı (özel sektörde serbest; kamu pratiğindeki %20 benzeri bir mekanizma
  tanımlanmış mı) ve artış birim fiyatının nasıl belirleneceği (sözleşme birim fiyatı mı,
  yeni fiyat tutanağı mı)
- **Yeni fiyat (sözleşmede olmayan iş) prosedürü tanımlı mı** — tanımsızsa her ilave iş
  pazarlık/uyuşmazlık konusudur, riskli işaretlenir
- Birim fiyatlı sözleşmede metraj azalışında firmanın tazminat talep hakkı var mı

### 6. Ödeme ve mahsup

- Vade başlangıcı (fatura tarihi mi, kabul mü); hakediş düzenleme-onay-ödeme süreleri;
  gecikme faizi
- **İşverenin/alıcının kesinti/mahsup hakkı kısıtlanmış mı** ("hiçbir kesinti yapılamaz"
  maddesi ceza uygulamasını engeller)
- Damga vergisi kimde

### 7. Riskin ve mülkiyetin geçişi

- Riskin geçiş anı — Incoterms ile tutarlı mı (makine); geçici kabule kadar sahadaki
  imalatın hasar riski kimde (yapım)
- **Mülkiyeti saklı tutma kaydı:** bedel tamamen ödenene kadar mülkiyet satıcıda kalıyorsa,
  ekipman kullanımda olsa bile hukuki durum farklıdır
- Nakliye/montaj sırasında sigorta kimde, kapsam ve muafiyet

### 8. Kabul: FAT/SAT, performans testi, geçici/kesin kabul

- Kabul kriterleri **ölçülebilir mi**, test protokolünü kim hazırlıyor
- Test başarısız olursa: düzeltme süresi, tekrar test, nihayetinde **red hakkı** ve iade
  koşulları
- **"Ekipman sahaya gelince kabul edilmiş sayılır"** veya **"işyerinin kullanılmaya
  başlanması kabul sayılır"** tipi zımni kabul maddeleri performans garantisini boşa
  çıkarır — **riskli işaretlenir**
- Zımni kabul süresi ("15 gün içinde itiraz edilmezse kabul edilmiş sayılır") varsa süresi
  ve başlangıcı
- Yapımda: eksik-kusur (punch list) giderim süresi ve yaptırımı; kesin kabul süresi (geçici
  kabulden itibaren, tipik 12 ay) ve bu dönemdeki bakım/onarım sorumluluğu
- **As-built, kalite dosyası, kaynak haritası, parametre yedekleri teslimi kabul ön şartı mı**

### 9. Garanti

- Süre ve **başlangıç anı** (sevk mi, devreye alma mı — sevkten başlayan garanti, montaj
  gecikirse erir; yapımda geçici kabul mü)
- Yapımda: **yapısal garanti ile yüzey koruma (boya/galvaniz) ve kaplama (panel)
  garantilerinin ayrımı** — süreler ve başlangıç anları
- Kapsam dışı haller (aşınma parçaları, kullanıcı hatası tanımının genişliği, "orijinal
  olmayan parça kullanımı" maddesi); **üretici garantisi ↔ uygulama garantisi** ayrımı
- Garanti kapsamında müdahale süresi ve parça/işçilik/yol dahil mi
- Garanti süresince **zorunlu bakım sözleşmesi** şartı var mı (gizli maliyet)
- Değişen parçaya yeni garanti veriliyor mu
- Ayıba karşı kanuni sorumluluk sürelerinin sözleşmeyle daraltılması girişimi →
  **riskli, hukuk teyidi**

### 10. Sorumluluk, sigorta ve hasar

- **All-risk (CAR) sigortası** (yapım): kim yaptırıyor, bedel, muafiyet, işveren ek
  sigortalı mı
- 3. şahıs mali mesuliyet; komşu parsel/mevcut tesis hasarı
- **Toplam sorumluluk üst sınırı** (sözleşme bedelinin %'si)
- **Dolaylı zarar / üretim kaybı / kâr kaybı sorumluluğunun tamamen reddi** — gıda/su
  ürünleri üretiminde duruş kaybı büyük olabileceği ve çalışan tesis yanında iş yapıldığı
  için **önem derecesi yüksek** işaretlenir

**Sigorta gerekiyorsa tür, kapsam, tutar ve süreyi gerekçelendir:**

- Yapımda inşaat bütün riskler (**CAR/all risk**), montaj/devreye almada montaj bütün
  riskler (**EAR**), taşımada nakliyat; üçüncü kişilere zarar riski varsa **3. şahıs
  mali mesuliyet** değerlendirilir. İşveren sorumluluk, ürün/mesleki sorumluluk veya
  diğer poliçeleri yalnız işin somut riskleri gerektiriyorsa ele al. Her tür için
  hangi olayın hangi varlığa/kişiye zarar verebileceğini ve neden gerekli olduğunu yaz.
- **Mal/iş bedeli sigortaları:** ilgili iş/malın yeniden yapım/ikame değerini ve poliçe
  kapsamına göre nakliye, montaj, test, geçici işler vb. bileşenleri ayrı göstererek
  önerilen sigorta bedelini hesapla. Sözleşme toplamını kapsamını doğrulamadan kullanma; mevcut
  tesis, komşu mallar ve enkaz kaldırma gibi ek riskler için kapsam/alt limitleri belirt.
- **Sorumluluk sigortaları:** olası tek olay zarar senaryosunu (bedeni/maddi zarar,
  komşu tesis, çalışan üretim alanı vb.) kur; **olay başına limit** ve **poliçe dönemi
  toplam limitini** para birimiyle öner. Neden yeterli görüldüğünü senaryo ve maruziyetle
  açıkla; sözleşme bedelinin sabit yüzdesinden otomatik limit türetme.
- Muafiyet, alt limitler, istisnalar, test/devreye alma, bakım dönemi ve mevcut tesis
  kapsamını belirt. **All risk adı her riski kapsadığı anlamına gelmez**; fiili kapsam
  poliçe metninden teyit edilir. Sigorta limiti ile sözleşmesel sorumluluk tavanını ayır.
- Poliçeyi yaptıran/prim ödeyen taraf, sigortalılar, gerekiyorsa işverenin ek sigortalı
  olması; başlangıç-bitiş olayları/tarihleri, uzama ve yenileme şartları yazılsın.
  Nakliye–saha–montaj–kabul geçişinde sigortasız dönem kalıp kalmadığını kontrol et.
- **Sigorta bedeli/limit ile primi karıştırma.** Bedeli/limiti öner; prim kotasyonu
  yoksa primi "fiyatlanmadı" yaz. Mevcut poliçenin kapsam/limit/süresini kontrol etmeden
  yeterli kabul etme veya ikinci poliçe maliyeti ekleme. Alıcıya kalan ilave prim
  ilgili KTM basamağına yalnız bir kez girer.

### 11. Mücbir sebep

- **Tanımın genişliği:** "tedarikçi kaynaklı gecikmeler", "hammadde/malzeme temin güçlüğü",
  "işçi bulunamaması", "alt yüklenici gecikmesi" mücbir sebep sayılıyorsa madde firmayı
  ceza riskinden büyük ölçüde kurtarır — **riskli**
- Olağanüstü hava tanımı (kaç günlük yağış eşiği) ve ispat yükü
- Bildirim süresi ve sonuçları (süre uzatımı mı, fesih hakkı mı)

### 12. Fikri mülkiyet, know-how ve yazılım

- Onaylı imalat resimlerinin, PLC programının ve kaynak kodunun kullanım hakkı
- **PLC/yazılım şifresi teslim ediliyor mu** — verilmezse bakım ve gelecekteki modifikasyon
  tek firmaya bağımlı hâle gelir; otomasyonlu ekipmanda **kırmızı çizgi adayı**
- Mühendislik yazılımı lisansı devri
- Üretilen ürüne ilişkin gizlilik

### 13. İSG, çevre, saha ve montaj sorumlulukları

- İSG sorumluluğu ve uzman bulundurma; iş kazasında sorumluluk paylaşımı
- **SGK işyeri dosyası kim adına açılacak**; alt yüklenici SGK bildirimleri
- **Çalışan tesis içinde iş yapılıyorsa:** çalışma saatleri, sıcak çalışma izni,
  hijyen/gıda güvenliği kuralları (üretim tesislerinde kritik)
- **Vinç/iskele/enerji/su kimden, saha hazırlığı kimin sorumluluğunda** — kapsam
  boşluğunun en sık kaynağı
- Atık yönetimi ve çevre izinleri

### 14. Ara yüz ve sorumluluk matrisi

- Birden fazla yüklenici varsa (betonarme ayrı, çelik ayrı, ekipman ayrı): ankraj
  aplikasyonu, tolerans uyuşmazlığı, süre bağımlılığı kimde — **sorumluluk matrisi
  sözleşme eki** olarak önerilir

### 15. Uyuşmazlık ve uygulanacak hukuk

- Yetkili mahkeme/tahkim ve yeri; **yabancı firma tekliflerinde yurt dışı tahkim maddesi**
  maliyet ve süre açısından değerlendirilir
- Teknik uyuşmazlıkta bilirkişi/hakem mekanizması
- Sözleşme dili ve çelişki hâlinde hangi dilin esas alınacağı

### 16. Devir ve alt yüklenici

- Sözleşme devri ve alt yüklenici kullanımı işveren/alıcı onayına bağlı mı; onaysız alt
  yüklenici yasağı

## Çıktı kuralları

### Gerekçeli önerinin rapora aktarımı

Teminat, sigorta ve ceza için önce **gerekli / gerekli değil / bilgi bekleniyor**
sonucunu gerekçesiyle belirle. Gerekli olanları PDF'te ayrı alt başlıklarla ayrıntılandır:
**mevcut teklif koşulu ve kaynağı → somut risk → önerilen araç/madde → oran/matrah ve
parasal tutar → süre/başlangıç-bitiş → gerekçe → uygulama/teyit adımı**.
Bir firmanın daha zayıf koşulu varsa firma bazında etkisini göster. Üçü de düşük
riskli alımda gerekmiyorsa kısa açıklama yeterlidir; boş uzun bölümler açma.

Tutar önerisi için veri yeterliyse **sayısal tutarı mutlaka hesapla**. Veri yetersizse
dayanaksız kesin tutar belirtme: eksik girdiyi/RFI muhatabını, formülü ve varsa açıkça "varsayımsal
senaryo" etiketli hesabı ver. Her oran ve sürenin kaynağını **teklif/şartname, şirket
kuralı, doğrulanmış mevzuat veya gerekçeli ticari öneri** olarak ayır. Hiçbir varsayılan
yüzde/süreyi yasal zorunluluk gibi sunma. Hukuki zorunluluk veya güncel mevzuat iddiası
gerektiğinde ilgili ülkenin güncel resmi kaynağını doğrula, kaynak ve tarihini yaz;
doğrulanamıyorsa teyit bekliyor de. Özel sektör alımına kamu ihale oranlarını otomatik
uygulama. Nihai madde/mektup için hukuk, poliçe kapsamı ve limit için sigorta uzmanı
teyidini ilgili belirsizliğe bağla.

- Şartnameyle çelişen her madde **"Uymayan Noktalar" sekmesine de** yazılır; sadece
  sözleşme sekmesinde kalmaz.
- Riskli maddeler için Karar Özeti'ndeki **KIRMIZI ÇİZGİLER** listesine karşılık madde
  önerilir. Örnekler: "cezai şart üst limiti işin riskine göre gerekçelendirilecek", "avans teminat mektubu
  verilecek", "teminat iadesi SGK ilişiksizlik belgesine bağlı", "ödeme esası teorik
  tonaj", "yeni fiyat prosedürü sözleşmeye yazılacak", "PLC şifresi teslim edilecek",
  "kabul devreye alma ile gerçekleşir".
- Bir firmanın teklifinde **hiç genel şart ekli değilse** bu "belirtilmemiş" olarak
  işaretlenir ve sözleşme aşamasında işveren/alıcı lehine düzenlenebilir bir alan olarak
  not edilir — **bu bir avantaj olabilir, eksiklik olarak puanlanmaz.**
