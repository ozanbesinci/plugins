# Sentetik çıktı toparlama sınırı

`SyntheticGuardRuntime.recover_document(spec=...)` yalnız `tests/.runtime` altındaki güvenilir test hostu tarafından çağrılır. Store/ajan CLI üzerinde toparlama yazıcısı yoktur. Normal üretim Word ve K29 e-posta/posta kutusu kapıları kapalıdır.

Başarılı toparlama için aynı case/operation, tüketilmiş tek izin, request/artefakt/capsule hash'i, değişmemiş kaynak/build, canlı kimlik/politika/izin süresi, beklenen context revision ve güncel bağımsız sentetik QA gerekir. Kalıcı capsule, QA öncesinde karantina ve audit bağıyla kaydedilir; model kayıp metadata'yı tamamlamaz. P5 manifesti yeni backend örneğinde doğrulanıp yüklenir; `prepare_document` ikinci kez çağrılmaz.

Toparlama işlem başına değişmez CreateNew claim tüketir. Native çökmede yalnız STARTED claim kalırsa ikinci toparlama otomatik yürütülmez. Başarılı sonuç ayrı atomik final makbuzuyla kaydedilir. Mevcut final ancak aynı hash/lineage doğrulanırsa yeniden rename yapılmadan benimsenir; yabancı final ezilmez. QA başarısız, tamamlanmış, izin süresi geçmiş veya kanıtsız EXECUTING işlemi başarıya yükseltilmez.

Bu kontrol üretim yetkisi veya gerçek Word/görsel/iş kabulü değildir. Kopya backendinin desteklemediği capsule manifesti kapalı kalır; genel yetkili onarım aracı iddiası yoktur. Eski kayıtlar capsule içermez ve tahminle toparlanmaz. Geri alma: sentetik toparlama girişini kapat; karantina, capsule, claim/final ve audit kanıtını koru.

# Ayrı Windows Python ortamı

Windows CPython venv redirector ek süreç oluşturur. Bütçeli okuyucu, güvenilir aktif yorumlayıcının gerçek base executable'ını aynı venv launcher bağıyla çağırır; paket yolu ve `sys.prefix` ayrı ortamda kalır. Job limiti tek süreç olarak korunur; belge baytları Job'a bağlamadan verilmez. Devralınmış launcher değişkeni kabul edilmez. Başlatıcı doğrulanamazsa fail-closed hata verilir.

Mekanizma kaynakları: [CPython 3.14 venvlauncher](https://github.com/python/cpython/blob/v3.14.0/PC/venvlauncher.c), [CPython getpath](https://github.com/python/cpython/blob/v3.14.0/Modules/getpath.py). Gerçek ayrı ortam testleri olmadan genel Python PASS kaydı bu ortama taşınmaz.
