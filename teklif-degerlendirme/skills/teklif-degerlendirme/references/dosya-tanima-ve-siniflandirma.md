# Dosya Tanıma, Okuma ve Sınıflandırma

Kullanıcının dosya türünü ayrıca belirtmesi gerekmez. **Dosyaların işlevi ve ilgili
alım türü içeriklerinden belirlenir.** Bu referans, dosya tanıma ve sınıflandırma
yöntemini tanımlar. Otomatik çıkarıcı PDF/XLSX/DOCX/EML/metin için ilk geçiş sağlar;
diğer biçimler desteklenmiş gibi sayılmaz. Uygun araç yoksa okunamadı ve RFI kaydı
açılır. Yeni kütüphane kurulumu burada yapılmaz; ortam guncelleyici ile yönetilir.

Sıra: **(1) biçime göre oku → (2) her dosyayı rolüne göre sınıflandır → (3) alım dalını
tespit et → (4) envanter tablosunu kullanıcıya göster.**

## 1. Biçime göre okuma

| Biçim | Yol | Notlar |
|---|---|---|
| PDF (metin katmanlı) | `pdfplumber` ile metin + tablo | Her PDF ayrı `.txt`'ye yazılır; ana bağlam şişmesin |
| PDF (taranmış / metin yok) | sayfayı görsele çevir (`pypdfium2`) → **görsel olarak oku** | Özgün sayfayı görsel olarak incele; otomatik metin yoksa bunu kaydet |
| XLSX / XLSM | `openpyxl` (`data_only=True` ile değerler, `False` ile formüller) | Gizli sayfa ve gizli satır/sütun kontrolü şart — iskonto ve alternatif fiyat orada saklı olabilir |
| XLS (eski) | Mevcut Excel ile salt okunur aç; gerekiyorsa çalışma kopyasını XLSX'e çevir | Açılmıyorsa kullanıcıdan XLSX ister |
| CSV | ayırıcıyı tespit et (`;` Türkçe Excel'de yaygın), `utf-8-sig` dene | Bozuk Türkçe karakter → kodlama denemesi: utf-8, cp1254, iso-8859-9 |
| DOCX | OOXML (`word/document.xml`) tercih edilir | `python-docx` **kabul edilmemiş değişiklik izlemeyi (redline) sessizce düşürür**; teklif/şartname redline içeriyorsa OOXML'den oku |
| DOC (eski) | metin çıkarımı denenir; olmazsa kullanıcıdan DOCX/PDF ister | |
| JPEG / PNG / HEIC / WEBP | **doğrudan görsel olarak oku** (asıl yol) | Telefonla çekilmiş teklif, el yazısı fiyat, imzalı teklif mektubu, kaşe, teknik çizim. Okunan her değer "görselden okundu" kaynağıyla işaretlenir |
| MSG / EML | gövde ve ekler uygun yerel araçla ayrı okunur | Fiyat çoğu zaman mailin gövdesindedir, ekte değil. Ek varsa ek ayrıca sınıflandırılır |
| ZIP / RAR | açılır, içindekiler yeniden sınıflandırılır | Yol kaçışı/bağlantı içermeyen üyeler kontrollü çalışma alanına açılır; özgün arşiv hash'i korunur |
| DWG / DXF / IFC | **okunmaz** | Kullanıcıya bildirilir: "çizim dosyası okunamadı, PDF çıktısı gerekiyor". Sessizce yok sayma |

**Görselden okumanın kuralı:** görselden okunan hiçbir sayı doğrulanmadan toplama girmez.
Firmanın kendi beyan ettiği **genel toplamla** çapraz kontrol edilir; tutmuyorsa hücre
"görselden okundu — teyit gerekiyor" olarak işaretlenir ve RFI'ya yazılır. El yazısı
rakamlarda ve düşük çözünürlükte bu kural katıdır.

**Veri kaybı kontrolü (her dosya için):** sayfa sayısı, tablo sayısı, görsel sayısı,
**boş-metinli sayfa sayısı**. Boş metinli sayfa varsa o sayfa görsel olarak okunur.
Büyük görseller (>40.000 px²) ayrı ayrı incelenir: teknik çizim mi, keşif tablosu mu,
fiyat tablosu mu, logo mu.

## 2. Rol sınıflandırması

Her dosya şu rollerden uygun olanlarına atanır. Karar dosya adına değil, **ilk sayfanın
içeriğine** dayanır — dosya adları güvenilmezdir.

| Rol | Sinyaller |
|---|---|
| **Teklif** | firma antetli/kaşeli, "fiyat teklifi", "teklif mektubu", teklif no + tarih, geçerlilik süresi, ödeme koşulu, birim fiyat tablosu, KDV ibaresi |
| **Teknik şartname** | "teknik şartname", "spesifikasyon", madde numaralı zorunluluk dili ("olacaktır", "sağlanacaktır", "asgari"), standart atıfları (EN/ISO/API/ASME/TS), idare/işveren antedi |
| **Keşif / metraj cetveli (BoQ)** | poz no + tanım + birim + miktar sütunları, fiyat sütunu **boş** veya idare tahmini |
| **Proje / çizim** | ölçekli çizim, antet paftası, plan/kesit/görünüş, statik hesap raporu |
| **Yazışma** | mail zinciri, RFQ metni, soru-cevap, zeyilname bildirimi |
| **Referans/belge** | ISO/CE/EN 1090 sertifikası, iş bitirme, kapasite raporu, banka referansı, katalog |
| **Alakasız** | fatura, sunum, logo, kişisel dosya |

**Ayrım tuzakları**
- Aynı firmadan **birden fazla revizyon**: teklif no/tarih/revizyon karşılaştırılır, yalnız
  **en son revizyon** değerlendirilir, eskisi "değerlendirme dışı" notuyla listede kalır.
- Bir dosyada **hem şartname hem keşif** olabilir (birleşik ihale dosyası) → iki rol
  birlikte atanır.
- Katalog, teklif değildir; fiyat içermeyen teknik doküman teklif sayılmaz.
- Firma teklifinin ekindeki **genel satış şartları** ayrı bir belge gibi görünür ama o
  teklifin parçasıdır — sözleşme maddeleri analizinin girdisidir.

## 3. Alım dalının tespiti

Sinyaller içerikten toplanır; **iki dal aynı işte birlikte olabilir** (ekipman + betonarme
temel + çelik platform tipik). Birden çok dal tespit edilirse ilgili tüm referans dosyaları
okunur ve tek KTM zinciri kurulur.

| Dal | Tipik sinyaller |
|---|---|
| **İnşaat / yapım işi** | poz, keşif, metraj, m³ beton, C25/C30, donatı kg, kalıp m², tonaj, S235/S275/S355, EN 1090, EXC sınıfı, hafriyat, kalıp-iskele, hakediş, mobilizasyon, sandviç panel m², götürü bedel / birim fiyatlı ayrımı |
| **Makine / ekipman** | kapasite (ton/h, adet/h, m³), kW, debi/basma yüksekliği, Incoterms (EXW/FOB/CIF/DAP/DDP), CE, PED, ATEX, FAT/SAT, devreye alma, garanti/servis, yedek parça listesi, motor verim sınıfı, PLC/SCADA |
| **Genel mal / hizmet alımı** | yukarıdakilerin hiçbiri baskın değil: sarf malzeme, ambalaj, kimyasal, hizmet (nakliye, temizlik, bakım, danışmanlık, yazılım), kiralama, araç, mobilya | 

Dal belirlenemiyorsa **`dal-genel-mal-hizmet.md`** ile "genel mod"da yürü — ortak omurga
(kapsam eşitliği, KTM, ticari koşullar, risk, puanlama) her alımda geçerlidir; dala özgü
teknik kontrol listesi okunmaz ve bu Özet'te belirtilir. **Alım dalı dayanaksız olarak belirlenmez:** makine
kontrol listesi bir temizlik hizmeti alımına uygulanmaz.

## 4. Envanter tablosu (analizin ilk çıktısı)

Sınıflandırma bitince, analize başlamadan önce kullanıcıya şu tablo gösterilir:

| Dosya | Biçim | Rol | Firma | Okunabildi mi | Not |
|---|---|---|---|---|---|

Ardından tek paragrafla: kaç teklif var, şartname var mı, keşif var mı, tespit edilen dal
ne, okunamayan dosya var mı. **Yanlış sınıflandırmayı en hızlı kullanıcı yakalar** — bu
tablo onun için vardır.

Bu tablo Excel'de de bir satır grubu olarak Özet sekmesine girer (hangi dosyadan hangi veri
geldi — izlenebilirliğin başlangıcı).
