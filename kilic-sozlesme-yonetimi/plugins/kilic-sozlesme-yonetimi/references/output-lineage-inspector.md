# P4 salt-okunur çıktı teşhisi

`output-inspect --case-id ...` bilinen case işlem lineage'ında karantina/ready/final dosyasını DB state ve bound artifact SHA ile karşılaştırır. Final var ama commit/hash bağı eksik, final eksik, yabancı hash, ready veya karantina kalıntısı ayrı görünür. İşlem digest/binding/request veya path bağı bozuksa kapalı ret verir. Case dışında kayıt paylaşılmaz; büyük/alias dosya okunmaz.

Bu inspector teslim/Word QA/şirket yetkisi değildir. delivery_confirmed=false, recovery_action=NONE, production_ready=false kalır. Permission sütun/payload tutarlılığı HMAC kimlik doğrulaması değildir; signature_verification=NOT_RUN. Kaynak güncelliği, gerçek kimlik/QA ve DB kaydı olmayan global orphan taraması NOT_RUN; başka case'e ait kalıntı tahminle bağlanmaz.

Kaynak ingest journal reconcile ayrı kalır. Inspector dosya taşımaz/silmez, permission yenilemez/tüketmez, state yazmaz ve otomatik republish yapmaz. Kontrollü sentetik recovery ayrı PR'dır; normal Word ve K29 kapıları kapalıdır.
