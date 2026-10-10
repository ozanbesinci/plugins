# Maliyet ve Karar Akışı

### Adım 5 — Maliyet köprüsünün kurulması

Önce `references/hesaplama-kontrolleri.md` okunur. Zinciri görünür basamaklarla kur;
her giderin tek kimliği ve tek maliyet sahibi olur. Basamaklar sunum sırasıdır:
eskalasyonlu tutar ödeme tarihine yerleştirilip iskonto edilir; ödeme planına zaten
giren fark ikinci kez eklenmez. KTM bugünkü değer, nominal nakit bütçesi ayrı toplamdır.

- **5a — Miktar düzeltmesi** (basamak 3). Ortak referans miktar × firmanın birim fiyatları.
  Götürü teklifte birim fiyat dökümü yoksa toplamı beyan miktara oranlayarak **zımni birim
  fiyat** türet ve tahmin işaretle; beyan da yoksa "miktar beyansız" işaretle ve RFI'ya yaz —
  **dayanaksız oran kullanılmaz.**
- **5b — İthalat köprüsü** (basamak 4). `ithalat-maliyet-koprusu.md` ile EXW/FOB/CIF/DAP/DDP
  teklifleri **DDP eşdeğerine** getirilir. Yurt içi ve yurt dışı teklif bu köprü kurulmadan
  aynı satıra yazılmaz. Yapım işinde ithal malzeme tedariki varsa köprü 5c'nin içinde alt
  satır olur.
- **5c — Eşit kapsam düzeltmesi, firmalar arası** (basamak 5-A). Her teklifi tam kapsama
  getiren ilave kalemler tahmin edilir. **Eksik kalem sıfır sayılmaz** — piyasa rayici/idare
  tahminiyle eklenir; hücre sarı dolgu + mavi font, dayanağı not sütununda. Şartname yoksa
  referans "ortak referans kapsam"dır (bkz. `sartname-yoksa.md`).
- **5c2 — Ortak kapsam boşluğu** (basamak 5-B). Dalın kontrol listesi
  (`is-turu-*.md` / `ekipman-*.md` / `dal-genel-mal-hizmet.md` ve
  `poz-eslestirme-normalizasyon.md` §6) tekliflerin **birleşimiyle** karşılaştırılır:
  listede olup **hiçbir** teklifte bulunmayan kalemler ayrı bir tabloya yazılır.
  Tutar, ödeme tarihi ve kapsam gerçekten aynıysa ortak satıra girer; aksi halde
  firmaya özgü düzeltmedir. Fiyatlanmamış tutar sıfırlanmaz; ÖN SONUÇ ve RFI kaydı
  açılır. Muhatap, şartnamenin kalemi isteyip istememesine göre belirlenir.
- **5d — Vergisel düzeltme** (basamak 6). **Toplama giren:** damga vergisi ve firma bazında
  farklılaşan ve alıcıda kalan SGK yükümlülükleri (satıcı fiyatına dahil SGK tekrar eklenmez; ithalatta gümrük vergisi/İGV zaten 4. basamakta).
  **Toplama giren ek kalem:** indirilemeyen KDV kısmı.
  **Toplama girmeyen, ayrı satırda duran:** indirilebilir KDV ve yapım işlerinde **KDV tevkifatı** —
  tevkifat KDV'nin kime ödendiğini değiştirir, tutarını değiştirmez; yalnız nakit akışı
  farkıdır. Ayırt edici soru her zaman "indirilebilir mi?" (`ithalat-maliyet-koprusu.md`
  §2b). **Vergisel konularda mali müşavir teyidi şarttır** — hücreler "teyit bekleniyor"
  işaretlenir. Mevzuat oranları (KDV oranı, tevkifat payı) **tarih damgasıyla** yazılır:
  "…tarihinde geçerli oran" — oran değişirse analizin hangi rejime dayandığı belli olur.
- **5e — Dengesiz teklif ve anormal fiyat analizi.** Poz bazlı min/medyan/max sapması,
  front-loading deseni, anormal düşük teklif alt sınır testi:
  `poz-eslestirme-normalizasyon.md`. **Anormal düşük teklif eleme sebebi değildir** —
  açıklama istenir (RFI) ve risk matrisine girer.
- **5f — Ömür boyu maliyet (TCO)** (basamak 8). `tco-omur-boyu-maliyet.md`. Ekipman
  enerji/bakım tüketmiyorsa basamak "uygulanmadı" işaretlenir, gerekçesi yazılır.
- **5g — Finansman düzeltmesi** (basamak 7). `finansal-degerlendirme.md`: ödeme/hakediş
  planı NBD − nominal farkı, alıcıya ait banka komisyonları; avans ve kesinti iadeleri ödeme akışında tek kez.
- **5h — Eskalasyon riski** (basamak 9). Fiyat revizyon/eskalasyon hükmü olan teklif
  **"fiyatı sabit değildir"** uyarısı alır; hükümsüz uzun süreli teklif "risk primi gömülü
  veya revizyon talebi riski var" yorumu alır. Senaryo hesabı (%0/%X/%2X) ödeme tarihine iskonto edilerek KTM'ye girer.
  Olasılıklar tanımlanmadıkça "beklenen değer" denmez; "baz senaryo" denir.

- **5i — Nakit, kalite ve stok kontrolleri.** `references/nakit-kalite-stok.md`:
  ödeme takviminden nominal tepe nakit ve tarihi; kalite kayıpları ve ilave kontrol
  giderinden kullanılabilir birim maliyeti; tekrarlayan/toplu alımda sipariş/teslim
  senaryolarının NBD ve stok karşılaştırması. Yalnız ilgili modüller kurulur.
  Kalite/stok giderlerinin benzersiz NBD katkısı uygun mevcut KTM basamağına bağlanır;
  yeni bir mükerrer toplam oluşturulmaz. Nakit ihtiyacı tutarı KTM'ye eklenmez.

Zincir sonunda her firma için **tek bir KTM** oluşur; Özet ve Puanlama sekmelerine
**formülle** bağlanır.

### Adım 6 — Elemeli kapı ve puanlama

`references/puanlama-metodolojisi.md`. **Önce teklif sayısı kontrol edilir** (Adım 0c):
tek teklifte puanlama yapılmaz — eşik değerlendirmesi konur; yedi ve üzerinde ağırlıklı
puanlama kısa listeye uygulanır. **Sıra kesindir:** önce elemeli (knock-out) kapı,
sonra ağırlıklı puanlama. Asgari şartı sağlamayan teklif puanlamaya alınmaz; tabloda
"ELENDİ" görünür ve sıralamaya girmez. Ölçülebilir kriterler formülle normalize edilir.
**Ağırlık duyarlılık tablosu zorunludur.** Şartname yoksa yalnız idari kapı uygulanır.

**Puanı sunmadan önce ayırt edici ağırlık oranı hesaplanır** (`puanlama-metodolojisi.md`
§2b): bütün tekliflere aynı puanı veren kriterlerin ağırlığı sıralamaya katkı yapmaz.
Oran Puanlama sekmesine ve Karar Özeti'ne yazılır; **%30'un altındaysa puan tablosu tek
başına karar gerekçesi olarak sunulmaz.** Duyarlılık yorumu da bu orana koşulludur —
oran düşükken "sıralama değişmedi, sonuç sağlam" cümlesi yazılmaz (§4).

### Adım 7 — Tedarikçi/yüklenici yeterliliği ve risk

`references/tedarikci-yeterlilik-risk.md`. Mali/kurumsal yeterlilik, iş bitirme ve referans
doğrulaması, imalat/şantiye kapasitesi, servis ağı ve müdahale süresi, mevcut iş yükü, alt
yüklenici yapısı, menşe/tek kaynak riski; **olasılık × etki risk matrisi**.

### Adım 8 — Sözleşmesel koşullar

`references/sozlesme-maddeleri.md`. Cezai şart oranı **ve üst limiti**, gecikmenin başlangıç
anı, süre uzatım koşulları, teminat yapısı ve çözülme takvimi, fiyat revizyonu, iş
artış-eksilişi, riskin/mülkiyetin geçişi, kabul koşulları, garanti, sorumluluk sınırlaması,
mücbir sebep tanımının genişliği, fikri mülkiyet/PLC şifresi, İSG-SGK, alt yüklenici izni,
uyuşmazlık yeri.

**Teminat, sigorta ve ceza ihtiyacını her alımda değerlendir.** Gerekiyorsa yalnız
"alınmalı/konulmalı" deme: mevcut teklif koşulu ile öneriyi ayır; neden gerekli olduğunu,
önerilen tutarı, hesap dayanağını, süreyi ve uygulama koşullarını açıkla. Ayrıntılar
`references/sozlesme-maddeleri.md` §1, §3, §10 ve "Gerekçeli önerinin rapora aktarımı"nda.
İlgili açıklamaları yazılı rapora da taşı; yalnız Excel'de bırakma. Gerekmediğinde kısa
gerekçe yeterlidir. Veri eksikse dayanaksız tutar kullanma; formül, eksik girdi ve varsa işaretli
senaryo ver. Sabit bir oranı her mal/hizmete otomatik uygulama.
