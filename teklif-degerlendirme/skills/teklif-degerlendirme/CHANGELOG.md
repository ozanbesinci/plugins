# Sürüm Geçmişi — teklif-degerlendirme

Bu skill satınalma personelinden gelen geri bildirimlerle sürekli geliştirilir.
Her değişiklik buraya tek satırla yazılır: **ne değişti + neden**.

Sürüm numarası kuralı: **büyük** (omurga değişti, çıktı yapısı değişti) ·
**küçük** (yeni kontrol listesi, yeni referans dosyası) ·
**yama** (düzeltme, ifade netleştirme).

---

## v4.0.5 — 2026-09-30 — başlangıçta oturum kontrolü

- Kullanıcı talimatıyla başlangıçtaki otomatik `guncelleyici` taraması ve sonuç bekleme kaldırıldı; ilk adım aktif oturumun GPT-6.1/High kontrolü oldu.
- Yanlış seçimde analiz bekler; her yeni kullanıcı yanıtında gerçek oturum tekrar okunur ve gerekirse uyarı tekrarlanır. Doğru model ve efor doğrulanınca sonraki analiz adımına geçilir.
- Salt okunur, ek paket ve ağ erişimi gerektirmeyen `oturum_kontrol.py` eklendi; kullanıcı beyanı veya başka oturum kaydı kontrolü geçmez.
- Kullanıcının açık yayın kararıyla kararlı dağıtıma alındı; 4.0.4'teki bütün ajanlar için GPT-6.1/High değişikliği bu yayına dahildir. Model, oturum ve koşu denetimlerinin 50 testi geçti; canlı teklif kabulü ayrı tutulur.

## v4.0.4 — 2026-09-30 — bütün ajanlarda GPT-6.1 / High (yerel, yayımlanmamış)

- Kullanıcının model/efor kararı uygulandı: ana koordinatör ve bütün alt roller `gpt-6.1-sol` / `high` kullanır; aile başına en yeni sürüm seçimi ve Terra/Medium çıkarımı kaldırıldı.
- Hazırlık ve görev başlangıcında ana model ile efor birlikte doğrulanır; koşu içinde farklı efora geçip geri dönülmesi de engellenir. Gerçek alt oturum model/efor denetimi korunur.
- Talimat, politika, rol çözümleyici, kurulum ve çalışma referansları aynı kurala bağlandı. Yerel doğrulama gerçek teklif kabulü veya yayın anlamına gelmez.

## v4.0.3 — 2026-09-28 — sohbet içi güncelleyici başlangıcı

- Güncelleyici başlangıcı masaüstü Work ve Codex sohbetindeki seçim akışına bağlandı; PowerShell seçim penceresi çağrısı kaldırıldı.

## v4.0.2 — 2026-09-27 — Excel ve PDF sunum düzeltmeleri

- Kullanıcının açık yayın kararıyla kararlı dağıtıma alındı. Uçtan uca canlı analiz kabulü, yayın durumundan ayrı tutuldu.

- Excel'deki tüm köprüler kaldırıldı; kaynak dosya ve sayfa bilgisi düz metne çevrildi.
- Türkçe durumlar, okunabilir konu adları ve tutarlı firma adları eklendi; iç kimliklerin kullanıcıya taşınması giderildi.
- Doğrulanmış teklif bedelleri, eşit kapsamlı maliyet hesabından ayrı olarak özete eklendi.
- PDF paragraf/sütun düzeni, bölüm başlıkları ve yinelenen tablo başlıkları düzeltildi; karar özetindeki tekrarlar azaltıldı.
- Yüksek güvence görsel kapısı tüm sekme ve PDF sayfalarını kapsayacak şekilde genişletildi.
- Boş puanlama kaydında doğrulayıcı hatası giderildi; Excel kaydı sonrasında sunum kontrolü eklendi.

## v4.0.1 — 2026-09-27 — başlangıçta güncelleyici devri

- Yeni teklif analizinin ilk adımı birleşik `guncelleyici` paneline devredildi. Panel kontrolü ve kullanıcı tarafından seçilen kurulumlar tamamlanmadan analiz başlamaz.
- Teklif skill'inin ayrı başlangıç ortam kontrolü ve sürüm sorgusu kaldırıldı; panel sonrası güncellenmiş skill talimatı yeniden okunur.

## v4.0.0 — 2026-09-26 — yerel canlı test adayı

- Üç kullanıcı seçimli profil eklendi: hızlı, standart, yüksek güvence; kapsam, çıktı ve bütçe buna bağlandı.
- Model kimliği sabitlemesi kaldırıldı; her yeni analizde gerçek katalogdan Sol/Terra ailesinin erişilebilir en yeni sürümü çözülür, fiili oturum modeli ve eforu doğrulanır.
- Yerleşik alt ajan akışı ve her görevde yeni dar oturum getirildi; CLI model çalıştırma, oturum devamı, Astra ve Jev görevleri kaldırıldı. Luna yasağı korundu.
- Teklif/şartname çıkarımı, özgün PDF'ten bağımsız kör okuma, kod karşılaştırması ve dar Sol hakem ayrıldı; hızlıda kritik sayfa görüntülerinin hedefli kontrolü kullanılır.
- Merkezi veri, muhataplı RFI, kaynak tamlığı ve kanıtlı düzeltme sözleşmesi eklendi; düzeltme sonrası etkilenen hesap/çıktı yeniden doğrulanır.
- Bütçe sayımı benzersiz oturumun son birikimli toplamı ve ana sohbet farkına çevrildi; alt ajanlar sayılır, bilinmeyen tüketim sıfır değildir.
- Profil bazlı Excel ve sabit Python + pywin32 yeniden hesaplama, bağımsız mutabakat ve geri alınan parametre testi eklendi; yüksek güvencede PDF zorunludur.
- Ortam Python 3.14 ve program-guncelle'nin sabit paket sürümleriyle hizalandı; Python/kütüphane kurulum dosyaları bu pakete gömülmez.
- Kaynakla teyitli sıfır fiyat kabulü ve bilinmeyen maliyet kaydı düzeltildi; geçerli boş metin formülü ile bozuk sayısal önbellek ayrıldı.
- Canlı kabul verisi kullanıcıdan gelecek. Bu kayıt performans veya canlı test başarısı iddiası değildir; GitHub yayını ayrı yetki gerektirir.

## v3.1.1 — 2026-09-21

- CLI devamlarında mantıksal `task_id` sabitlendi; coordinator ve reviewer sonuçları
  başarılı model dönüşünden sonra otomatik kaydediliyor. Elle mühür döngüsü yalnız
  yerleşik oturum yolunda kaldı.
- Dış model/ağ erişimi kaynak paylaşmadan ve koşu dizini oluşturulmadan önce sınanıyor;
  platform izni erkene alındı, ticari sır için yinelenen onay eklenmedi.
- Ctrl+C terminal durumu kurtarma makbuzuna dönüşüyor; kapanış yarıda kesilirse aynı
  komut yaşam döngüsü kaydını değiştirmeden kilit temizliğini tamamlıyor.
- Sol/high denetçi öncesine hash-bağlı yerel kalite kapısı eklendi. Unicode, kaynak
  konumu, formül önbelleği, SHA etiketi ve kırık dosya bağlantıları model turundan önce
  denetleniyor.
- Çağrı, revizyon, girdi/çıktı tokenı ve süre tavanları eklendi; dar Excel teslim
  kusurlarında tam konuşma bağlamını yeniden oynatma yolu kapatıldı.

## v3.1.0 — 2026-09-21

- Tek koordinatör, gerçek yerleşik oturum makbuzu, CLI olay/kullanım kaydı ve aynı
  oturumda hedefli revizyon eklendi; boş durum sorgularını ve tekrar bağlam yükünü azaltmak hedeflendi.
- Ön sonuç ve kesin karar kapıları ayrıldı; kritik belirsizlikler kritik kalır,
  UNVERIFIED korunur ve tamamlanma/iptal durumu kalıcı kaydedilir.
- Kaynak listesi, koşuya özel kilit, değişmez skill snapshot'ı ve denetçiye özel
  yazma alanı eklendi; değişmeyen kanıt tekrar çıkarılmaz, kör inceleme önce kaydedilir.
- Standart veri/Excel üreticisi ve tekrar kullanılabilir kontroller eklendi.
- Mevcut izinli OpenAI analiz rolleri arasında ticari veri işleme için yinelenen
  koordinatör/denetçi onayları kaldırıldı; dış paylaşım ve platform izin sınırları korundu.
- Güncelleyici bağımsız v1.0.0 hattına ayrıldı. Şema 2 paketi bileşen sürümlerini
  ayrı taşır; doğrulanan yeni kurulum eski iki ağacı tamamen değiştirir, artıkları siler.
- GitHub'a yayın/yükleme öncesinde ayrıca kullanıcı onayı zorunlu; yerel geliştirme
  yayının tamamlandığı anlamına gelmez.

## v3.0.1 — 2026-09-20

- Ana ajan Sol/high, uzmanlar Terra/medium-high, bağımsız denetçi Sol/high ve
  yalnız kritik uyuşmazlıkta Astra/high olacak şekilde rol/efor politikası eklendi.
  Luna bütün roller, yedek yollar ve yeniden denemelerde devre dışıdır.
- Bağımsız ham kaynak incelemesi ve sürüme bağlı nihai teslim kontrolü zorunlu oldu;
  kritik açıkta yalnız ÖN SONUÇ ve bilgi talebi sunulur.
- Mevcut satınalma kuralları korunarak aşamalı referanslara ayrıldı. Deterministik
  hesaplar ve kontroller tekrar kullanılabilir Python araçlarıyla desteklendi.
- Aynı sürümde ana skill ve `teklif-degerlendirme-guncelle` birlikte paketlenir;
  GitHub Release tabanlı kontrol/güncelleme, dosya bütünlüğü ve işlem kilitleri eklendi.
- Kaynak veya yöntem revizyonunda bağımlı sonuç ve kontroller geçersiz olur;
  rol sayısı sabit ajan sayısı değildir, eşzamanlı alt ajan sınırı üçtür.
- Sürüm numarası doğrudan 3.0.1 olarak belirlendi; 3.0.0 yayımlandığı varsayılmaz.
- Windows'ta Türkçe ve emoji içeren yollar ile araç çıktıları için UTF-8
  giriş/çıkış sözleşmesi ve regresyon testi eklendi.

Doğrulama kayıtları dağıtımın yanında tutulur. Sentetik/birim testleri gerçek satınalma
vakası, canlı model uçları veya çevrimiçi yayın başarısı yerine geçmez.

---

## v2.0.3 — 2026-09-07

- Yerel çıktıların kurumsal senkronlu klasörlere yazılmasını engelleyen genel kısıtlama
  kaldırıldı. Kullanıcının belirttiği çıktı konumu esas alınır; konum belirtilmezse
  kaynak klasörün yanındaki `analiz/` klasörü kullanılır.
- Sürüm geçmişindeki kişisel, birinci tekil şahıs ve gündelik anlatımlar nesnel,
  kurumsal ifadelerle değiştirildi. Teknik içerik ve önceki sürümlerin karar gerekçeleri
  korundu.

---

## v2.0.2 — 2026-09-06

- Markdown dokümanlarındaki kişisel talep ve sohbet anlatımları resmî, nesnel
  ifadelere dönüştürüldü; değişikliklerin teknik kapsamı ve tarihçesi korundu.
- Doküman ve raporlar için kurumsal dil standardı tanımlandı. Oluşturucu bilgisi
  ve script ile üretilen standart başlangıç mesajı korundu.

---

## v2.0.1 — 2026-09-06

- Skill başlangıcına oluşturucu bilgisi eklendi.
- Yeni `scripts/baslangic_mesaji.py`, satınalma çalışanlarına yönelik oluşturucu
  mesajını üretir. Her yeni analizde script çalıştırılır ve çıktısı kullanıcıya görünen
  ilk sohbet mesajına aynen aktarılır; devam sorularında tekrarlanmaz.
- Script ek bağımlılık gerektirmez; UTF-8 çıktı ile Türkçe karakterleri korur.

---

## v2.0 — 2026-09-06

**Rapor teslim standardı ve risk açıklamaları güncellendi.**

- Mevcut tetikleyiciler korundu; teklifleri incele/analiz et/karşılaştır, en uygun
  teklifi ver, tekliflere bak ve benzer satınalma ifadeleri tanıma eklendi.
- Rapor uzunluğu mal/hizmetin içeriği, durumu ve riskine göre değişir; sabit sayfa
  sayısı veya her başlığı doldurma zorunluluğu yoktur.
- Gerektiğinde avans/kesin teminat için tutar, matrah, süre, çözülme ve gerekçe;
  sigorta için tür, bedel/olay başına ve toplam limit, muafiyet, süre ve gerekçe;
  ceza için oran/tutar, matrah, başlangıç, dönem, tavan ve gerekçeli senaryo istenir.
- Teklif hükmü, mevzuat/şirket kuralı ve ticari öneri ayrılır; sabit yüzde dayatılmaz.
  Eksik girdide rakam uydurulmaz. Teminat/limit, komisyon/prim ve ceza tahsilatı ayrılır.
- **Nihai rapor PDF'tir; doğrulama sonrası yalnız oluşturulan ara rapor `.md` silinir.**
  PDF başarısızsa ara dosya korunur; kaynak belgeler ve skill notları silinmez.
  Çıktı sözleşmesi değiştiği için ana sürüm artırıldı.

**Doğrulama kapsamı:** yönerge tutarlılığı, skill biçimi ve dağıtım paketi kontrolü;
bu değişiklik mevcut teklif PDF'ini yeniden üretmez ve buluta yükleme yapmaz.

---

## v1.8 — 2026-09-05

**Nakit ihtiyacı, kalite ve stok maliyetine ilişkin üç koşullu hesap modülü eklendi.** Yeni referans:
`references/nakit-kalite-stok.md`. Mevcut maliyet köprüsüne bağlanır; toplam maliyet
zincirine mükerrer bir basamak eklenmedi.

- **Nakit İhtiyacı:** tarih bazında nominal ödemeler; en yüksek tek dönem ödeme,
  birikimli ihtiyaç ve tepe tarihi. Alıma tahsisli nakit biliniyorsa ek finansman
  açığı/limit kontrolü. NBD ile karıştırılmaz; KDV mahsubu nakit girişi sayılmaz.
- **Kalite Maliyeti:** kusurlu, yeniden işlenen, iade/hurda ve ikame miktar dengesi;
  ilave kontrol, ayıklama, yeniden işleme, iade taşıması ve teyitli tazminler.
  Kullanılabilir çıktı başına maliyet; mevcut fire/ikame/TCO gideri tekrar eklenmez.
- **Sipariş ve Stok:** toplu alım, aylık/kademeli teslim; tüketim-stok dengesi,
  sipariş/teslim sayıları, MOQ, raf ömrü, kapasite ve depolama gideri. Nominal bütçe,
  NBD ve nakit tepesi yan yana. Stok sermaye maliyeti NBD'nin üstüne tekrar eklenmez.
- Üç koşullu Excel sekmesi ve Karar Özeti bağlantıları tanımlandı. Eksik parametreler
  Adım 0 sorularına, hesaplar Adım 5i'ye, kontroller Adım 11/19'a eklendi.
- ASQ/ACCA yöntem kaynakları referansa işlendi; sayısal örnekler sentetiktir.

**Doğrulama:** 11 yeni test, toplam **37/37** geçti. Geç iadenin nakit tepesini
azaltmaması, ay içi netleştirmenin tepeyi gizlemesi, kalite miktar dengesi, toplu
indirimle nominal sıralama değişimi ve vade etkisiyle NBD sıralamasının tersine
dönmesi kontrol edildi. Yeni modüller gerçek alım verisiyle veya bulut uçlarında
henüz sınanmadı; örnek testleri gerçek satınalma onayı değildir.

---

## v1.7 — 2026-09-05

**Satınalma yönetimi ve personelinin kullanımına yönelik hesap denetimi.** Mevcut
KTM/Excel/rapor akışı korundu; karar sırasını bozabilecek hesap ve yorumlar düzeltildi.

- **Ortak miktar:** %5 altındaki farklar da eşitlenir; eşik sadece uyarıdır. Götürü
  toplam doğrusal ölçeklenmez. Kantar farkı otomatik %3-7 artırılmaz, ödeme esası teyit edilir.
- **Net fiyat:** ardışık iskonto, fiyat birimi (100 adet/ton/koli), kademeli fiyat,
  MOQ/paket/fire, aktif madde ve bölünmüş siparişin ek giderleri eklendi.
- **Finansman:** `NBD − nominal` işareti açık; avans mahsubu, hakediş kesintisi,
  depozito, indirilebilir KDV finansmanı ve eskalasyon farkı tek nakit akışına bağlandı.
  Faiz paritesiyle teorik forward ile gerçek banka kotasyonu ayrıldı.
- **Banka masrafları:** her bankaya/ürüne 90 günlük dönem ve %5 BSMV dayatılması kalktı;
  kotasyondaki takvim dönemi, asgari ücret, gün esası ve vergi kapsamı kullanılır.
- **Vergi/ithalat:** indirilemeyen KDV maliyete girer; teşvik beklentisi baz tutarı
  sıfırlamaz. TCMB Unit dikkate alınır. Gümrük kıymeti/KDV matrahı ayrıldı; DDP
  boşaltma, FCA/FOB ve DAP/DPU ayrımları düzeltildi. Maliyet kimliğiyle çift sayım önlenir.
- **TCO:** kW/kWh ve verim farkı hesabı düzeltildi; ortak çıktı/ömür, yenileme,
  başlangıç parça stoğu, duruş, basit/iskontolu geri ödeme ve hurda/bertaraf netleştirildi.
- **Puan:** ortak maliyetin KTM sırasını korurken toplam puan sırasını değiştirebileceği
  örneklendi. Tahmin payı brüt NBD bazına alındı. Eksik teknik bilgi ile kanıtlı kısmi
  uygunluk ayrıldı; %5 puan farkının istatistiksel eşdeğerlik olmadığı açıklandı.
  Eşit/sıfır/boş değerler, elenen teklif ve düşük ayırt edici oran sınırları eklendi.
- **Rekabet:** seçenek ve bağımsız tedarikçi sayısı ayrıldı. Kısa listeden önce TCO/
  finansman gibi seçimi değiştirebilecek farkların bütün tekliflerde taranması sağlandı.
  Şartnamesiz modda en geniş teklif, otomatik ihtiyaç kabul edilmez.
- **Yeni kaynak:** `references/hesaplama-kontrolleri.md`; kontrol örnekleri
  `scripts/hesaplama_ornekleri_test.py`. GİB, Ticaret Bakanlığı, TCMB, ICC ve banka
  kaynakları ilgili dosyalarda; güncel işlem oranları yine ayrıca teyit edilir.

**Doğrulama:** 26 sentetik sayısal test geçti. Önceki gerçek Kuluçkahane karar
çalışma kitabında 102 miktar × birim fiyat hesabı, 15 bölüm toplamı ve 3 vergi köprüsü
bağımsız yeniden hesapla tutarlı bulundu. Bu, eski dosyanın aritmetik kontrolüdür;
kaynak tekliflerin yeniden okunması, yeni revizyon veya bulut arayüzünde tam koşu değildir.
Eksik ödeme planı ve fiyatlanmamış ortak giderler nedeniyle eski toplamlar nihai
satınalma maliyeti sayılmaz. Eski karar dosyası değiştirilmedi.

---

## v1.6 — 2026-09-03

**Yazılı raporun PDF sürümü zorunlu hâle getirildi.** Teklif değerlendirme
raporunun Markdown sürümüyle birlikte PDF olarak da teslim edilmesi tanımlandı. Eski kural PDF'i
"paylaşım için" opsiyonel bırakıyordu; kullanıcı ayrıca istemedikçe yalnız Markdown
üretilmesine yol açıyordu. Karar merciine, ihale komisyonuna ve arşive sunulan biçim PDF'tir.

- **Adım 10 yeniden yazıldı** (`SKILL.md`): rapor üretiliyorsa çıktı iki dosyadır —
  `.md` + `.pdf`. PDF ayrı istek değil, raporun parçası. Adım 0a'daki çıktı sorusu da
  buna göre düzeltildi: kullanıcıya PDF için ayrıca sorulmaz.
- **Dönüştürme zinciri beş basamağa çıktı ve sırası düzeltildi**
  (`excel-ve-rapor-uretimi.md` §5): **Edge headless** → weasyprint → **pandoc (yeni)** →
  reportlab → HTML+MD teslim + nedenini açıkça yazma. Eski sıra reportlab'ı Edge'in önüne
  koyuyordu; yerel makinede reportlab kurulu, weasyprint değildi. Bu durum zincirin
  sistematik olarak tablo düzenini kabalaştıran basamağa yönelmesine neden oluyordu. İlk üç basamak hazırlanan HTML'i olduğu gibi
  basar, reportlab düzeni sıfırdan kurar; bu yüzden en sona alındı. Son basamakta bile
  "PDF üretildi" izlenimi verilmesi yasak.
- **Üretim sonrası doğrulama eklendi** (§5 ve `SKILL.md` Adım 11/18): PDF diskte var mı,
  0 byte'tan büyük mü, sayfa sayısı makul mü, son bölüm ("Sonuç ve Öneri") içinde mi.
  Gerekçe: Edge headless dönüşümü bitirmediği hâlde dosyayı bırakabiliyor; boyut/içerik
  kontrolü olmadan raporun tamamlandığının bildirilmesi hatalı durum beyanıdır. Doğrulama pası 18 maddeye çıktı.
- **Kalite ilkesine bağlandı:** "Rapor PDF'i olmadan teslim edilmez." Üretilemediyse bu
  bir teslim eksiğidir ve öyle yazılır.
- **Dönüştürme zincirinin 1. basamağı uygulamalı olarak doğrulandı:** Türkçe karakter ve tablo içeren
  örnek HTML, yerel Edge headless ile PDF'e basıldı — rc=0, 48 KB, 2 sayfa, `%PDF-`
  başlığı yerinde. Doğrulamada belirlenen teknik sınırlama yönergeye eklendi: Edge sayfa numarasını yalnız
  kendi altlığında basar ve o altlıkta dosya yolu görünür; `--no-pdf-header-footer` yolu
  gizler ama numarayı da götürür (Chromium `@page` sayfa sayacını desteklemez). Numara
  şartsa weasyprint kullanılır.

---

## v1.5 — 2026-09-03

**İlk gerçek veri uygulamasında belirlenen altı eksiklik giderildi.** Önceki
denetimler doküman incelemesiyle sınırlıydı; ilk uygulama gerçek bir dosya setiyle yapıldı (Kılıç kuluçkahane
proses havuzları — 3 teklif, ortak keşif cetveli, 6 taranmış proje çizimi, teknik şartname
yok). Analiz doğru sonuç verdi ve doğrulama pası 44 kontrolün 44'ünü geçti; ama koşu
sırasında **mevcut yönergelerin kapsamadığı veya ilave işlem gerektiren**
altı eksiklik belirlendi. Tamamı bu sürümde kurala bağlandı.

- **Tazelik artık iki testle ölçülüyor** (`SKILL.md` Adım 1). Eski kural yalnız *beyan
  edilen geçerlilik* süresine bakıyordu; geçerlilik hiç yazılmamışsa test sessizce
  çalışmıyordu. Gerçek veri uygulamasında üç teklifin de geçerlilik beyanı yoktu ve
  **üçü de 3,5 ay eskiydi**. Mevcut yazılı kurallar bu durumu işaretlemiyordu; durum
  analizin kritik bulgularından biriydi. Yeni: **yaş testi** (teklif tarihi ↔ analiz tarihi, beyandan bağımsız,
  >60 gün KRİTİK / 30-60 gün uyarı), tarih yoksa dosya tarihi kullanılıp bu yazılıyor.
  Tetiklendiğinde Özet'in kritik uyarısına, kırmızı çizgilere ve RFI'nın 1. maddesine
  giriyor; oynak dallarda 9. basamağı (eskalasyon) da devreye alıyor.
- **Anormal düşük teklif testi ikiye ayrıldı** (`poz-eslestirme-normalizasyon.md` §5).
  Eski tek test (ham profil ₺/kg × 1,6-1,8) **yalnız çelik için** tanımlıydı; betonarme
  bir işte karşılığı yoktu ve güncel rayiç bulunmadığında değerlendirme üretilemiyordu.
  Yeni: **Test A** mutlak alt sınır — beton, donatı ve kalıp için katsayılarla genişletildi
  (kalıpta işçilik baskın olduğu için mutlak sınırın güvenilmez olduğu açıkça yazıldı).
  **Test B — yakınsama testi:** dış fiyat gerektirmez, referans rakip tekliflerin
  kendisidir. Diğer teklifler birbirine ≤%5 yakınsamışken bir teklif kümeden ≥%15 aşağıdaysa
  sinyal verir. Gerçek veri uygulamasında iki teklif %1,1 içinde buluşmuş, üçüncüsü %20 aşağıdaydı;
  bu test uygulama sırasında ayrıca kuruldu. N≥3 gerektirdiği, ikili modda kurulmadığı
  `teklif-sayisi-modlari.md`'ye de yazıldı.
- **Zincirin 5. basamağı 5-A / 5-B olarak ikiye bölündü** (`SKILL.md`). Eski tek satır
  yalnız *firmalar arası* kapsam farkını modelliyordu. Hiçbir firmanın fiyatlamadığı kalem
  (keşif cetvelinde talep edilmediği için) **ayrı bir durumdur: sıralamayı değiştirmez,
  bütçeyi değiştirir.** İkisini toplamak, "eşit kapsama getirince sıra değişti mi?"
  sorusunu cevaplanamaz hâle getiriyordu. Numaralandırma bilinçli olarak 5-A/5-B yapıldı;
  6-9 kaymadı, diğer dosyalardaki basamak referansları geçerli kaldı. Adım 5'e **5c2**
  alt adımı eklendi: rayiç dayanağı yoksa **dayanaksız tutar kullanılmıyor**, satır kuruluyor
  ve hücre düzenlenebilir bırakılarak "teknik ofis tarafından doldurulacak" notu ekleniyor.
- **Ayırt edici ağırlık oranı zorunlu hâle geldi** (`puanlama-metodolojisi.md` yeni §2b).
  Bütün tekliflere aynı puanı veren bir kriterin ağırlığı sıralamaya katkı yapmaz; ama
  ağırlık toplamı yine 100 göründüğü için tablo kapsamlı bir çok kriterli karar modeli
  izlenimi oluşturur. Gerçek veri uygulamasında **100 puanın 64'ü ayırt etmiyordu** — sıralamayı fiilen yalnız fiyat
  belirliyordu, oysa tablo 10 kriterli görünüyordu. Yeni: oran hesaplanıp Puanlama ve
  Karar Özeti'ne yazılıyor; **%30'un altında puan tablosu tek başına karar gerekçesi
  olarak sunulmuyor.** Nötr puan kuralı da tanımlandı: veri yoksa 5,0 (0 cezalandırma,
  10 ödüllendirme olurdu), düzenlenebilir hücre, ve **nötr puanlı her kriter aynı zamanda
  bir RFI maddesidir.**
- **Duyarlılık yorumu ayırt edici orana koşullandı** (`puanlama-metodolojisi.md` §4).
  "Sıralama tüm senaryolarda aynı → sonuç sağlamdır" cümlesi, ağırlığın büyük bölümü sabit
  puanlıyken **yapısal olarak** doğru çıkar ve karar vericide dayanaksız güven oluşturur.
  Oran <%60 iken bu cümle artık yazılmıyor; yerine sıralamanın değişmesinin matematiksel
  olarak mümkün olmadığı ve bunun *"sonucu değiştirebilecek bilgi bulunmuyor"* anlamına
  geldiği yazılıyor.
- **Uymayan Noktalar sekmesi idareyi muhatap olarak kapsıyor**
  (`excel-ve-rapor-uretimi.md`). Sekme "firma × uygunsuzluk" olarak tanımlıydı; oysa gerçek
  koşudaki en kritik üç bulgu (şartnamenin hiç olmaması, cetvelde su yalıtımı ve sızdırmazlık
  testinin bulunmaması, teyit edilmemiş proje revizyonu) **firma kusuru değildi.** Sekme
  artık **muhatap** sütunuyla kuruluyor: firma · TÜM FİRMALAR · İDARE. Aynı mantık
  `SKILL.md` Kalite İlkeleri'ne de eklendi — yanlış tarafa yüklenen bulgu hem haksızlıktır
  hem gerçek sorunu görünmez kılar.
- **Eşit Kapsam ve Ağırlık Duyarlılığı sekme tanımları** yeni kurallara göre yeniden
  yazıldı; Eşit Kapsam'ın 5-B bloğunun toplamı Özet'teki KTM parametresine **formülle**
  bağlanıyor (tek kaynak ilkesi).
- **Doğrulama pasına üç kontrol eklendi** (`SKILL.md` Adım 11 → 15, 16, 17): yaş testi
  çalıştırıldı mı · ayırt edici oran hesaplanıp yazıldı mı ve nötr puanlı her kriterin
  RFI karşılığı var mı · firma kusuru olmayan eksiklik İDARE satırına yazıldı mı.
  6. ve 8. maddeler de 5-A/5-B ayrımı ve koşullu duyarlılık yorumu için genişletildi.

> **Not:** bu sürümdeki maddelerin hiçbiri v1.3'teki gibi hesap hatası değil. Beşi
> **eksik kapsama** (kural yazılmıştı ama bir durumu kapsamıyordu), biri **yanlış yorum**
> (hesap doğru, açıklama yanıltıcı) ile ilgilidir. Bu bulgular gerçek veri uygulamasında
> belirlenmiş; önceki üç doküman incelemesinde tespit edilememiştir.

## v1.4 — 2026-09-02

**Denetimin kalan beş maddesi kapatıldı.** v1.3 dört sistematik hesap hatasını düzeltmişti;
bu sürüm aynı denetimde bulunan ama "ayrı karar" olarak bekletilen beş yapısal maddeyi
kapatıyor. Hiçbiri v1.3'teki gibi tek yönlü hata değil — üçü **tanımsızlık**, ikisi
**eksik modelleme**.

- **KDV'nin vergi zemini netleşti.** İthalat köprüsünde KDV 10. satırdı ve yapısal olarak
  "= DDP eşdeğer maliyet" toplamının içindeydi; aynı satırın metni ise "ayrı satırda
  tutulur" diyordu. Bu çelişki personel için %20'lik bir belirsizlikti.
  Yeni: **KTM = KDV hariç** — `SKILL.md` zincir tanımına yazıldı, 10. satır
  "toplama GİRMEZ" damgası aldı ve toplam formülü `1…9 + 11…13` olarak açıkça yazıldı.
  Yeni bölüm `ithalat-maliyet-koprusu.md` §2b: hangi verginin girip hangisinin girmediğini
  tek soruya bağlayan tablo — **"indirilebilir mi?"**. Gümrük vergisi/İGV/anti-damping ve
  damga vergisi girer; KDV ve tevkifat girmez (tevkifat KDV'nin kime ödendiğini değiştirir,
  tutarını değiştirmez). **Karışık zemin yasağı** kuralı eklendi: bir teklifin KDV dahil,
  diğerinin hariç girmesi %20'lik yapay fark üretir; KDV dahil verilmiş teklif ayrıştırılır,
  ayrıştırılamıyorsa RFI maddesidir.
- **Puan ölçeği tanımlandı** (`puanlama-metodolojisi.md` §3b — yeni). Formül
  (`SUMPRODUCT/100`, ağırlık toplamı 100, puanlar 0-10) sonucu **0-10** üretiyordu ama
  hiçbir yerde yazılı değildi ve metin iki yerde "100 üzerinden" diyordu. Artık ölçek
  açık, sütun başlıklarında zorunlu ("Puan (0-10)", "Toplam (0-10)"), 100'lük sunum için
  `/10` alternatifi var ve **bir dosyada tek ölçek** kuralı geçerli.
- **"%5 fark" ölçüsü tanımlandı.** Eşiğin mutlak puan mı oran mı olduğu belirsizdi —
  0-10 ölçeğinde 5 puan, ölçeğin yarısı demek olurdu. Artık **göreli**:
  `(birinci − ikinci) / birinci < %5` → "ayırt edilemez" (0-10 ölçeğinde ~0,3-0,5 puan).
  Ölçek değişse bile kural aynı kalır; üç geçtiği yer de aynı tanıma bağlandı.
- **Normalizasyonun kriterlerin fiilî etkisine yansıması ölçüldü ve alternatif yöntem eklendi**
  (`puanlama-metodolojisi.md` §3c — yeni). Oransal yöntemde (`10 × MIN/firma`) 30 ağırlıklı
  fiyat kriterindeki %10 fiyat farkı toplama **0,273** etki ediyor; 8 ağırlıklı öznel bir
  kriterdeki 3 puanlık takdir ise **0,240**. Yani yazılı ağırlık ile fiili ağırlık farklı
  şeyler. Bu bir hata değil yöntemin özelliği — ama bilinerek seçilmesi gerekiyor.
  Eklenen: **aralık (min-maks) yöntemi** alternatifi, iki yöntemin karşılaştırma tablosu
  ve seçim kuralı. Min-maks **2 teklifte kullanılmaz** (fark %1 de olsa %100 de olsa hep
  10/0 verir), 5+ teklifte kullanılabilir. Seçilen yöntem ve **fiyat yayılımı (`MAKS/MIN`)**
  Puanlama sekmesine yazılır; yayılım %50'yi geçerse oransal yöntemin fiyatı yeterince
  cezalandırmadığı Karar Özeti'nde belirtilir.
- **Teminat/akreditif komisyonu gerçek banka pratiğine getirildi**
  (`finansal-degerlendirme.md` §4). Eski formül `tutar × yıllık oran × gün/365` iki şeyi
  birlikte kapsamıyordu: bankalar **üç aylık dönem** üzerinden ve **başlayan dönem tam**
  keser; ayrıca **BSMV (%5)** uygulanır. 1.000.000 TL / 7 ay / çeyrek %0,5 örneğinde gün bazlı
  hesap 11.671 TL, doğrusu 15.750 TL — **%35 eksik**. Yeni formül yukarı yuvarlamalı çeyrek
  sayısı + BSMV çarpanı; ayrıca komisyonun kendisi de bir nakit akışı olarak iskonto
  ediliyor ve **teslim süresinin gizli maliyeti** olduğu (uzun teslim → uzun teminat →
  yüksek komisyon) not edildi, ayrıca puanlanmaması için çifte sayım kuralına bağlandı.
- **Kur duyarlılığı iki yönlü oldu** (`finansal-degerlendirme.md` §6). Yalnız
  "+%10 / +%20" senaryosu vardı; bu yapı tek yönlü sonuç üretiyor ve TL teklif lehine
  sistematik sapma oluşturuyordu. Artık **−%20 / −%10 / baz / +%10 / +%20** ve **"başabaş kur"**
  satırı: sıralamanın hangi kur seviyesinde değiştiği. Ek kural: "TL teklif kur riskinden
  muaftır" varsayımı kontrol edilir — fiyat revizyon maddesi kura endeksliyse o teklif de
  duyarlılık satırında sabit gösterilmez.

**İlave düzenlemeler:** mevzuat oranlarına
**tarih damgası** zorunluluğu (KDV oranı, tevkifat payı, BSMV — "…tarihinde geçerli oran");
ve `excel-ve-rapor-uretimi.md` tuzak listesine **formül argüman ayırıcısı** maddesi
(openpyxl'e noktalı virgülle yazılan formülü Excel okuyamaz; dosya biçiminde ayırıcı her
zaman virgüldür) — `puanlama-metodolojisi.md`'deki örnek formül de virgüle çevrildi.

Yansıyan yerler: `SKILL.md` (zincir 6. basamağı ve KTM tanımı, Adım 5d yeniden yazıldı),
`ithalat-maliyet-koprusu.md` (10. ve 14. satır + yeni §2b), `finansal-degerlendirme.md`
(§4 ve §6), `puanlama-metodolojisi.md` (§0, §3, yeni §3b ve §3c, §5),
`teklif-sayisi-modlari.md` (ölçek ifadesi), `excel-ve-rapor-uretimi.md`
(Puanlama sekmesi tanımı + tuzak listesi).

---

## v1.3 — 2026-09-02

**Hesap denetimi: dört sistematik hata düzeltildi.** Skill gerçek teklif setine
uygulanmadan formül denetiminden geçirildi; bulunan dört hatanın hepsi **tek yönlü**, yani
belirli bir teklif tipini sürekli kazandıran hatalardı.

- **Döviz cinsi vadeli ödeme artık TL oranıyla iskonto edilmiyor**
  (`finansal-degerlendirme.md` §1b — yeni bölüm). Eski hâlinde döviz ödemesi spot kurla
  TL'ye çevrilip TL nominal oranıyla indirgeniyordu; bu yöntem "TL hiç değer kaybetmeyecek"
  varsayımına eşdeğerdi ve **ödemeyi öteleyen döviz teklifine haksız avantaj sağlıyordu.**
  Ölçülen sapma: 100.000 EUR / 12 ay vadeli ödemede %35 (1,1 milyon TL, 4,5 milyonluk
  alımda). Yeni kural: her para birimi kendi oranıyla iskonto edilir, ya da forward kurla
  çevrilip TL oranıyla iskonto edilir; ikisi de yazılı, banka kotasyonu varsa forward
  tercih edilir. Excel'de para birimi başına ayrı oran hücresi.
- **TCO'da oranın cinsi akışın cinsine bağlandı** (`tco-omur-boyu-maliyet.md` §3a — yeni
  bölüm). İşletme maliyetleri bugünün fiyatıyla sabit yazılıp **nominal** TL oranıyla
  iskonto ediliyordu; 10 yıl / %40 nominal / %30 enflasyon örneğinde ömür boyu maliyet
  **%64,5 eksik** çıkıyor (2,41 yıl yerine 6,80 yıl eşdeğeri). Bu hâliyle modülün temel
  varsayımı ("%3 enerji farkı %10 fiyat farkını siler") gerçekleşmiyordu. `r_reel =
  (1+r_nominal)/(1+π) − 1` formülü eklendi (çıkarma yolu yasaklandı), enflasyon artık
  zorunlu girdi ve π için duyarlılık satırı kuruluyor.
- **Çifte sayım yasağı kuralı eklendi** (`puanlama-metodolojisi.md`). KTM'ye para olarak
  giren eksiklik puanlamada ikinci kez cezalandırılıyordu: eksik kapsam (ağırlık 15/12),
  yedek parça fiyatı (4) ve ödeme koşulları (8) — makine setinde 27 ağırlık. Hangi konunun
  parada, hangisinin puanda olduğunu gösteren tablo kuruldu. Kriter 2 yeniden tanımlandı:
  "kapsam bütünlüğü" → **kapsam belirsizliği / tahmin payı**,
  `puan = 10 × (1 − tahminle eklenen tutar / KTM)` — artık eksikliğin bedelini değil,
  KTM'nin ne kadarının analizde kullanılan tahminlere dayandığını ölçer. Kriter 5'ten ödeme
  tutarı/vadesi, kriter 8'den yedek parça fiyatı çıkarıldı.
- **Kantar → teorik tonaj düzeltmesinin yönü düzeltildi**
  (`poz-eslestirme-normalizasyon.md` §3). "Kantar bazlı teklif teorik esasa %-5 ile
  **indirgenir**" yazıyordu; kantar tonajı fire, bulon ve kaynak metalini içerdiği için
  teorikten yüksektir, yani alıcı daha fazla ton öder — düzeltme **artırma** yönünde
  olmalı. Çelik işinde %3-7 sistematik sapma. Sayısal örnek ve görünür katsayı hücresi
  eklendi; düzeltmenin yönünü belirleyen kural tanımlandı: **karşılaştırma birim fiyat üzerinden
  değil ödenecek toplam üzerinden yapılır.**

Yansıyan yerler: `SKILL.md` (soru kapısı finansal parametreleri, kur çevrimi notu, zincir
8. basamağı, Doğrulama pası 7 ve yeni 9. madde), `excel-ve-rapor-uretimi.md` (dört sekme
tanımı: para birimi başına oran hücresi, reel oran üçlüsü, kriter 2 bağlantısı, kantar
katsayısı), `sartname-yoksa.md` (kriter adı).

**Denetimde bulunup bu sürüme alınmayanlar** (ayrı karar bekliyor): KDV'nin ithalat
köprüsünde toplama girip metinde "maliyet değil" denmesi çelişkisi · oransal
normalizasyonun (`10 × MIN/firma`) fiyat ağırlığını fiilen ~8'e indirmesi · toplam puan
ölçeğinin (0-10 mu 0-100 mü) ve "%5 fark" ölçüsünün tanımsız olması · teminat komisyonunda
BSMV ve başlayan-çeyrek uygulamasının yokluğu · kur duyarlılığının tek yönlü olması.

---

## v1.2 — 2026-09-02

**Teklif sayısı varsayımı kaldırıldı.** Skill'in her yerinde örtük bir "birkaç teklif var"
kabulü vardı: medyan referans metraj, medyandan sapma testi, sıralama, ağırlık duyarlılığı.
Tek teklifte bunlar olmayan bir rekabeti varmış gibi gösteriyor, çok teklifte de bağlamı
tüketiyordu.

- **Yeni dosya `references/teklif-sayisi-modlari.md`** ve SKILL.md'ye **Adım 0c — teklif
  sayısı kapısı**: 1 / 2 / 3-6 / 7+ için dört mod.
- **Tek teklif modu:** karşılaştırma yerine **makullük ve kapsam denetimi**; puanlama ve
  duyarlılık kurulmaz (tek teklife puan vermek olmayan sıralamaya gerekçe üretir);
  Özet'te "TEK TEKLİF — REKABET YOK" uyarısı, **pazarlık gündemi** ve ikinci teklif
  önerisi zorunlu. Maliyet köprüsü yine kurulur — tek teklifte de teklif fiyatı gerçek
  maliyet değildir.
- **İkili mod:** medyan/sapma yerine **fark analizi**; anormal düşük teklif testi mutlak
  alt sınırla yapılır; referans metraj için iki senaryo kurulur, ortalama uydurulmaz.
- **Kısa liste modu (7+):** eleme ve KTM hepsine, derin analiz ilk 4-5'e; kısa liste
  ölçütü yazılı ve kullanıcı değiştirebilir. Medyan/sapma testleri bu modda en güçlü.
- **Sayım kuralı netleşti:** sayılan şey firma değil **teklif**. Revizyonlar tek sayılır,
  **alternatifler** (A/B seçenekli, farklı marka/kapasite) ayrı sayılır ve ayrı sütun alır.
  **Eleme sonrası** kalan sayı modu belirler — 5 teklif elemeyle 1'e düşerse mod değişir.
- **Sıfır teklif:** analiz başlamaz; şartname tek başına geldiyse gereksinim listesi +
  teklif isteme kontrol listesi önerilir.
- Etkilenen dosyalar güncellendi: `poz-eslestirme-normalizasyon.md` (medyan için N≥3),
  `puanlama-metodolojisi.md` (yeni §0), `sartname-yoksa.md` (ortak referans kapsam N≥2
  gerektirir), `excel-ve-rapor-uretimi.md` (sayıya göre düşen sekmeler), doğrulama pasına
  "mod doğru mu" kontrolü.

## v1.1 — 2026-09-02

**Hedef kitle ve amaç netleşti.** Skill artık şirketin satınalma personeli tarafından
Claude ve ChatGPT kurumsal üyelikleri üzerinden kullanılıyor; kişiye özel hitap kaldırıldı,
amaç "doğru satınalma" olarak dört ilkeyle tanımlandı (uygunluk, karşılaştırılabilirlik,
yönetilmiş risk, izlenebilir gerekçe).

- **Dosya tanıma eklendi** (`references/dosya-tanima-ve-siniflandirma.md`): kullanıcı
  dosyaların ne olduğunu söylemek zorunda değil. PDF (metin/taranmış), Excel, Word, JPEG/PNG,
  MSG/EML, ZIP okunur; her dosya rolüne (teklif/şartname/keşif/proje/yazışma/belge/alakasız)
  ve alım dalına göre sınıflandırılır; analiz **envanter tablosuyla** başlar.
- **Şartnamesiz mod eklendi** (`references/sartname-yoksa.md`): şartname yoksa teknik
  uygunluk değerlendirmesi yapılmaz — atlanır ve atlandığı raporda görünür. Kapsam ölçütü
  tekliflerin birleşiminden türetilen "ortak referans kapsam" olur. Bir firmanın kendi
  teklifi şartname yerine kullanılmaz.
- **Genel mal/hizmet dalı eklendi** (`references/dal-genel-mal-hizmet.md`): inşaat ve makine
  dışındaki alımlar (sarf, ambalaj, kimyasal, hizmet, kiralama, yazılım) artık kapsam içinde;
  doğru kıyas birimi tablosu (₺/kg, ₺/ton-km, ₺/kişi-vardiya…) ile.
- **Soru kapısı zorunlu hâle geldi (Adım 0):** anlaşılmayan bir şey varsa analize
  başlanmıyor; sorular tek blokta, numaralı ve kısa soruluyor; cevapsız kalan varsayım
  işaretlenmeden toplama girmiyor.
- **Şartname çıkarımı ayrı dosyaya taşındı** (`references/sartname-gereksinim-cikarimi.md`):
  19 maddelik çerçeve + zorunlu↔tercih↔bilgi ayrımı + iç çelişki listesi.
- **Platform matrisi yazıldı** (`references/excel-ve-rapor-uretimi.md`): Claude, ChatGPT ve
  yerel CLI arasındaki farklar (paket kurma, internet/TCMB kuru, PDF yolu, çıktı teslimi,
  soru sorma) tabloya alındı. İnternet yoksa kur kullanıcıdan isteniyor — tahmin kur yok.
- Sekme seti SKILL.md'den referansa taşındı; SKILL.md akış omurgası olarak kaldı.

## v1.0 — 2026-09-02

İki ayrı skill tek skill'de birleştirildi:
`teknik-sartnameli-insaat-teklif-degerlendirme` + `teknik-sartnameli-makine-teklif-degerlendirme`
→ **`teklif-degerlendirme`**.

- Maliyet Köprüsü Zinciri birleştirildi: makinenin 6 + inşaatın 7 basamağı → **9 koşullu
  basamak**; devrede olmayan basamak gizlenmiyor, "uygulanmadı" yazılıyor.
- Dört referans birleştirildi (finansal değerlendirme, puanlama metodolojisi, sözleşme
  maddeleri, tedarikçi/yüklenici yeterlilik-risk); puanlamada iki varsayılan ağırlık seti
  yan yana duruyor.
- Dala özgü 8 dosya olduğu gibi korundu (4 ekipman + 3 iş türü + poz eşleştirme).
- Excel/rapor kuralları skill'in içine alındı (dış bir "xlsx skill"ine bağımlılık kaldırıldı).
