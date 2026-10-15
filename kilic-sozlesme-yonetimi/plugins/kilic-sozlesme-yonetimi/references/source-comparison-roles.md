# Tarihsel referans ve güncel karşılaştırma hedefi

`version-compare --case-id ... --reference-version-id ... --current-target-version-id ...` yalnız aynı mantıksal belge içinde byte karşılaştırması yapar. Referansın snapshot hash'i ve mevcut erişim hakkı denetlenir; özgün dosya artık değişmişse bu bilgi gösterilir, eski snapshot güncel karar kaynağına yükseltilmez. Hedef özgün dosya hash'ine eşleşmeli, alt sürümü veya geçersizliği olmamalı. Uzun byte karşılaştırmasından sonra erişim/kaynak/CAS yeniden denetlenir.

REFERENCE_ONLY ve SELECTED_CURRENT_TARGET açıklayıcı rollerdir; decision_authority=NONE, semantic_comparison=NOT_RUN ve critical_analysis_allowed=false kalır. Bu ek CLI karşılaştırması mevcut P3 HAS_CHILD karar kapısını veya eski context/request şemalarını gevşetmez. Metin/madde hizalaması, hukuki anlam ve uzman onayı verilmez; kaynaklar değiştirilmez. Normal Word ve K29 kapıları kapalıdır.
