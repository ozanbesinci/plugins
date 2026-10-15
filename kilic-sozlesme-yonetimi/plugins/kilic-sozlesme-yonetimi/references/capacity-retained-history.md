# Kayıt kapasitesi

`capacity --case-id <uuid>` salt-okunur kota görünürlüğüdür.512 node/512 pack/2048 ilişki, mevcut iş ledger limitleri,256 işlem/2048 karar, sürüm başına256 kontrol ve render başına3 gözlem mevcut sabitlerden okunur; limitler artırılmaz. Kullanılmış/kalan/tam/aşılmış sayıları case veya ilgili kaynak sürümü kapsamında hesaplanır. Bilinmeyen case'e veri verilmez.

Kota bütün retained satırları sayar. Geçersizleşen kayıt geçmişte kalır ve kapasiteyi serbest bırakmaz. Context pack current_revision_rows/older_revision_rows ayrımı yalnız semantik revizyon eşliğidir; kullanılabilirlik veya belge/iş doğruluğu onayı değildir. Diğer kayıtların semantik active/historical durumu bu basit counter'dan çıkarılmaz. Bu sınır açıkça semantic_validity_checked=false olarak döner.

Silme, taşıma, prune, arşiv veya retention kararı yoktur. Şirket saklama politikası, gerçek kullanım hacmi ve latency kabulü NOT_RUN. K29/normal Word kapıları ve tarihsel audit/izin kayıtları korunur.
