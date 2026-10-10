# Şartname Gereksinim Çıkarımı — Ortak Çerçeve

Şartname (veya yerine geçen gereksinim listesi) varsa bu çerçeveyle taranır. Amaç,
**uygunluk matrisinin satırlarını** üretmek: her satır ölçülebilir bir gereksinim olmalı,
"kaliteli olacaktır" gibi ölçülemez ifadeler ayrı bir listede toplanmalı (bunlar RFI ve
sonraki şartname iyileştirmesinin konusudur).

Şartname uzunsa (>15 sayfa) **tamamı** parça parça okunur ve her gereksinim **verbatim
alıntı + madde numarası** ile kaydedilir. Özet geçmek, sonradan "şartnamede vardı" diye
çıkan maddeye karşı savunmasız bırakır.

## Ortak çerçeve (her iki dal)

1. İşin/ekipmanın tanımı, adedi, kapasite/performans değerleri, ana boyutlar (tam tablo)
2. Tasarım/imalat standardı **ve EDİSYONU** — API, ASME, EN, TSE, ISO, DIN, PED, ATEX, CE,
   2006/42/EC; yapım işinde TBDY 2018, ÇYTHYE, TS 498, EN 1090 EXC sınıfı, Yapı Denetim
3. Malzeme kaliteleri — **genel metin ile detay tablosu arasındaki farka dikkat** — ve
   sertifika formatı (EN 10204 2.2 / 3.1)
4. Tasarım/işletme koşulları: sıcaklık, basınç, debi, güç, çevrim süresi, kapasite
   toleransı, verim garantisi; yapım işinde yük kabulleri, sehim limitleri, zemin sınıfı
5. Yüzey işlem / boya-kaplama sistemi: ortam-korozyon sınıfı (ISO 12944 C2…C5), kat sayısı
   ve DFT, galvaniz mikron, ceza koşulları.
   **Şartname ortam sınıfına sessizse ve yapı kıyıya yakınsa** yalnız "C4-C5 gerekebilir,
   netleştirilmeli" uyarısı düşülür — varsayım dayatılmaz; şartname söylüyorsa şartnamedeki
   değer esastır
6. Kaynak/imalat gereksinimleri: WPS/PQR/WPQ, kaynakçı sertifikaları (EN ISO 9606),
   tolerans sınıfı, atölye/saha ayrımı
7. Test ve muayene: NDT türü ve oranı, hidrostatik/pnömatik test, performans/kapasite
   testi, FAT/SAT, beton numune/karot, ankraj çekme testi; personel sertifika seviyesi
   (EN ISO 9712), raporlama ve **bedel sorumlusu**
8. 3. taraf denetim/belgelendirme (Yapı Denetim, BV/TÜV/Loyd, PED onaylı kuruluş) ve
   bedelinin kimde olduğu
9. Elektrik/otomasyon gereksinimleri: motor verim sınıfı, pano, PLC/SCADA, enstrümantasyon
10. **Kapsam sınırları:** nakliye, montaj, vinç/kaldırma, iskele, mobilizasyon, geçici
    elektrik-su, devreye alma, eğitim, hafriyat, zemin iyileştirme, altyapı bağlantıları —
    **hangisi kimde**
11. Süre (teslim/tamamlanma), iş programı formatı, gecikme cezası, teminatlar,
    ödeme/hakediş düzeni
12. **Ödeme esası:** yapım işinde teorik tonaj mı kantar tonajı mı, beton için proje
    metrajı mı irsaliye mi; makinede kabul/sevk esası
13. Garanti, yedek parça taahhüdü, arıza müdahale süresi, servis ağı
14. Dokümantasyon: kullanım kılavuzu, bakım planı, kalite dosyası (MDR), as-built, kaynak
    haritası, CE dosyası, malzeme sertifika dosyası, iş güvenliği dosyası
15. Enerji/verim garantisi ve tüketim değerleri (TCO girdisi; garanti isteniyorsa ceza
    koşulu da çıkarılır)
16. Mevcut tesis parkı ile uyum: şartname belirli marka/model/muadil şartı koyuyor mu
    (PLC, motor, salmastra, rulman, sürücü, panel markası)
17. İSG/SGK ve çevre: iş güvenliği uzmanı, SGK bildirimi, alt yüklenici izni, ilişiksizlik
    belgesi, atık yönetimi, emisyon limitleri
18. Kabul koşulları: FAT/SAT veya geçici/kesin kabul ve teminat çözülme takvimi
19. Sözleşmesel gereksinimler: teminat türleri ve oranları, cezai şart, eskalasyon/fiyat
    farkı hükmü, iş artış-eksilişi, Incoterms/teslim yeri

Dala özgü kontrol kalemleri için ayrıca ilgili dosya okunur:
`ekipman-*.md`, `is-turu-*.md`, `dal-genel-mal-hizmet.md`.

## Zorunluluk dilinin ayrıştırılması (elemeli kapının temeli)

Her gereksinim üç kovadan birine düşer — bu ayrım yapılmazsa elemeli kapı keyfîleşir:

| Kova | Dil | Sonucu |
|---|---|---|
| **Zorunlu** | "olacaktır", "sağlanacaktır", "asgari", "şart", "zorunlu" | Karşılanmazsa **eleme** |
| **Tercih** | "tercih edilir", "olması avantajdır", "istenir" | Karşılanmazsa **puan kaybı**, eleme değil |
| **Bilgi** | tanım, açıklama, mevcut durum anlatımı | Ölçüt değil |

Eleme kararı her zaman **zorunluluk ifadesinin verbatim alıntısıyla** desteklenir.

## Şartname iç çelişkileri (ayrı liste, zorunlu)

Şartname–proje–keşif arasındaki çelişkiler ayrıca listelenir:
- Aynı büyüklük için iki farklı değer (metinde 30 m³, tabloda 32 m³)
- Keşifteki miktarın projeyle uyuşmaması
- Genel metinde istenen malzeme sınıfının detay tablosunda düşürülmesi
- Birbirini dışlayan iki çözümün aynı anda istenmesi (galvaniz + boya sistemi)
- Atıf yapılan standardın edisyonunun belirtilmemesi veya yürürlükten kalkmış olması

**Bunlar teklif farklarının açıklamasıdır** ve idarece **zeyilname** ile netleştirilmelidir.
RFI sekmesinde "İDARE" muhatabına yazılır. Çelişki çözülmeden verilen sonuç, o kaleme
ilişkin olarak ön sonuçtur.
