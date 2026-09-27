# Tedarikçi / Yüklenici Kurumsal Yeterlilik ve Risk Matrisi

Ucuz ve teknik olarak uygun bir teklif, **teslim edilemezse veya iş yarıda kalırsa**
değersizdir. Yapım işinde yarım kalan iş, teslim edilmeyen makineden daha maliyetlidir
(sahada kısmi imalat, ara yüz sorunları, yeni yükleniciye devir zorluğu). Bu modül
"firma bu işi gerçekten yapabilir mi ve yaparsa yanımızda durur mu" sorusunu ölçer.

## 1. Kurumsal ve mali yeterlilik

| Alan | Ne aranır | Değerlendirme |
|---|---|---|
| Kuruluş ve süreklilik | Kuruluş yılı, ortaklık yapısı, unvan değişiklikleri | Yeni firmada teminat ve hakediş yapısı sıkılaştırılmalı |
| Mali büyüklük | Yıllık ciro, öz kaynak, banka referans mektubu | **Sözleşme bedeli / yıllık ciro oranı kritiktir:** iş, cironun büyük bölümünü oluşturuyorsa taahhüt riski yüksektir |
| İmalat kapasitesi | Kapasite raporu, atölye alanı, aylık ton imalat kapasitesi, tezgâh parkı (CNC kesim, kaynak robotu), boya/kumlama hattı veya galvaniz anlaşması, personel sayısı | Süre taahhüdüyle tutarlı mı: **beyan tonaj / aylık kapasite ≥ taahhüt edilen imalat süresi** olmalı |
| Şantiye/montaj kapasitesi | Montaj ekip sayısı, vinç/platform parkı (kendi mi kiralık mı), şef ve formen kadrosu | Aynı anda kaç şantiye/proje yürütebiliyor |
| Kalite sistemi | ISO 9001; işe göre EN 1090 FPC (EXC sınıfı), ISO 3834, ISO 45001, ASME U-Stamp, ISO 22000/hijyenik tasarım | **Belge geçerlilik tarihi ve kapsamı** kontrol edilir |
| İş bitirme | Benzer nitelik/kapasite ve ölçekte tamamlanmış işler | "Benzer" tanımı: aynı ekipman türü veya yapı tipi + karşılaştırılabilir kapasite/tonaj/alan + benzer detay karmaşıklığı |
| Mevcut iş yükü | Devam eden projeler/şantiyeler ve teslim takvimleri | Aynı dönemde birden fazla büyük iş varsa gecikme riski |

**Sözleşme bedelinin cirosuna oranı yüksek + yüksek avans talebi + düşük teminat kabulü**
birleşimi **kırmızı çizgi adayıdır.**

## 2. Referans ve saha/şantiye doğrulaması

Referans listesinden **en az iki işverenin/tesisin fiilen aranması** ve mümkünse bir
tamamlanmış işin yerinde görülmesi öneri listesine yazılır. **Bu skill arama yapmaz —
soru setini üretir.**

**Referans soru seti — makine/ekipman:** teslim tarihinde tutuldu mu, devreye almada kaç
gün kaybedildi, garanti döneminde arıza sayısı, servis yanıt süresi, yedek parça temin
süresi, tekrar aynı firmadan alır mıydınız.

**Referans soru seti — yapım işi:** süreye uyuldu mu, hakediş/metraj uyuşmazlığı yaşandı
mı, iş artışı talepleri makul müydü, İSG performansı, eksik-kusur listesi ne kadar sürede
kapandı, kesin kabulde sorun çıktı mı, tekrar çalışır mıydınız.

Devam eden şantiye veya fabrika ziyareti (düzen, İSG, ekipman parkı) **sözleşme öncesi
adım** olarak önerilir. Referans verilmemişse veya farklı ürün grubuna/yapı tipine aitse
**bu bir bulgudur**, RFI'ya girer.

## 3. Satış sonrası kapasite (makine dalı — tesis konumu belirleyicidir)

Şirketin tesisleri Muğla/Bodrum-Milas hattında olduğu için servis mesafesi kâğıt üstünde
küçük görünen ama pratikte belirleyici bir kalemdir: büyük şehirlerdeki servis ağı burada
"aynı gün" demez.

- En yakın servis noktası ve mesafe/ulaşım süresi; gıda/su ürünleri tesislerinde
  **hafta sonu ve gece müdahale** kabiliyeti
- Taahhüt edilen arıza müdahale süresi (saat/gün) ve bunun **sözleşmede yazılı olup
  olmadığı** — yazılı değilse taahhüt sayılmaz
- Türkiye'de teknik servis ekibi var mı, yoksa yurt dışından mı geliyor (vize/uçuş süresi
  gecikme yaratır)
- Yedek parça stoğu Türkiye'de mi, sipariş süresi kaç hafta
- Uzaktan bağlantı/teletanı imkânı (PLC'li ekipmanlarda arıza süresini kısaltır)
- Türkçe dokümantasyon ve Türkçe operatör eğitimi

## 4. Alt yüklenici, tedarik zinciri ve menşe riski

- **Hangi işler alt yükleniciye veriliyor** (boya, montaj, nakliye, kablolama tipik) —
  ana firma tam sorumluluğu kabul ediyor mu, alt yüklenici işveren onayına tabi mi
- **Kritik bileşen markası ve menşei** (motor, sürücü, PLC, salmastra, rulman, valf) —
  tek kaynağa bağımlılık var mı
- Ana malzeme tedarik kaynağı: hazır profil/sac stoğu mu sipariş mi; hammadde fiyat
  dalgalanmasında temin riski
- Galvaniz/boya dış hizmetse: tesis, kazan boyu, kapasite randevusu
- İhracat kısıtı / lisans gerektiren bileşen var mı
- Bileşen tedarik süresi teslim taahhüdünü riske atıyor mu (uzun tedarik süreli sürücü/PLC)
- Menşe ülke lojistik riski (gümrük, sevkiyat yoğunluğu, mevsimsel navlun)

## 5. Risk matrisi (Excel sekmesi)

Her risk için: **tanım | firma | olasılık (1-5) | etki (1-5) | skor (=olasılık×etki) |
azaltıcı önlem | sözleşmede karşılığı var mı.**

Skor renklendirmesi: **1-6 yeşil, 8-12 sarı, 15-25 kırmızı.**

**Standart risk listesi (her işte kontrol edilir):**
1. Teslim gecikmesi / süre aşımı — iş programından sapma
2. İşin yarıda bırakılması veya teslim edilmemesi (mali yetersizlik, anormal düşük fiyat)
3. Kapasite/performans taahhüdünün saha koşullarında karşılanmaması
4. Metraj/hakediş uyuşmazlığı ve iş artışı talepleri
5. Kapsam boşluğundan doğan ek talep (montaj, vinç, iskele, altyapı, testler)
6. Kur artışı / eskalasyon veya fiyat revizyon maddesi kaynaklı fiyat baskısı
7. Yüksek avans + firma mali riski
8. Kalite kusuru: kaynak/NDT bulguları, boya yetersizliği (agresif ortamda erken korozyon)
9. Servis müdahale gecikmesi ve duruş
10. Yedek parça bağımlılığı ve fiyat artışı
11. Ara yüz sorunları (betonarme-çelik ankraj aplikasyonu, ekipman-yapı bağlantıları)
12. İSG olayı ve iş durdurma
13. SGK/vergi borcu nedeniyle teminat iadesi/ilişiksizlik sorunları
14. Alt yüklenici kalitesi ve ana firma kontrol zafiyeti
15. Belgelendirme eksikliği (CE/PED, EN 1090/Yapı Denetim) nedeniyle işletme izni veya
    yasal sorun
16. Şartname-proje çelişkisinden doğan yorum farkı ve sonradan uyuşmazlık

**Her kırmızı skorlu risk için** ya sözleşmesel bir karşılık (teminat, ceza, taahhüt,
sorumluluk matrisi) ya da bir **kırmızı çizgi maddesi** üretilmelidir. Karşılığı olmayan
kırmızı risk Karar Özeti'nde ayrıca listelenir.

## 6. Puanlamaya bağlanma

Bu modülün çıktısı puanlama matrisindeki yeterlilik ve servis kriterlerine **gerekçe olarak**
bağlanır:
- Makine dalı: "Tedarikçi kurumsal/mali yeterlilik ve referans" ve kısmen
  "Garanti/servis/müdahale süresi"
- Yapım dalı: "Yüklenici kurumsal/mali yeterlilik ve iş bitirme" ve
  "Şantiye organizasyonu/ekipman/İSG"

Her puanın **gerekçe sütununda bu sekmedeki bulguya atıf** yapılır.

**Risk skoru hesap sınırı:** 1–5 olasılık ve etki puanlarının çarpımı önceliklendirme
göstergesidir; yüzde olasılık veya TL beklenen kayıp değildir. Parasal risk
hesaplanacaksa dayanaklı gerçekleşme olasılığı × ilave kayıp tutarı ayrıca kurulur;
KTM/TCO'da zaten yer alan kayıp ikinci kez eklenmez.
