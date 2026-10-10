# Çalıştırıcı ve teslim kapıları — v4

`scripts/ajan_yonetimi.py` giriş noktasıdır; `ajan_v4.py` yerleşik alt ajanların
kayıtlarını yönetir. Kendi başına model çağırmaz. Her komutun seçenekleri için
`python "<runner>" <komut> --help` kullanılabilir. Yollarda boşluk varsa tırnakla.

## Hazırlık

İlk adım aktif ana oturumun model/efor kontrolüdür; otomatik `guncelleyici`
tarama/kurulum akışı ve `@@SONUC` ön koşulu yoktur. Önce şu salt okunur kontrolü yap:

```text
python "<skill>/scripts/oturum_kontrol.py" --main-log "<aktif-ana-oturum.jsonl>" --session-id "<aktif-oturum-kimliği>"
```

`READY` yalnız gerçek GPT-6.1/High seçimiyle gelir. `WAITING_FOR_SELECTION` veya
`UNVERIFIED` durumunda analizi başlatma; gerekli seçimi bildir ve kullanıcı yanıtını
bekle. Her yeni yanıtta aynı güncel oturumu yeniden kontrol et; yanlış seçim
sürdükçe uyarıyı tekrarla. Kullanıcının “değiştirdim” veya “devam et” demesi tek
başına geçiş izni değildir. Doğrulanınca başlangıç mesajı ve analiz hazırlığına geç.

Ayrı `ortam_ve_belge.py` ortam kontrolünü çalıştırma; scriptin
`--help` çıktısındaki belge çıkarma komutunu analiz sırasında kullan. PDF görüntüleme pypdfium2,
metin çıkarma pdfplumber/pypdf, Excel üretimi openpyxl, Excel hesaplatma pywin32'dir.
Paket sürümleri `requirements.txt` ile eşleşir. Gereken analiz aracı kullanılamıyorsa
somut engeli bildir; `guncelleyici`yi otomatik açma. Kurulum/güncelleme yalnız ayrı
kullanıcı isteğiyle yapılır; buradan pip, wheel veya ayrı Python kurulumu yapılmaz.

Katalog JSON'u: `source` gözlenen araç/katalog kaynağı, `observed_at` saat dilimli
ISO zaman, `models` gerçek `id` ve desteklenen `efforts` listesidir. Sunulmamış
model kimliği üretme; eski önbelleği güncel gözlem gibi etiketleme. Hazırlıktaki
katalog gözlemi en fazla 5 dakika eski olabilir. Yeni koşuda
katalog tekrar okunur; `gpt-6.1-sol` ve `high` desteği doğrulanır, bütün rol
kimlikleri manifestte sabitlenir. Ana sohbet de aynı model ve High eforunu kullanır.

Bağlam JSON'u profil önericinin alanlarını taşır:
`has_spec` boolean, `purchase_type` (`genel_mal_hizmet` genel mal/hizmet için),
`imported` boolean, `has_tco` boolean; isteğe bağlı `max_amount` ve `fast_limit`.
Tutar sınırı tanımlı değilse null bırakılır. İthalat ve TCO birlikte yüksek güvence;
şartnamesiz genel yerli iş hızlı; diğerleri standart önerilir.

```text
python "<skill>/scripts/ajan_yonetimi.py" prepare --source "<kaynak>" --run "<yeni-koşu>" --catalog "<katalog.json>" --main-log "<gerçek-ana-oturum.jsonl>" --context "<bağlam.json>" --profile standart --log-root "<gerçek-sessions-kökü>"
```

İsteğe bağlı `--sources` göreli kaynak yollarının JSON listesidir; envanterden
çıkarılan dosya gerekçesi saklanır. Liste kullanılmazsa tüm uygun kaynaklar taranır.
`--downgrade-reason` önerilenin altındaki profil için kullanıcının uyarı sonrası
teyit/gerekçesidir. Teknik tercihi kullanıcı beyanıymış gibi yazma.

Koşu dizini yeni olmalı; kaynak altında olacaksa `analiz/` altında tutulur.
Kaynaklar ve skill değişmez kopyaya alınır; kopyalama öncesi/sonrası hashler
karşılaştırılır ve kaynak/orijinal hashleri izlenir.
Hazırlık dönen `runner` yolu sonraki bütün komutlarda kullanılır. Eski v3 manifesti
yerinde v4'e dönüştürülmez.

## Yerleşik görev yaşam döngüsü

```text
python "<runner>" task --run "<koşu>" --role extraction --purpose "<dar amaç>"
python "<runner>" bind --run "<koşu>" --task "<görev-id>" --log "<gerçek-alt-oturum.jsonl>"
python "<runner>" seal-result --run "<koşu>" --task "<görev-id>" --path "<görev-dizini/sonuç.json>"
python "<runner>" register --run "<koşu>" --task "<görev-id>" --path "<görev-dizini/sonuç.json>"
```

Sıra:

1. `task` beklenen model/efor, görev kimliği, kaynak envanteri ve çıktı dizinini verir.
2. Koordinatör yerleşik araçla **yeni** alt ajan açar; tüm sohbet geçmişini vermez,
   çağrıda beklenen model/eforu açıkça belirtir.
3. Ana ajan gerçek alt oturum günlüğünü `bind` ile hemen bağlar. Alt ajan sonuç
   kaydını mühürlemeden bağlama tamamlanmış olmalıdır; sayaç görünür kalır.
4. **Alt ajan kendi oturumunda** `seal-result` çalıştırır. Araç çıktısındaki
   `TEKLIF_RESULT_SEAL` işareti aynı alt ajanın günlüğüne düşer.
5. Sonuç tamamlanınca ana ajan `register` ile günlüğü, gerçek model/eforu ve
   dosya hash'ini doğrulatır. Ana oturumda üretilmiş bir mühür bağımsız kanıt değildir.

Ana sohbetin modeli ve eforu her yeni görevde yeniden denetlenir; hazırlıktan sonra
GPT-6.1/High dışına geçmek yeni görevi engeller. Farklı model/efora geçip tekrar
doğru seçime dönülmesi de koşu içindeki uyuşmazlığı kaldırmaz.

Aynı oturum kimliği başka görevde kullanılamaz. Alt ajan ana oturumun doğrudan
çocuğudur ve başka ajan açamaz. `task --phase revision` de yeni oturum açar.
Planlanan fakat açılmayan görevi `cancel --task ... --reason ...` ile iptal et;
çalışan görevin kaydını silerek tüketimi saklama.

## Veri, bağımsız okuma ve hakem

`record --run ... --kind ... --path ...` ile koşu içindeki dosyalar hash'leriyle
kaydedilir. Başlıca türler:

| Tür | İçerik |
|---|---|
| `data` | Merkezi `teklif-data/v4` JSON |
| `coverage` | Her özgün dosyanın okunmuş/okunamamış/uygulanmıyor kapsam kaydı |
| `blind` | Kabul edilmiş bağımsız rolün sonuç JSON'u |
| `verdict` | Kabul edilmiş GPT-6.1/High hakem sonucu |
| `decision` | Güncel veriye bağlı GPT-6.1/High karar özeti |
| `workbook`, `excel_receipt` | Excel ve gerçek hesap/doğrulama raporu |
| `pdf`, `visual` | Yüksek güvence PDF'i ve gerçek görsel gözlemler |

`data` değişince bağlı QA, hesap, Excel/PDF ve karar kayıtları geçersiz olur.
Kayıtlı dosyayı yerinde değiştirme; yeni revizyon dosyası üretip kaydet.

```text
python "<runner>" qa --run "<koşu>"
python "<runner>" compare --run "<koşu>"
python "<runner>" task --run "<koşu>" --role adjudicator --purpose "<farklar ve karar özeti>"
python "<runner>" apply --run "<koşu>" --output "<koşu/merkezi-veri-v2.json>"
```

Hakemden önce QA geçmeli, bağımsız görev tamamlanıp kayıt altına alınmalı ve kodla
fark listesi üretilmelidir. `qa`, veri/kapsam kontrolünün ardından taslak Excel'i
kendisi üretir ve `excel_dogrula.preflight` ile düzen, formül ve girdi sözleşmesini
sınar. Bu aşamada gerçek COM hesaplatması yapılmaz; taslağı ayrıca workbook olarak
kaydetme. Son karar özeti geldikten sonra üretilen son Excel gerçek COM'dan bir
kez geçirilir ve yalnız bu son dosya/rapor teslim artefaktı olarak kaydedilir. `apply` yalnız gerçek hakem oturumuna ve güncel
veri/fark hash'ine bağlı kanıtlı düzeltmeyi kabul eder. Ardından QA ve etkilenen
hesap/Excel doğrulamasını yenile. Düzeltme olmayan hakem kararı da uygulanır ve
güncel sonuçla bağı kurulur. Bundan sonra `task --role decision_summary` ile yeni
GPT-6.1/High görevini aç, güncel veri hash'ine bağlı summary/recommendation sonucunu
bind/seal-result/register döngüsünden geçir ve `record --kind decision` ile bağla.

## Teslim kapısı

`verify --run ...`: kaynak ve skill hashleri, rol makbuzları, dosya kapsamı,
kritik bilgi tamlığı, hakem kaydı, güncel Excel hesap raporu ve profile özgü
PDF/görsel kontrolleri bir araya getirir.

- `VERIFIED`: zorunlu kontroller geçti, kritik açık konu yok.
- `PRELIMINARY`: doğrulanan işin açık bilgileri veya bütçe sınırı var; kesin firma
  önerisi yok, muhataplı RFI ve sınırlar görünür.
- `BLOCKED`: eksik/başarısız kontrol veya tutarsız kayıt var; doğrulanmış teslim
  denmez. Kullanıcıya mevcut durumu ve somut engeli bildir; makbuz uydurma.

`close --run ...` teslim kapısını çalıştırıp zamanı ve bütçe değerlerini dondurur;
sonradan ana sohbetin tüketimi kapanmış koşuya eklenmez. BLOCKED koşuyu
başarılı kapatmaz. `status --run ...` profil, görevler, kayıtlar ve güncel bütçeyi verir.

## Bütçe ve güncelleme

Her benzersiz oturumun son birikimli girdi/çıktı toplamı bir kez sayılır; ana sohbetin
koşu öncesi sayacı düşülür. Gerçek alt oturumlar ve saptanan alt soylar dahil edilir.
Eksik telemetride yeni görev açılmaz. %80 uyarısına kullanıcının yanıtı
`ack-budget --reason ...` ile kaydedilir; bu tavanı artırmaz. %100'de yeni görev yoktur.

Güncelleme kilidinde yeni snapshot hazırlanmaz. Başlamış v4 koşusu kendi sabit
kopyasıyla devam edebilir. Eski global analiz kilidi ve yarım işlem kaydı otomatik
silinmez. Kaynak veya skill kopyası değiştiyse yeni koşu gerekir.
