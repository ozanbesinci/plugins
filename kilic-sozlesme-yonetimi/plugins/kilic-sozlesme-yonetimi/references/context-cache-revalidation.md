# Kayıtlı altgraf cache ve yeniden doğrulama

P3 cache anahtarı normalize istek, gerçekten değerlendirilen düğümler/kenarlar ve bütçenin seçim sonucuna bağlıdır. `include_related=false` iken RELATED kenarı bağlama girmez. İsteğe bağlı grup değerlendirilip dışarıda bırakılmışsa kontrol edilen bağımlılıkları da digest/SUPPORTS kapsamındadır. Bütün graph zarf/hash denetimi korunur.

Her çağrı güncel kaynak baytı, erişim, reader/policy profili, invalidation ve kapanımı yeniden kontrol eder. Cache hit bu kontrollerin veya parser dışındaki bütün işin atlandığı anlamına gelmez. Kaynak/otorite onayı ve host token tasarrufu yaratmaz.

Kalıcı paket kendi oluşturma revizyonu ve hash'iyle değişmez kalır. Dönen `basis_revision` bu kaydı; `validated_at_revision` ve sonuçtaki `semantic_version` yeni kontrolün revizyonunu gösterir. Eski paket farklı revizyonda kullanılmadan önce güncel sonuç eski revizyona projekte edilip bütçe dahil bütün alanlarıyla karşılaştırılır. Sonuç/provenance/hash uyuşmazlığı veya invalidation açık hatadır. Revizyon basamak sayısı bütçe seçimini değiştirirse eski COMPLETE paket kullanılamaz.

Farklı revizyondaki tekrar kullanım `CONTEXT_PACK_REVALIDATED` audit olayında basis/current revizyonlarını, istek/dependency ve basis/current sonuç digest'lerini kaydeder. Aynı kayıt/sonuç/revizyon için tek makbuz vardır; bu olay semantik revizyonu artırmaz. P6 değerlendirmesi ayrıca güncel `context_version` ve kaynaklı bulguları kendi makbuzuna bağlar. Geçmiş görünümü eski içeriği güncel diye sunmaz; paket ID'si tek başına güncel kabul kanıtı değildir.

Yeni algoritmanın ayrı namespace'i vardır. Eski geniş anahtarlı kayıtlar değiştirilmez/silinmez; retained kota aynı kalır. Geri dönüş eski algoritmayı kullanır, destructive migration/temizlik gerekmez. Ölçülen kazanç paket/kanıt bağı yazıları ve yerel gecikmeyle sınırlıdır; kurum hacmi, SLA, ekip veya host kabulü ayrı NOT_RUN'dır. Normal Word ve K29 kapıları değişmez.
