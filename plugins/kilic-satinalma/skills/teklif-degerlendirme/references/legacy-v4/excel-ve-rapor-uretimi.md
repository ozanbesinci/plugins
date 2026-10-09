# Excel ve rapor uretimi - v4 quality rules retained

Use one canonical data source. Keep offer-stated total separate from comparable total cost. Show source file + locator as plain text; do not rely on hyperlinks for traceability.

Use English OOXML formula names and comma separators. Do not hide calculation defects with `IFERROR`. `openpyxl` writes formulas but does not calculate them. On Windows, a final verified workbook that depends on formulas requires real Excel recalculation/independent reconciliation when available; do not silently substitute LibreOffice as equivalent verification.

All calculated outputs must remain formula/parameter traceable where the workbook is intended to be interactive. Keep editable assumptions visibly distinct. Missing/fiyatlanmamis is not zero.

High assurance: the first accepted final render receives full visual coverage when the profile requires it; later revisions inherit PASS only for byte/render-identical page hashes and visually recheck changed pages. V5 delta-QA execution overrides older v4 instructions that would re-open every unchanged page on every revision.

Do not claim PDF delivery when PDF was not generated and opened successfully. Keep Excel/PDF tied to the same canonical decision state.
