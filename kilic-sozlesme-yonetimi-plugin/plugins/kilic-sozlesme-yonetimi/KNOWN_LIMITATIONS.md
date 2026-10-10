---
title: Sözleşme Yönetimi bilinen sınırlar
created: 2026-10-04
modified: 2026-10-05
type: development
status: 🟡 devam ediyor
tags: [is, sozlesme, plugin]
---

# Bilinen sınırlar

## BLOCKED / CONFIG_REQUIRED

Host/OS düzeyinde reader→verifier→writer rol izolasyonu ve güvenilir kimlik/işlem izni kanıtlanmadı. Store allowlist ve salt-okunur snapshot uygulama kontrolleridir; aynı OS kullanıcısına karşı güvenlik garantisi değildir. Kritik dış yazma/gönderme devrede değil.

Normal sandbox'ta Word otomasyonu oturum hatasıyla engellendi; ayrı izin yükseltilmiş yetenek testi geçti. Work/Codex/Claude gerçek plugin yürütümündeki izin yolu henüz kanıtlanmadı. Python network canary'si WinError10013/10051 ile engellendi; tarayıcı/web aracı resmi belgeye erişebildi. Bu sonuç kurumsal ağın tamamı hakkında hüküm değildir.

Şirket yetki matrisi, PR-GNL-003 ve resmî genel bilgi güvenliği politikası salt okunur araştırmada bulundu. Bulunan çalışma setinin güncel yürürlük/onayı ve bu plugine özel AI veri/saklama/erişim kararı doğrulanmadı. Üretim kimlik/QA adaptörü ve Hukuk/teknik kabulü açık. Business yönetim paneline mevcut oturumla erişildi; bu yayın veya host kullanım kabulü değildir. S-20 şirketin kendi poliçe alımı kapsamı açık iş tercihi olarak korunur; tedarikçi sigorta kapsamını durdurmaz.

Bu tercih [[tasks/karar-kilic-sozlesme-s20-kapsami]] içinde `waiting`, sorumlu Ozan olarak kayıtlıdır; P0/P1 geliştirmesini engellemez.

## NOT_IMPLEMENTED / NOT_RUN

- Genel belge sadakati, karmaşık Word numaralandırma/biçim revizyonu, PDF tablo/kolon/genel görsel/OCR ve Excel hesap/display doğrulaması. Üç-format okuyucu ve case birimine bağlı kapsamlı kontrol kaydı çalışıyor; tam kritik kaynak doğrulaması PARTIAL.
- EML dışında mailbox/MSG e-posta okuyucuları. EML MIME gövde/alıntı/alternatif ve ek ayrımı dev.3'te testlidir; gönderen kimliği veya iş kabulü oluşturmaz. Eklerin içeriği ayrıca okunur.
- Bağlamın otomatik/anlamsal atıf keşfi ve göreve yeterlilik onayı; kalıcı açık konu/görüş/yetkili karar adaptörleri. Kayıtlı tanım/istisna/ek kapanımı ve UTF-8 bayt bütçesi P3 diliminde testli çalışır.
- P4 üretim kimlik/kurumsal yetki/QA adaptörü, host izolasyonu, sağlayıcı uzlaştırması ve çıktı kurtarma. Muhafız/parmakizi/izin tüketimi yalnız sentetik test diliminde çalışır; gerçek yürütüm kapalıdır.
- Üretim Word/görsel QA adaptörü, yeni açıklama yorumları, temiz/onaylı nüsha, genel türevi yeni girdi sürümüne yükseltme ve karmaşık revizyon. P5 ilk gerçek metin Track Changes dilimi, eski yorum/revizyon koruması ve ayrı sentetik native Word accept/reject + dört görünüm yerel inceleme testli; genel sadakat/kurumsal yetki değildir.
- K00–K29 sohbet skill'leri ve host entegrasyonu; tam 104 kabul tanımı.
- Live model/token/ücret ölçümü, SharePoint geçişi ve kurum çapında yayın. E-posta gönderimi son kullanıcı talimatıyla tamamen kapsam dışıdır.

## P1 destek sınırı

İlk migration 12 tabloyu kapsar; ek 002–005 ile fiziksel toplam 20'dir; tüm 44 hedef tablo uygulanmadı. P1 cache bayt envanteri, P2 cache PARTIAL belge okuması/kapsamlı kontrol, P3 kayıtlı bağlam paketidir; kritik analiz/onay cache'i değildir. Aday veri UNVERIFIED saklanır, iş kararı yaratmaz. BYTE diff anlamsal madde karşılaştırması değildir.

Windows kilidi gerçekten sınandı; diğer işletim sisteminde bu sürüm güvenli biçimde durur. Alım sınırı 100 MiB; P2 OOXML okuyucu sınırı 64 MiB, XML/parça 8 MiB ve 1024 parça; PDF 16 MiB/100 sayfa, XLSX 20.000 hücre/100 sheet. Kaynak erişimi kaybolursa context/snapshot okuması kapatılır; daha ince dosya/kurum ACL adaptörü sonraki iştir.

Snapshot yalnız commit edilmiş DB ve kayıtlı kaynak baytlarını taşır; karantinadaki yarım çıktılar teslim edilmez. Yerel audit, aynı kullanıcı haklarına sahip saldırgana karşı değiştirilemez veya hukuki imza kaydı değildir. Üretim verisi bu geliştirme klasörüne alınmadı.

## P2 destek sınırı

RAW/BEFORE/AFTER metin görünümleri revizyon kabulü değildir. İç içe/structural revizyon, field, gizli metin, altChunk, gömülü nesne ve şekiller görünür sınırlardır; kesin yazma/hukuki analiz izni yaratılmaz. Legacy DOC/XLS, makro ve şifreli belge desteklenmez. OOXML Strict namespace bu dilimde desteklenmez.

PDF ikinci okuyucu aynı text layer'ı kullanır; bağımsız kaynak görüntüsü kanıtı değildir. Temel içerik stream filtreleri sınırlıdır; desteklenmeyen filtrede kaynak metni zorlanmaz. Kritik değer/tarama adaylarında render/OCR kontrolü gerekir. OCR'ın Türkçe yeterliliği NOT_RUN.

Worker 30 saniyede sonlandırılır; ZIP/node/çıktı boyutları sınırlıdır. Worker yeni süreçtir, OS güvenlik/RAM kotası sandbox'ı değildir; özellikle native PDF/xref parser'ında RAM izolasyonu kanıtlanmadı. Ürün genel kritik analiz izni false kalır.

Windows'ta kaynak/snapshot dosyalarının 260 karakteri aşması desteklenip sınandı. DuckDB'nin ölçülen build'i çok derin DB yolunu açamadı; DB ve restore staging DB yolu 240 UTF-16 birimiyle sınırlandı. Bu sınır dosya oluşturma/kopyalama öncesi DB_YOL_SINIRI verir; otomatik başka klasöre taşıma yapılmaz.

## P2 kontrol kaydı sınırı

EXTRACTED_TEXT_MATCH PASS yalnız çıkarılmış görünüm/aralığın beklenen metne eşleşmesidir. PDF_PAGE_RENDER hedef görüntü üretimidir; görsel inceleme NOT_RUN kalır. Yerel gözlem ayrı kayıttır; eşleşse bile PARTIAL, inceleyen etiketi/kimliği UNVERIFIED. Çağıranın alan sınıflaması gerçek veya kurumsal karar olarak alınmaz. Okuyucunun tüm sorunları kontrol kaydında korunur; metin eşleşmesi BLOCKING sorunu çözmez.

Genel DOCX/XLSX render verifier ve güvenilir insan/host kimlik adaptörü yoktur. Boş metinli PDF render edilir; bu dilimde boş metin eşleşmesinden gözlem onayı çıkarılmaz. Tekrarlanan hedef/gözlem cache'den gelir; en fazla 256 kontrol/sürüm, üç yeni yerel gözlem/render hedefi vardır. Bütçe dolunca açık duruş gerekir; OCR otomatik tetiklenmez. Tam kaynak doğrulaması/nihai analiz izni false kalır. Kontrol geçmişi kaynak değişiminde silinmez; güncellik NEEDS_REVIEW ile ayrı belirtilir.

## P3 destek sınırı

Kapanım yalnız kayıtlı bağlantılardan üretilir. Bir düğümün DEFINITION/EXCEPTION/ANNEX etiketi, bir bağlantının gerekçesi ve yerel beyan kimliği UNVERIFIED'dır. Harita tüm mevcut güncel okumaların birimlerini gösterir; henüz okunmamış belge veya keşfedilmemiş atıf için yeterlilik kanıtı vermez. Tanım/istisna/ek/kontrol sığmıyorsa hazır bağlam yoktur; otomatik küçük parçalara bölme ve uzman soru üretme henüz uygulanmadı.

Bütçe yalnız `context` alanının gerçek UTF-8 baytlarıdır; dış tanı zarfı, tüm host konuşması, tokenizer/token/ücret dahil değildir. Her pakette kritik analiz false ve şirket yetkisi NOT_VERIFIED. 512 düğüm/2048 bağlantı/512 paket, 64 KiB kayıt/1 MiB bağlam ve 128 sürüm/4096 harita birimi uygulama sınırlarıdır; üretim ölçeği garantisi değildir. Tarihsel paket metadata'sı yalnız RECHECK_REQUIRED/NEEDS_REVIEW durumuyla görünür; güncel içerik için kaynaklar yeniden denetlenir. Detay [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P3_CONTEXT_PACKS]].

## P4 destek sınırı

Sentetik kimlik/şirket/kalite bayrakları üretim kanıtı değildir. Normal ajan yolu CONFIG_REQUIRED ile BLOCK verir; izin verme/yürütme JSON veya CLI komutu yoktur. Test API'si aynı OS kullanıcı haklarına karşı izolasyon sağlamaz; HMAC anahtarının test fixture'ında olması gerçek yetki kurulumu sayılmaz. İstek üstbilgi/gövde/hedef/sürüm ve canlı kapsamı bağlar; e-posta adresinin gerçek kişiye ait oluşunu doğrulamaz.

P4'ün ilk Backend fixture'ı sabit DOCX test baytları üretir; taslak yazımı veya Track Changes motoru değildir. P5 ayrı SyntheticDocxBackend gerçek hedefli revizyon motorunu bu kapılara bağlar; kurumsal kimlik/kaliteyi sağlamaz. Final/karantina NTFS hard link'leri aynı dosyayı paylaşır, değişim tamamlanma kontrolünde reddedilir. Dosya yayını/DB commit atomik değildir; yarım durum korunur ve uzlaştırılır. Karantina/final çıktı kurtarma ve gerçek provider sorgusu bu dilimde yoktur. Store snapshot final eylem dosyalarını taşımaz; P5 kayıtlı DOCX BLOB/soy ilişkisi DB içinde taşınır ama yeniden yayımlanmaz. İzin tüketimi korunur, dosyasız tamamlanma BLOCK olur.

Tek izin/işlem için gerçek süreç yarışı ve kesinti sınanır; bağımsız yeni işlem UUID'lerinin bütün iş dünyasındaki mükerrer gönderimini önleme veya exactly-once teslim garantisi değildir. Mock sağlayıcı kabulü teslim onayı false bırakır. Gerçek mail, SharePoint ve üretim kurumsal yazma NOT_RUN. Ayrıntı [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P4_ACTION_GATES]].

## P5 destek sınırı

Ana belge AFTER normal run aralığında metin değişimi/silme çalışır; eski revizyona, işaret aralığına, content control/text box'a, yan parçalara, alan kodlarına veya yapısal biçime yazma desteklenmez. Yeni metin ilk run biçimini devralır; karmaşık biçim eşlemesi yoktur. Tüm alan kodlu belgeler (header/footer dahil), dış ilişkiler ve imzalı/korumalı paketler bu yazma diliminde kapalıdır; Word sayfa numarası gibi yaygın alanlar da bu sınırdadır. Desteklenmeyen hedef düzleştirilmez.

Native Word kabul/ret ve açık iç/dış nüsha kararları iki sentetik probe'da kanıtlandı; genel QA adaptörü ve üretim host izin yolu değildir. TestWordEvidence fixture'ı güvenilir şirket onayı olamaz; normal ajan yürütümü kapalıdır. Her probe dört tek sayfa görsel içerir, gözlemci kimliği UNVERIFIED. Paketli renderer eksik soffice nedeniyle çalışmadı; native Word/PDFium kanıtı ayrı korunur. Klasik yeni yorum ve açık seçimli iç/dış taslak çalışır; iş onaylı nüsha ve genel türevi kaynak sürümüne yükseltme uygulanmadı. AI-only accept QA kopyaları dışa teslim nüshası değildir. Modern/genişletilmiş yorum, silme hedefli yorum ve dış nüshada bilinmeyen metadata/custom/media parçaları engellenir. Dış taslak tüm yorumları kaldırır; gövdedeki sırları otomatik anonimleştirmez. Detay [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P5_COMMENTS_COPIES]].

## P6/P7 ve yayın sınırı

30 iş becerisi gerçek ortak kaynak/bütçe/şema kontrollerine bağlı taslak protokolleridir. Alan değerlendirmesinin uzman/Hukuk kabulü ve host doğal dil kullanımı NOT_RUN; yalnız protokol/metadata sayısı tam iş davranışı değildir. K00 doğal dil yorumunu hosta bırakır, açık senaryo eşleşmesini deterministik seçer. Para/tarih girdileri kullanıcı girdisi UNVERIFIED, resmi takvim veya şirket oranı onayı değildir.

40 senaryo kimliği × üç varyantın 120 çalıştırması/296 kontrolü sekiz kısmi fixture profilinde teknik PASS. Tam fiyat/teknik ek/mail/teminat/poliçe/gerçekleşme paketleri ve bağımsız uzman rubric'i yok; özgün 104 tam kabul NOT_RUN. Üretim kimlik/yetki/QA, kurumsal erişim/saklama/connector ve Hukuk/teknik kabul kapıları eksik. Koşullu GitHub/Business yayını BLOCKED; metadata ve geliştirme ZIP'i yayın başarısı sayılmaz. [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P7_RELEASE_CHECKS]].


## Dev.2 kapsam güncellemesi

Kaynaklı normalleştirme/karşılaştırma ve yükümlülük/olay ledger'ı çalışıyor; uzman anlam/ifa onayı değildir. Güncelleyici2.3.0/13 paket/özel signed PDF/aynı talebe dönüş gerçek boş-ortam testindePASS. Yeni Python kurucusuNOT_RUN, uzun venv kökü yazmadanBLOCKED, mevcut bozuk shared bileşen otomatik onarılmaz. Yerel Windows shell olmayan cloudhost kurulum yapamaz.31 becerinin gerçek ad/sürüm/geliştirici mesajı paket/çıktı düzeyinde testli; uygulama içinde modelin her çağrıda sohbet satırını aktarması ve gerçek kullanıcı keşfiNOT_RUN. Eski P5 yeni yorum/temiz taslak maddeleri ilk faz sınırıdır; sınırlı klasik yorum/iç-dış taslak P5 ikinci dilimde testli, tam onaylı/karmaşık nüsha açık. Üretim yayın engeli bağımsız geliştirmeyi durdurmaz.


## Dev.3 güncel kapsam

E-posta gönderimi ve mailbox taslağı kapsamdan kaldırıldı; bu bir eksik connector değildir. EML kaynak okuma eklendi, kaynak kimliği veya iş kabulü oluşturmaz. Ek içerikleri ayrı kaynak olarak okunmalıdır. Önceki gönderim sınırlamaları/eski P4 kanıtları tarihsel sürümlere aittir. Özgün104 kabul tanımından üç gönderim regresyonu kullanıcı kararıyla kapsam dışıdır; kalan101 tam kabul açık. Word üretim yetki/QA, uzman ve host kabulü ayrı açık kalır.
