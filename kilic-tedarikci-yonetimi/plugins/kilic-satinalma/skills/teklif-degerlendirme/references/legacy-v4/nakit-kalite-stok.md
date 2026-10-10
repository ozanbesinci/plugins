# Nakit, kalite ve stok - v4 business rules retained

Apply these modules only when relevant; missing data means `not calculated/partial/scenario`, not silent zero.

## Cash
Build dated nominal cash flows; do not discount the cash-budget table. Keep separate: largest single-period payment, maximum cumulative cash requirement, and incremental financing need after known allocated cash/limits. Deductible VAT offset is not automatically a bank cash inflow. Deposit/blockage cash and guarantee-letter nominal face value are different. Cash peak is not an extra KTM cost.

## Quality loss
Use traceable defect/return/rework data; never invent a supplier defect rate. Separate prevention/inspection cost from failure cost. Do not count the same lost item, replacement, refund, rework or downtime twice. Monetized downtime already included in TCO must not be added again. Use only new unique cost events.

## Stock and ordering
Compare scenarios on the same demand horizon. Distinguish order date, delivery date, ownership/risk transfer and payment date. `Q/2 + safety stock` is valid only under its restrictive regular-demand assumptions; otherwise use dated inventory. Order count is integer. Negative stock means unmet demand. A scenario that violates capacity, shelf life or required delivery cannot win only because it is cheap. If financing PV already captures capital cost, do not add the same stock carrying capital cost again.
