# Karar yeterliliği ve hard-gate kuralları

## Erken kapı

SUFFICIENCY aşaması pahalı final adımlarından önce çalışır. Amaç, karar zaten desteklenemiyorsa tam adjudication ve final görsel QA'ya token harcamamaktır.

## PRELIMINARY_ONLY tetikleyicileri

Aşağıdakilerden biri kritik ve çözülmemişse final firma önerisini durdur:

- teklif geçerlilik süresi dolmuş ve yenileme/teyit yok,
- `comparison_contract` kapsam/miktar/birim/currency/base-date/payment/VAT/Incoterm bazını eşitleyemiyor,
- bağımsız yeniden hesaplama kritik sonucu mutabıklaştıramıyor veya cost bridge residual tolerans dışı,
- toplam/para birimi/ödeme/teslim gibi kritik ticari alanlar eksik,
- şartnamenin mandatory kritik maddesinde `noncompliant`, `unreadable` veya `conflicting` ve eleme kararı çözülememiş,
- kritik fiyatlanmamış kapsamın maliyeti bilinmiyor,
- kritik kaynak okunamıyor veya controlling source/revizyon otoritesi belirsiz,
- açık kritik RFI var.

## Puanlama kapısı

Puanlama ancak:

1. hard-gate kontrolleri tamamlandığında,
2. en az iki bağımsız uygun tedarikçi kaldığında,
3. `comparison_contract` PASS olduğunda,
4. karşılaştırılan maliyet zemini aynı quantity/scope/currency/base-date/payment/VAT/Incoterm bazına normalize edildiğinde,
5. kritik kapsam eksikleri puana gizlenmediğinde

çalışır. Contract FAIL ise hesap tablosundaki ranking sonucu `suppressed_by_comparability` olarak işaretlenir ve kesin tedarikçi sırası üretilemez.

Tek tedarikçide karşılaştırmalı puan üretme. İki tedarikçide medyan/sapma gibi anlamsız istatistik kullanma.

## Geçerlilik

`quote_date` ve `validity_end` ayrı fact olmalıdır. Yalnız “30 gün geçerli” varsa son tarihi kod teklif tarihinden türetir; teklif tarihi yoksa tarih uydurulmaz.

## Kapsam

- **5-A:** firmaya özgü dahil/hariç/eksik kapsam.
- **5-B:** bütün firmalarda ortak kapsam boşluğu; ancak tutar/döviz/ödeme tarihi bütün firmalar için aynı ve kanıtlıysa ortak maliyet olabilir.
- Bilinmeyen maliyet 5-B olarak sıfıra yazılamaz.

## BLOCKED yapisal kalite

`PRELIMINARY_ONLY`, is karariyla tamamlanabilecek eksik/teyit ihtiyacidir. Buna karsilik kanitsiz `verified` fact, evidence-source hash uyusmazligi, orphan offer/supplier veya duplicate canonical grain gibi yapisal data-quality bozukluklari final `validate_run` tarafindan `BLOCKED` edilir.

## Pre-output karar bütünlüğü

REPORT başlamadan önce `claim_registry` ve pre-output `scope_ledger` PASS olmalı ve `reviewed_snapshot` dondurulmalıdır. Unsupported kritik recommendation/observation veya beklenen kaynak/tedarikçi/analiz kapsamının sessiz eksilmesi kesin sonuç üretimini engeller. Snapshot dondurulduktan sonra rapor katmanı karar girdisini canlı DB'den değiştiremez.

## v5.0.4 ek hard-gate'ler

- Odeme plani tutar/oran/anapara mutabakati gecmezse final karar yok.
- Kalem toplamlari ile verified grand total kritik farkliyse final karar yok.
- Urun/kapsam kimligi veya miktar birimi acikca esitlenemiyorsa ranking yok.
- Farkli para birimleri ayni kanitli base-currency/base-date tabanina normalize edilmediyse cost bridge/ranking yok.
- Independent recompute veya cost bridge `UNVERIFIED` ise kesin karar yok.
