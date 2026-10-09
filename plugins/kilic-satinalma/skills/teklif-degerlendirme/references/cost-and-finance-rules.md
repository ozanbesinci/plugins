# Cost and finance rules

Use these rules only with source-backed or user-supplied inputs. Never invent FX, tax, interest, payment, quantity, or market-price parameters.

## Price normalization

- Preserve price unit: per item, per 100 items, per tonne, per pack, etc.
- Compute line gross as `quantity * unit_price / price_unit`.
- Apply sequential discounts multiplicatively, never by adding discount percentages.
- Normalize every supplier to the same need quantity. Fixed installation/freight items do not scale with quantity unless the source says so.
- Respect MOQ, pack multiples, and loss/waste assumptions. Missing quantities are not zero.
- Reconcile line totals, discounts, VAT, and supplier stated total. Do not silently repair a discrepancy.

## One cost record

Every monetary effect has one stable cost identity and one owner. Store nominal amount, currency, payment date, source evidence, and cost-bridge stage. A cost already represented in a payment schedule, TCO, import bridge, or scope adjustment must not be added again.

Keep firm-specific scope completion (5-A) separate from common scope gaps missing from every offer (5-B). A common 5-B amount is allowed only when scope, amount, currency, and timing are truly common. Unpriced scope remains unknown and creates an RFI.

## Payment present value

- Use buyer cash outflows as positive and refunds/returns as negative.
- `t=0` payments are not discounted.
- Use a common valuation date.
- Discount each currency with a rate appropriate to that currency. Do not convert a deferred foreign-currency payment at spot and then discount it with a TRY rate.
- If exact dates are known use day count / 365 with an annual effective rate. Do not put an annual rate directly into a monthly exponent.
- Payment present value and nominal cash budget are separate measures.

## VAT and tax

- Non-deductible VAT is cost.
- Deductible VAT is not added to core cost; its payment/recovery timing can create a financing effect.
- VAT withholding changes who receives the VAT; it is not an additional tax.
- Import duties, additional duties, anti-dumping, stamp tax, and similar charges enter cost only when applicable and source-confirmed.
- Tax treatment requires accountant/customs confirmation when the source is not authoritative or transaction-specific.

## Decision boundaries

- Unknown is not zero.
- Abnormally low price is not an automatic exclusion; request explanation and flag risk.
- Cheapest cost, weighted score, and technical compliance are separate result axes.
- Do not claim savings unless reference scope, date, quantity, and cost basis are comparable.
