# Excel ve PDF üretimi — v4

Tek kaynak merkezi veridir. Aritmetiği `teklif_motoru.py`, dosyayı
`excel_uret.py`, gerçek Excel hesap ve mutabakatını `excel_dogrula.py` yürütür.
Ana sohbet her koşuda yeni üretici veya COM otomasyonu yazmaz.

## Profilin sekme seti

Alan referanslarındaki eski sekme adları aşağıdaki tabloda ilgili içerik bloğuna
birleştirilir. Örneğin Fiyat Detayı, Eşit Kapsam ve Poz Bazlı Fiyat hızlıda
**Fiyat ve Kapsam** içindedir; Uymayan Noktalar **Bilgi Talepleri** ile ilişkilidir.
Sekme sayısını artırmak için boş tablo kurulmaz; uygulanmayan yöntem Özet'te gerekçelidir.

| İçerik / sekme | Hızlı | Standart | Yüksek güvence |
|---|---|---|---|
| Özet | Evet | Evet | Evet |
| Karar Özeti | Evet | Evet | Evet |
| Fiyat ve Kapsam | Evet | Evet | Evet |
| Bilgi Talepleri | Evet | Evet | Evet |
| Elemeli Değerlendirme | Özet'te | Ayrı | Ayrı |
| Ticari ve Sözleşme | Özet'te kısa | Ayrı | Ayrı |
| Şartname Uygunluğu | Özet/Bilgi Talepleri'nde sınır | Varsa | Varsa |
| Puanlama ve duyarlılık | Yok | Koşullar uygunsa küçük tablo | Koşullar uygunsa ayrı |
| Yeterlilik ve Risk | Karar Özeti'nde kısa | Karar Özeti'nde kısa | Ayrı |
| Uzman Teyidi | Yok | Yok | Ayrı; çözülemeyen konular ve muhatap |
| İthalat, finansman, toplam sahip olma, nakit, stok, kalite | Dört sekme içinde gerekli bilgi | Veri varsa koşullu | İlgiliyse ayrıntılı |
| Değişim Kaydı | Yeni teklif revizyonunda | Yeni teklif revizyonunda | Yeni teklif revizyonunda |
| PDF | İstenirse | İstenirse | Zorunlu |

Hızlıda ilk üretim dört çekirdek sekmedir. Standart tipik 7–8 sekmedir; veri ve
yöntemin gerektirdiği koşullu sekmeler eklenebilir. Yüksek güvencede tek tedarikçi
olması puan üretme yetkisi vermez. Tek tedarikçide “TEK TEKLİF — REKABET YOK”,
iki tedarikçide medyan/sapma yerine fark analizi vardır.

## İçerik değişmezleri

**Özet:** kaynak envanteri, belge no/tarih/revizyon, yaş ve geçerlilik, kapsam ve
maliyet zinciri; profil/seçim gerekçesi, kritik uyarılar, renk lejantı, veri/skill
sürümü. “Bu analiz teklif-degerlendirme <VERSION> ile üretilmiştir” damgası koddan gelir.

**Karar Özeti:** düzeltme sonrası yeni GPT-6.1/High karar özeti görevinin kaynaklı metni; uygunluk ve maliyet durumu; kırmızı
çizgiler, RFI/teyit sorumluları ve sonraki adımlar. Kritik bilgi açıkken kesin firma
önerisi bulunmaz. Profil düşürme ve yapılmayan kontrol açıkça yazılır.

**Fiyat ve Kapsam:** miktar × birim fiyat, iskonto, vergi zemini, kur, ödeme/vade,
5-A ve 5-B ayrı blokları, bilinen ara toplam ile nihai KTM ayrımı. Rayiç/tutar
bilinmiyorsa boş/FİYATLANMADI kalır; sıfır yapılmaz. Bedelsiz, kaynakla teyitli
kalemin gerçek birim fiyatı sıfır olabilir.

**Puan ve duyarlılık:** maliyet önce ortak zemine getirilir, elemeli kapı önce
uygulanır. Ağırlık toplamı 100 ve ölçek 0–10 görünürdür. Elenenler görünür ama
MIN/MAX/puan referansına girmez. KTM'de parasallaştırılan etki ikinci kez puanlanmaz.
Ayırt edici ağırlık oranı ve en az üç uygun duyarlılık senaryosu ilgili tabloda
gösterilir; standartta ayrı sekme zorunlu değildir.

**Ticari koşullar:** avans/teminat/hakediş/ceza/garanti/sözleşme riskleri kaynaklıdır.
Para birimi başına iskonto oranı ayrıdır; vadeli döviz TL oranına bağlanmaz.
TCO'nun nominal/reel akış ve oranı tutarlıdır; `r_reel=(1+r_nominal)/(1+enflasyon)-1`.
Nakit tepe KTM'ye eklenmez; kalite/stok gideri benzersiz olayla bir kez sayılır.

**RFI:** muhatap, açık konu, öncelik, kaynak, etki ve soru. Şartname istememişse
İDARE, firmalar cevap vermemişse ilgili firmalar; hepsinin eksikliği otomatik firma
kusuru değildir. Cevapsız sorular revizyonda korunur.

## Biçim ve formüller

- Arial; lacivert `1F3864` başlık/beyaz yazı; uzun metin sarılı, satır yüksekliği yeterli.
- Para `#,##0.00`, yüzde `0.0%`, tarih `dd.mm.yyyy`; sayıları metin yazma.
- Giriş/varsayım: sarı dolgu `FFEB9C`, mavi yazı `0000FF`.
- Uygun/dahil: yeşil `C6EFCE`; kısmen/belirtilmemiş: sarı; uygunsuz/hariç: kırmızı
  `FFC7CE`. Anlam yalnız renge bağlı değildir; metin etiketi de bulunur.
- Filtre ve dondurulmuş başlık; basılabilir alan/sayfa yönü; taşmayan sütunlar.
- Hesap sonucu formüldür; metin/RFI tablosuna yapay formül eklenmez. Parametre tek
  hücrede, bütün bağlı hesaplar bu hücreye referanslıdır.
- XLSX formülleri İngilizce fonksiyon/virgül ayırıcıyla saklanır. Türkçe Excel'in
  görünen noktalı virgülü dosya içine yazılmaz.
- `IFERROR` ile hesap kusurunu gizleme. Bilgi eksikse koşullu formül boş metin
  döndürebilir; boş metin ile eksik/bozuk sayısal önbellek ayrı değerlendirilir.

## Kaynaklar ve metin çıkarımı

Bütün profillerde kanıt düz metindir: “Kaynak 1 · sayfa/hücre” ve Kaynaklar
sekmesinde özgün dosya adı. Excel'de iç/dış köprü veya HYPERLINK formülü bulunmaz.

pdfplumber/pypdf metni özellikle dar/yatay/çok sayfalı tablolarda hata yapabilir.
Sayfa toplamlarını beyan edilen ara/genel toplamla kodla karşılaştır; farklılıkta
özgün sayfa görüntüsünü kontrol et. “6 65.000,00” gibi boşluğu kendiliğinden silme;
görsel ve toplamla doğrula. Boş metinli PDF sayfası pypdfium2 ile görüntülenir.

Kur kaynağında tutar × döviz satış / **Unit** hesaplanır; kaynak tarihi, kur türü ve
para birimi saklanır. Veri yoksa kullanıcıdan istenir, güncel kur tahmin edilmez.

## Gerçek Excel doğrulaması

openpyxl formül yazar, hesaplamaz. XML'e `<v>` enjekte etmek veya önbellek üretmek
doğrulama değildir; **elle formül önbelleği doldurulmaz**.

Sabit Python + pywin32 otomasyonu kendine ait görünmez Excel örneğinde, kaynak
çalışma kitabının kopyasıyla çalışır. Makro/bağlantı güncellemesi kapalıdır.
Tam yeniden hesaplama, formül hata taraması ve bağımsız motor sonucu mutabakatı
yapılır. Uygulanabilir parametre değiştirilir, bağımlı sonuç denetlenir, eski değer
geri konur ve yeniden hesaplanır. Son dosya hash'ine bağlı rapor saklanır.
Kullanıcının açık Excel'ine bağlanılmaz, Excel süreçleri topluca sonlandırılmaz.

Dosya sürümü/hash'i başına başarılı kontrol bir kez çalışır. Etkilenen veri
değişirse yeni dosya üretilir ve ilgili kontrol yenilenir. Excel yoksa “doğrulanamadı”;
uygun kayıtlı ön sonuç dışında doğrulanmış nihai teslim iddiası yoktur.
LibreOffice veya başka hesap motoruna sessiz geçiş yapılmaz.

Mekanik kontrol tüm profillerde formül/karakter/bağlantı, sütun/satır boyutu ve
kesik metin riskini kapsar. Yüksek güvencede **tüm sekmeler ve tüm PDF sayfaları**
gerçek görüntüden incelenir; dosya hash'i, sayfa/sekme ve somut bulgular kaydedilir.
Küçük önizleme yalnız sayfa envanteridir; uzun metinli ve yoğun tablolar okunabilir
ölçekte de kontrol edilir. Başlık kesilmesi, yalnız kalan tablo başlığı, anlamsız boş
sayfa, aşırı küçülmüş yazı ve taşma düzeltilmeden PASS verilmez.

## Türkçe gösterim ve firma adları

Sekme adı **Bilgi Talepleri**, konu kimliği **BT-001**; maliyet modülü
**Toplam Sahip Olma** olarak görünür. RFI/TCO/QA ve verified/missing gibi
makine alanları merkezi JSON'da kalır. Başlıklar, durumlar ve açıklamalar Türkçedir.
Yabancı dildeki kaynak ifadesinin Türkçe karşılığını göster; özgün alıntıyı merkezi
veride sakla. Döviz/standart kodlarını ve özgün kaynak dosya adlarını bozma.

Her firmaya kaynakla doğrulanmış tek açık ticari ad seç. Belirsizse kullanıcıya sor.
`--display-names <firma-adlari.json>` ile `{ "A": "Firma ticari adı" }`
eşlemesini üreticiye ver; aynı ad özet, risk, puan, nakit ve karar metninde kullanılır.
Bilinen İngilizce durumlar otomatik çevrilir; serbest metnin Türkçesi üretim öncesinde
kontrol edilir. Otomatik sözcük taraması dil kontrolünün tamamı değildir.

Doğrulanmış teklif toplamı, eşit kapsamlı maliyet hesaplanamasa da Özet'te
**Teklif tutarı** olarak döviz, KDV, kapsam ve kaynakla görünür. Bu tutarları
karşılaştırılabilir toplam maliyete veya firma sıralamasına kendiliğinden dönüştürme.
Karar metnini yapay sabit karakter satırlarına bölme; gerçek paragrafları koru.
Ayrıntı tablolarındaki bütün açık konu kimliklerini karar özetine tekrar dökme.

Görsel kayıt: `pdf_sha256`, `status: PASS`, tüm sekme adlarını içeren `sheets`,
1'den son sayfaya kadar `pages` ve her sayfa için
`observations: [{"page": 1, "sheet": "Özet", "finding": "Somut görsel gözlem"}]`.
Eksik sayfa/sekme gözlemi yüksek güvence kapısını geçmez.

## PDF ve sürüm

Yüksek güvencede PDF zorunludur; standart/hızlıda kullanıcı rapor isterse PDF üretilir.
Kod merkezi veriyi ve GPT-6.1/High hakem metnini birleştirir; rapor üretmek için yeni yorum
oturumu açılmaz. Mevcut otomasyonun PDF dışa aktarımı kullanılır.

PDF diskte var, boş değil ve açılabilir olmalıdır. Metin, Türkçe karakterler,
sonuç/ön sonuç ve sürüm damgası doğrulanır. Görsel kontrol kapsamı yukarıdadır.
PDF üretilemediyse çıktı teslim edilmiş gibi sunulmaz; engel ve eldeki ön çıktı belirtilir.

Adlandırma:
`<PROJE>_Teklif_Karsilastirma.xlsx`,
`<PROJE>_Teklif_Degerlendirme_Raporu.pdf`.
Revizyon `_v2`, `_v3`; kaynak dosya değiştirilmez. Dosya adı için ASCII/alt çizgi
tercih edilir; kaynak dosyanın Türkçe adı korunur. Geçici çalışma dosyası teslim
bağlantısına konmaz. PDF doğrulanmadan ara rapor metni temizlenmez.

## Üretim ve doğrulama komutları

```text
python "<skill>/scripts/excel_uret.py" --data "<merkezi-veri.json>" --output "<yeni-kitap.xlsx>" --profile standart --inventory "<envanter.json>" --qa "<qa.json>" --decision "<sol-karar.json>"
python "<skill>/scripts/excel_dogrula.py" --workbook "<yeni-kitap.xlsx>" --data "<merkezi-veri.json>" --profile standart --decision "<sol-karar.json>"
```

Yüksek güvencede `--profile yuksek_guvence`; PDF konumu gerekiyorsa doğrulayıcıya
`--pdf "<yeni-rapor.pdf>"` verilir. Üretici workbook yanında hesap/formül sözleşmesi
yazar; bu dosya kontrol girdisidir. Doğrulayıcı başarıda hesaplanmış kitabı aynı
çıktı yoluna yerleştirir ve **hash değişir**. Her iki komuta aynı ayrı karar
JSON'u verilir; `decision_sha256` ile son veri/karar/metin bağı doğrulanır. Bu nedenle koşudaki `workbook`,
`excel_receipt` ve varsa `pdf` kayıtlarını doğrulama tamamlandıktan sonra yap.
Üretilen makbuz yolunu kullan; dosya adına bakıp PASS varsayma.
