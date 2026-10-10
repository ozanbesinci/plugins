# Teslim ve dogrulama - v4 acceptance rules retained

Verify source/hash coverage, revisions, supplier/offer mapping, requirement coverage, evidence locators, quantity/unit/tax/FX/payment basis, unique cost IDs, hard gates, unresolved RFI, scoring eligibility and output QA.

Independent review must be genuinely independent for the facts it is assigned. In v5, deterministic/secondary-parser agreement is accepted automatically where the policy allows it; only actual disagreements or required blind-review facts go to adjudication. Never send unchanged decisions to a revision adjudicator.

Delivery states:
- VERIFIED: mandatory gates passed and no critical open issue remains. This is not corporate purchase approval.
- PRELIMINARY: useful validated analysis exists, but critical information or comparability is open; no definite supplier recommendation.
- BLOCKED: source/parser/schema/calculation/output QA chain is not reliable enough to claim completion.

When a source revision changes, create a new run/output revision. Preserve unanswered RFI and change history, but never transfer an old hash-bound approval/QA receipt to changed content.

Synthetic tests do not prove live production performance. Organization-wide rollout should use controlled live acceptance on representative procurements and record actual token/time/quality telemetry.
