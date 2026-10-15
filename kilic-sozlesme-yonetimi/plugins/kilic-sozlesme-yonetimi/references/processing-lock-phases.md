# İşleme kilidi ve kaynak/CAS yeniden kontrolü

İlk kısa DB işlemi case revizyonu, sürüm/storage/source bağı, snapshot baytları, özgün dosya hash'i ve cache profilini sabitler. Native ayrıştırma, JSON çözümleme/şema kontrolü ve serileştirme DB kilidinin dışında yapılır. İkinci DB işlemi aynı case revizyonu, source erişimi/hash, snapshot hash, sürüm satırı, geçersizleştirmeler ve reader build kimliğini yeniden denetler. Değişiklikte kapalı ret; yarım işleme kaydı yoktur. İki gerçek parser aynı profili eşzamanlı işlese de tek işleme kaydı oluşur; farklı sonuç veya kaybolan önceki kayıt başarı sayılmaz.

Ürünün varsayılan lock_timeout=5 saniye politikası değişmedi. Yük altında KILIT_MESGUL gerçek ret sonucu olarak görünür, başarıya çevrilmez. CAS/replay/cache tekillik testlerindeki60s yalnız bu özelliği test etme beklemesidir;5s müşteri gecikmesi kabulü değildir. Ayrı meşgul kilit negatifleri korunur. Kurumsal yük/latency kabulü ölçümü henüz NOT_RUN; CONS-028 tamamen kapalı sayılmaz.

Native iki parser aynı anda extractor'a girme, gerçek başka CLI sürecinin parser sırasında beyan kaydetmesi ve eski CAS sonucunun yayımlanmaması sınanır. Kaynak değişimi ve parser hata negatifleri ayrı tutulur. K29 ve normal üretim Word kapıları değişmez.
