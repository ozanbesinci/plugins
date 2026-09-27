# İthalat Maliyet Köprüsü (Incoterms → DDP Eşdeğer)

Farklı Incoterms ve farklı menşeili teklifleri **aynı teslim noktasındaki toplam maliyete**
indirgemek için kullanılır. Yurt içi bir imalatçının anahtar teslim fiyatı ile yurt dışı
bir üreticinin EXW fiyatı, bu köprü kurulmadan aynı tabloya yazılamaz.

Yapım işinde de kullanılır: yurt dışından profil/sac/panel tedarikli teklif geldiğinde bu
köprü, eşit kapsam düzeltmesinin **içinde alt satır** olarak kurulur.

## 1. Teklifin Incoterms'ini tespit et

Teklifte açıkça yazmıyorsa **varsayma, RFI'ya ekle**. İpuçları: "fabrika teslim",
"ex works", "nakliye hariç", "CIF İzmir", "gümrük dahil", "anahtar teslim",
"montaj dahil sahada teslim".

| Terim | Teslim / alıcıda kontrol edilecek giderler |
|---|---|
| EXW | Satıcı işyerinde yüklemeye hazır; yükleme, ihracat işlemleri, taşıma ve ithalat kapsamı kontrol edilir |
| FCA | Adı yazılı yerde taşıyıcıya teslim; satıcı tesisinde yükleme satıcıda, diğer teslim yerinde boşaltma ayrımı ayrıca kontrol edilir |
| FOB | Yalnız deniz/iç su taşımacılığı; sevk limanında gemide teslim, ana taşıma alıcıda |
| CFR / CIF | Satıcı adı yazılı varış limanına navlunu öder, CIF sigortayı da kapsar; risk sevk limanında gemide devreder. Tahliye/terminal giderleri taşıma sözleşmesine göre kontrol edilir |
| CPT / CIP | Her taşıma türü; satıcı adı yazılı noktaya taşımayı öder, CIP sigortayı da kapsar; risk taşıyıcıya teslimde devreder |
| DAP | Adı yazılı varış yerinde boşaltmaya hazır; boşaltma ve ithalat işlemleri/vergileri alıcıda |
| DPU | Adı yazılı varış yerinde boşaltılmış; ithalat işlemleri/vergileri alıcıda. 2020'de DAT yerine kullanılır; eski DAT teklifinde belirtilen sürüm korunur |
| DDP | Adı yazılı varış yerinde ithalat işlemleri yapılmış, boşaltmaya hazır; **boşaltma otomatik dahil değildir**. Montaj/devreye alma ve vergi ayrıştırması ayrıca kontrol edilir |

Terim tek başına yetmez: **Incoterms sürümü + adı yazılı yer + dahil hizmetler**
kaydedilir. Taşıma masrafını üstlenen ile riski taşıyan taraf aynı olmayabilir.
Hedef, kullanıcının belirlediği **aynı noktada ve aynı kullanım kapsamındaki alıcı
maliyeti**dir; "DDP eşdeğer" hesap gerçek DDP sözleşmesi/ithalatçı statüsü yaratmaz.

## 2. Köprü ve matrah hesabı

Her maliyet satırı: benzersiz kimlik, para birimi, net tutar, ödeme tarihi, kaynak,
teklife dahil/hariç, alıcı/satıcı sorumlusu ve KTM basamağı içerir.

1. Kaynak net teklif fiyatı kendi para biriminde saklanır; karşılaştırma değeri
   `net tutar × ForexSelling / Unit` ile çevrilir. Kur çarpanı **ek maliyet değildir**;
   yabancı tutar ile TL karşılığı toplanmaz.
2. Yalnız teklifte bulunmayan ve alıcının taşıdığı giderleri ekle: menşe yükleme/iç
   taşıma, ihracat işlemleri, ana navlun, sigorta, terminal/ardiye, müşavirlik ve
   varış iç taşıma/boşaltma. Gabari dışı taşıma teklif gerektirir.
3. Sigorta primi `poliçe matrahı × prim oranı`dır. Sigortalı değer, kapsam ve sigortaya
   dahil edilen artış poliçeden alınır. CIF fiyat zaten sigorta içeriyorsa yeniden
   eklenmez. CIF içine kendi primini tekrar koyan döngüsel formül kurulmaz.
4. **Gümrük kıymeti** ayrı hesap tablosudur: mevzuata göre kıymete giren satış bedeli,
   giriş yerine kadar navlun/sigorta ve diğer kıymet unsurları; zaten fiyata dahil
   olanlar tekrar eklenmez. `gümrük vergisi = teyitli matrah × oran` yalnız ad valorem
   (değere bağlı) vergi için geçerlidir. Miktara bağlı vergi varsa ilgili yöntem kullanılır.
5. Türkiye ithalatında GTİP/menşe/belgeye göre Türkiye'nin güncel tarife ve ticaret
   önlemleri esas alınır; **AB TARIC Türkiye tarifesinin yerine kullanılamaz**.
   İGV, ek mali yükümlülük, anti-damping ve ödeme şekline bağlı KKDF uygulanabilirliği
   ayrı kontrol edilir. A.TR serbest dolaşım belgesidir, tek başına menşe belgesi değildir.
6. **İthalat KDV matrahı**: gümrük kıymeti ve mevzuatın matraha dahil ettiği vergi,
   gider ve farklar üzerinden müşavirce teyit edilir. Yalnız mal bedeline KDV çarpılmaz;
   her verginin matrahı ayrı hücredir. Gümrük hesaplarında kullanılacak kur/tarih,
   karşılaştırma amaçlı TCMB kurundan farklı olabilir; ikisi etiketlenir.
7. İthalat köprüsü = **tek bir para birimine çevrilmiş net teklif + benzersiz ek
   alıcı giderleri + indirilemeyen vergiler/KDV**. Ödeme finansmanı 7., montaj kapsamı
   5-A basamağında işleniyorsa burada bilgi bağlantısı olur, yeniden eklenmez.

## 2b. Hangi vergi toplama girer, hangisi girmez

Ayırt edici soru: **alıcının bu işlemde indirim hakkı ne kadar?**

| Kalem | KTM işlemi |
|---|---|
| Alıcıda kalan gümrük vergisi, İGV, EMY, anti-damping, damga vergisi | Maliyete bir kez girer; muafiyet ve yükümlü taraf teyit edilir |
| Müşavirlik, terminal, nakliye | Teklifte yoksa ve alıcıya aitse net bedeli girer |
| KDV'nin indirilemeyen kısmı | `hesaplanan KDV × (1 − indirim payı)` maliyete girer |
| KDV'nin indirilebilir kısmı | Ana maliyete girmez; ödeme ile gerçekçi mahsup/iade tarihinin NBD farkı finansman basamağına girer |
| KDV tevkifatı | Aynı KDV'yi satıcı/vergi dairesi arasında böler; yeni bir vergi değildir, oranı işlem bazında teyit edilir |

`net fiyat = KDV dahil fiyat / (1 + o satırın KDV oranı)`.
Birden çok vergi oranı varsa satır bazında ayrıştırılır. İndirim hakkı bilinmiyorsa
varsayım ve iki senaryo gösterilir; %100 indirilebilir kabulü kesinleştirilmez.
Teşvik beklentisi ile yürürlükteki belge ayrılır; belge alınacak diye baz maliyet
sıfırlanmaz. Teşvikli durum ayrıca koşullu senaryodur.

**KTM etiketi "indirilebilir KDV hariç"**, nakit bütçesi ise KDV ödemeleri dahil ayrı
gösterilir. Gider yazılabilmek ile KDV indirim hakkı aynı şey değildir.

## 3. Kurallar

- **Vergi ve oran bilgileri teyit gerektirir.** GTİP kodu, vergi oranı, teşvik kapsamı ve
  KDV uygulaması için gümrük müşaviri / mali müşavir teyidi şarttır. Excel'de bu hücreler
  sarı+mavi (düzenlenebilir varsayım) işaretlenir ve "müşavir teyidi bekleniyor" notu
  düşülür.
- Oranlar **tek bir hücrede** tanımlanır, tüm firmalar aynı oran hücrelerine formülle
  bağlanır — böylece oran düzeltilince tüm firmalar birlikte güncellenir.
- **Yerli teklif için de köprü kurulur:** yerli imalatçının fiyatı KDV hariç mi, nakliye ve
  montaj dahil mi, sahada boşaltma kimde — bunlar da eklenir. Aksi hâlde köprü tek taraflı
  olur ve yerli teklif haksız avantaj/dezavantaj kazanır.
- **Teslim süresi de bu adımda düzeltilir:** EXW teklifin "8 hafta" teslim süresine navlun
  ve gümrükleme süresi (deniz için tipik 3-6 hafta + gümrük 3-10 gün) eklenerek **saha
  teslim süresi** bulunur ve puanlamada bu kullanılır.
- Köprü kurulduktan sonra Özet sekmesinde şu cümle görünür olmalı: **"Teklif fiyatı
  sıralaması ile DDP eşdeğer sıralama farklıdır/aynıdır."**

## Kaynaklar (2026-09-05 kontrolü)

- [ICC — DDP ve boşaltma](https://academy.iccwbo.org/incoterms/article/incoterms-2020-exw-or-ddp/): DDP boşaltmayı otomatik satıcıya yüklemez.
- [ICC — taşıma türleri ve DPU](https://library.iccwbo.org/clp/clp-incoterms-qa-2020.htm?AGENT=ICC_HQ): terimler sürüm ve taşıma türüne göre ayrılır.
- [Ticaret Bakanlığı — gümrük kıymeti](https://www.ticaret.gov.tr/gumruk-islemleri/sikca-sorulan-sorular/ticari/gumruk-kiymeti): satış bedeli ve kıymet unsurları.
- [GİB — indirilemeyen KDV](https://gib.gov.tr/mevzuat/kanun/436/sirkuler/924): indirim hakkının istisnaları vardır.

Bunlar yöntem kaynaklarıdır; güncel GTİP/vergi oranı ve işlem kapsamı her alımda ayrıca teyit edilir.
