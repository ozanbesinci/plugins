# Legacy v4 business-rule library

These files preserve non-obvious procurement/domain rules from v4.0.5 so the v5 deterministic architecture does not lose business knowledge.

Use them only as domain and quality references. Do NOT copy v4 orchestration, fixed-model, token-budget, full-context reread, or full-revision visual-QA instructions from older material. `SKILL.md`, `config/policy.json`, `references/architecture.md`, `references/agent-routing.md`, and `references/qa-and-output.md` are authoritative for v5 execution.

Load only the relevant domain file:

- `dal-genel-mal-hizmet.md`: general goods/services/rental.
- `ekipman-*.md`: equipment-family technical controls.
- `is-turu-*.md`: construction-family technical controls.
- `poz-eslestirme-normalizasyon.md`: item mapping, units, quantities and abnormal-price signals.
- `sartname-gereksinim-cikarimi.md`: requirement extraction framework.
- `sartname-yoksa.md`: no-specification mode.
- `teklif-sayisi-modlari.md`: supplier-count-specific method.
- `nakit-kalite-stok.md`: cash, quality-loss and stock scenario rules.
- `excel-ve-rapor-uretimi.md`: spreadsheet/output invariants retained from v4.
- `teslim-ve-dogrulama.md`: delivery-level acceptance rules retained from v4.
