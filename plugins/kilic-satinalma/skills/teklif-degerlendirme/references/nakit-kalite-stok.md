# Nakit ihtiyacı, kalite kayıpları ve sipariş/stok senaryoları

Üç hesap koşulludur: ödeme takvimi varsa nakit tablosu; kalite kaybı karar açısından
anlamlıysa kalite tablosu; tekrarlayan tüketim veya toplu alım seçeneği varsa stok
senaryosu kurulur. İlgisiz modül için gerekçe yazılır. Veri eksikliği, uygulanmama
gerekçesi değildir: **hesaplanamadı / kısmi hesap / senaryo** olarak gösterilir.
Tek teklif modunda da çalışırlar; rekabet puanlaması gerektirmezler.

## 1. En yüksek nakit ihtiyacı

**Girdi:** ödeme ve teslim tarihleri, avans, net hakediş, satıcı/vergi dairesine KDV
ödemeleri, banka gideri, depozito/bloke, iade ve gerçek nakit girişleri. Varsa alıma
tahsisli başlangıç nakdi, tarihli nakit tahsisleri ve kullanılabilir kredi limiti.
Şirketin bütün nakit planı yoksa şirketin ödeme gücü hakkında hüküm verilmez.

Gün/tarih bazında kur; uzun işte aylık özet ekle. Aynı gün işlemlerinin sırası önemli
ama bilinmiyorsa çıkışların önce olduğu ihtiyatlı senaryoyu göster. Ay içindeki
tepeyi aylık netleştirme gizleyebilir. **Tutarlar nominaldir, iskonto edilmez.**

```
net çıkış_t = gerçek ödeme_t − gerçek nakit girişi_t
kümülatif net çıkış_t = önceki kümülatif net çıkış + net çıkış_t
en yüksek tek dönem ödemesi = MAX(dönemlerin brüt ödemeleri)
en yüksek birikimli nakit ihtiyacı = MAX(0, MAX(kümülatif net çıkış))

finansman öncesi bakiye_t = başlangıç tahsisli nakit
                         + bugüne kadarki ek nakit tahsisleri
                         − kümülatif net çıkış_t
ek finansman ihtiyacı_t = MAX(0, −finansman öncesi bakiye_t)
en yüksek ek finansman ihtiyacı = MAX(ek finansman ihtiyacı_t)
```

- Başlangıç/tahsisli nakit bilinmiyorsa ilk iki tepe hesaplanır; şirketin finansman
  açığı hesaplanmış sayılmaz. Kredi çekişi açığı kapatıyorsa **finansman öncesi**
  açık saklanır; kredi girişiyle açığı sıfırlayıp finansman ihtiyacı yok denmez.
- KDV mahsubu bankaya para girişi değildir. Teyitli mahsup, ilgili vergi ödemesini
  azaltır; aynı tutar ayrıca nakit girişine yazılmaz. Devreden KDV, sırf indirim hakkı
  var diye belli tarihte tahsil edilecek tutar kabul edilmez.
- Döviz için ayrı para birimi tablosu ve ödeme tarihindeki kur senaryolarıyla TL
  karşılığı gösterilir. Bugünkü kurla hesaplanan TL tutarı garanti ödeme bütçesi değildir.
- Depozito/bloke çıkışı nakit tablosunda tam tutardır; KTM'de yalnız net ekonomik
  etkisi vardır. Teminat mektubu nominal tutarı fiili nakit blokajı değilse çıkış değildir.
- KTM ile aynı kaynak kayıtlarından beslenir; **nakit açığı veya tepe ödeme KTM'ye
  ilave maliyet olarak eklenmez**, puanda ikinci fiyat kriteri yapılmaz. Teyitli
  finansman sınırını aşan teklif koşullu önerilir; limit yoksa limit uydurulmaz.

**Kontrol örneği:** tarihler sırasıyla 300, 400, 200 ödeme; daha sonra 150 iade.
Tek dönem tepe ödeme **400**, birikimli ihtiyaç **900**, son net çıkış **750**.
Başlangıç tahsisli nakit 500 ise en yüksek ek finansman ihtiyacı **400**.
Özet'te tepe tutar **ve tarihi**, en büyük ödeme dönemi, varsa limit aşımı görünür.

## 2. Kalite kayıpları ve ilave kontrol maliyeti

**Girdi:** aynı ürün/proses için izlenebilir hata/iade oranı, örneklem ve dönem,
kontrol/ayıklama gideri, yeniden işleme başarı oranı ve bedeli, ikame alım, taşıma,
bertaraf, tedarikçi tazmini ve bunların tarihleri. Garanti beyanı ile gerçekleşmiş
performans ayrılır. Oran yoksa firma için keyfi hata oranı veya sıfır kayıp yazılmaz.

Kalitesizlik maliyeti (hata sonucu) ile rutin kontrol/önleme gideri ayrı satırlardır.
Teklif nedeniyle artan kontrol maliyeti de alım kararına girer; bütün tekliflerde
aynı olan ve alımla değişmeyen dağıtılmış genel gider fark yaratmaz.

```
kusurlu miktar = gelen miktar × teyitli kusur oranı
kusurlu miktar = yeniden işlemeye ayrılan + doğrudan iade/hurda edilen
kullanılabilir miktar = ilk seferde uygun miktar
                     + başarılı yeniden işleme miktarı
                     + zamanında gelen uygun ikame miktarı
ilave kalite gideri = kontrol/ayıklama + yeniden işleme + ilave taşıma/bertaraf
                   + henüz alım bedeline girmemiş ikame gideri
                   + dayanaklı diğer kayıplar − teyitli tazmin/iade
```

- Başarısız yeniden işleme, iade/hurda akışına aktarılır; aynı ürün iki sonuca birden
  sayılmaz. Bedelsiz ikame, satın alınmış ikame ve para iadesi ayrı seçeneklerdir;
  sözleşme gerçekten ikisini vermiyorsa hem iade hem bedelsiz yenisi varsayılmaz.
- **Miktar modeli seçilir:** fire nedeniyle sipariş zaten artırılmışsa kayıp malın
  alış bedeli alım toplamındadır; tekrar hurda alış maliyeti eklenmez. Bunun yerine
  tek sipariş + ikame modeli kullanılıyorsa ikamenin yalnız yeni giderleri eklenir.
  Yeniden işlenen ürün kullanılabilir çıktıya dönüyorsa otomatik fire sayılmaz.
- Duruş/üretim kaybı TCO'da varsa buradan yalnız bağlantı verilir. Teyitli iade
  kendi tarihinde negatif akıştır; belirsiz tazminat baz maliyeti azaltmaz.
- KTM'ye bağlanan değer **yeni ve benzersiz giderlerin NBD'si**dir: tek seferlik
  alımda kapsam/maliyet düzeltmesine, tekrarlayan işletme kaybında TCO'ya bağlanır.
  Aynı kalem iki basamağa girmez. Kullanılabilir birim maliyeti = bütün ilgili
  maliyetler / aynı ihtiyaca uygun çıktı; teslim tarihine kadar yeterlilik ayrıca kontrol edilir.

**Kontrol örneği:** 1.000 adet × 10 TL; 40 kusurlunun 20'si başarıyla yeniden işlenir,
20'si iade edilip 20 uygun adet ücretli ikame alınır. Kontrol 100, yeniden işleme 40,
iade taşıması 30, ikame 200, teyitli ürün bedeli iadesi 200 TL.
Uygun çıktı **960 + 20 + 20 = 1.000**, nominal toplam **10.170 TL**, birim **10,17 TL**.
İlave kontrol/önleme ve hata giderlerinin ayrımı tabloda korunur. Bunlar örnek verilerdir.

## 3. Sipariş sıklığı ve stok maliyeti

**Aynı ihtiyaç ve analiz dönemi** için en az iki uygulanabilir senaryo: toplu alım,
kademeli/aylık teslim veya kullanıcıdaki seçenekler. Sipariş verme, teslim alma,
mülkiyet/risk devri ve ödeme aynı tarih olmak zorunda değildir; yıllık sözleşme +
aylık teslim, yıllık peşin alımdan ayrı senaryodur.

**Girdi:** dönemlik tüketim planı, başlangıç kullanılabilir stok, parti/paket/MOQ,
teslim süresi, emniyet stoğu, fiyat kademeleri, sipariş/teslim başına ek gider,
depolama tarifesi/kapasitesi, raf ömrü, bozulma ve ödeme planı.

```
dönem sonu stok = dönem başı stok + kullanılabilir teslim − tüketim − stok kaybı
ortalama stok = Σ(stok seviyesi × o seviyede geçen süre) / toplam süre
sipariş gideri = gerçek sipariş adedi × sipariş başına ek gider
teslim gideri = gerçek teslim adedi × teslim başına ek gider
depolama = dönem bazında stok/palet/alan × ilgili süre ve birim tarife
```

- `Q/2 + emniyet stoğu` yalnız düzenli tüketim, eşit partiler, anlık ikmal ve stok
  tükenmemesi koşullarında ortalama stok yaklaşımıdır. Mevsimsellik, raf ömrü veya
  büyük dönem sonu artığı varsa tarih bazlı stok tablosu kullanılır. Gerçek sipariş
  sayısı tam sayıdır; `yıllık tüketim/Q` kesirli sipariş sayısı olarak fiyatlanmaz.
- Negatif stok karşılanmayan ihtiyaçtır. Kapasite/raf ömrü aşılan, gerekli tarihte
  mal sağlamayan seçenek ucuz diye önerilmez; bölünmüş teslim/ikameyle düzeltilip
  gideri yeniden hesaplanır. Kalite kaybı ve stokta bozulma aynı kayıpsa tek sayılır.
- Senaryo maliyeti: net alım + benzersiz sipariş/teslim/depolama/bozulma giderleri
  − gerekçeli dönem sonu stok değeri. Ödeme tarihlerinden **NBD** ve §1 nakit
  tepesi ayrıca bulunur. Başlangıç/son stok bütün senaryolarda aynı esasa getirilir;
  sırf fazla stok aldı diye bunun tamamı tüketilmiş maliyet sayılmaz.
- Genel stok taşıma oranı sermaye maliyeti içeriyorsa bileşenleri ayrılır: KTM
  ödeme NBD'siyle kurulurken aynı stok için sermaye maliyeti tekrar eklenmez.
  Nakit kira, sigorta, elleçleme gibi ilave fiili giderler kendi tarihlerinde eklenir.
  Bozulmadan doğan ek satınalma zaten miktara girdiyse kayıp alış bedeli tekrar eklenmez.
- Dağıtılmış sabit personel/depo gideri satınalma seçeneğiyle değişmiyorsa tasarruf
  sayılmaz; gerçek ek gider veya dayanaklı kapasite fırsat maliyeti ayrı gösterilir.

**Kontrol örneği:** yıllık sabit tüketim 12.000, başlangıç/son stok ve emniyet stoğu 0;
birim fiyat 10 TL; sipariş ve teslim birlikte 200 TL/parti; sermaye maliyeti hariç
depolama 1 TL/adet-yıl. Yıl başında tek teslim: ortalama stok 6.000, nominal
toplam **126.200 TL**. Her ay başında 1.000 teslim: ortalama stok 500, 12 sipariş,
nominal toplam **122.900 TL**. Toplu alıma %5 iskonto verilirse **120.200 TL** olur;
bu nominal avantajdır, karar ödeme NBD'si, raf ömrü ve nakit sınırıyla birlikte verilir.

## 4. Çıktı ve son kontrol

Excel'de koşullu üç sekme: **Nakit İhtiyacı**, **Kalite Maliyeti**, **Sipariş ve Stok**.
Karar Özeti'ne tepe nakit+tarih, kullanılabilir birim maliyeti, seçilen sipariş/teslim
planı, senaryoların KTM farkı ve veri eksiklikleri formülle bağlanır. Puan tablosu
varsa maliyet fiyat kriterine bir kez yansır. Her yeni gider aynı zamanda nakit
takvimine kendi tarihi ve vergi rejimiyle bağlanır. Takvim eksikse tepe kesinleştirilmez.

Girdi sınırları: miktar ve gider matrahları negatif olamaz; kusur/başarı oranları
0–1 arasındadır. Yeniden işleme ve doğrudan iade/hurda toplamı kusurlu miktarı
geçemez. Net ihtiyaç > 0 iken kullanılabilir çıktı 0 ise birim maliyet bölmesi
kurulmaz. Talep 0 ise gereksiz alım senaryosu yaratılmaz. Tarih eksikliği ve
aynı gider kimliğinin iki kez kullanılması görünür hata/RFI olur.

Doğrulama: miktar akışları mutabık mı; nakit tepe son toplamla karışmış mı; iadeler
iki kez düşülmüş mü; sipariş/teslim sayısı ayrılmış mı; depolama süresi ve birimi
uyumlu mu; sınırı aşan senaryo öneriliyor mu; KTM'de aynı gider iki kez var mı?

Yöntem kaynakları (2026-09-05 kontrolü):
[ASQ kalite maliyetleri](https://asq.org/quality-resources/cost-of-quality) kontrol/önleme
ve hata giderlerini ayırır.
[ACCA stok kontrolü](https://www.accaglobal.com/middle-east/en/student/exam-support-resources/fundamentals-exams-study-resources/f2/technical-articles/stock-control.html)
sipariş büyüklüğünün sipariş ve stok tutma giderlerine etkisini ele alır.
[ACCA nakit bütçesi örneği](https://www.accaglobal.com/content/dam/acca/global/PDF-students/acca/ffm_2020_sep_a.pdf)
dönemsel bakiye ve açıkların görünür tutulmasını örnekler.
