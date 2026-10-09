# Import and TCO rules

## Import / DDP-equivalent bridge

Do not compare EXW/FOB/CIF/DAP/DDP offers directly without a common destination and scope.

Record Incoterms term, version, named place, included services, and risk/cost responsibilities. Add only buyer-borne costs not already included in the offer. Keep customs valuation and comparison FX logic distinct when law requires a different customs rate/date. Do not use EU TARIC as a substitute for Turkey-specific tariff treatment.

A DDP-equivalent calculation is an analysis bridge; it does not make the contract legally DDP or change importer status. Local offers need the same delivery-scope bridge: freight, unloading, installation, and site delivery must be comparable.

## TCO

Use TCO only when lifecycle costs are material. Candidate rows include energy, consumables, planned maintenance, spare parts, downtime, replacement, and end-of-life value/cost.

Do not fabricate annual hours, energy price, downtime cost, inflation, or discount rates. If unavailable, leave the component unpriced, create an RFI, and use transparent scenarios only when the user supplies or approves parameters.

Keep rate basis consistent:

- constant/current-price cash flows use a real discount rate;
- nominal escalated cash flows use a nominal discount rate;
- `real = (1 + nominal) / (1 + inflation) - 1`.

Do not approximate the real rate as nominal minus inflation when rates are material.

Show acquisition cost, lifecycle present value, and total separately. For a higher-price/lower-operating-cost option, calculate simple or discounted payback only when the savings series supports it; otherwise state that payback is not reached or cannot be calculated.
