"""Independent bounded PDF renderer for ReportLab failure; same frozen model."""
from pathlib import Path
import json
from pdf_renderer import label, scenario_rows, assumption_rows

def render_safety_pdf(model,path: Path,primary_error: str):
    import pymupdf as fitz
    font_path=Path("C:/Windows/Fonts/segoeui.ttf")
    if not font_path.is_file(): font_path=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font_path.is_file(): raise RuntimeError("Alternatif PDF fontu bulunamadı")
    font=fitz.Font(fontfile=str(font_path))
    doc=fitz.open(); page=None; y=0
    def new_page():
        nonlocal page,y
        page=doc.new_page(width=595,height=842)
        page.insert_font(fontname="KilicPDF",fontfile=str(font_path))
        y=45
    def lines(text):
        text=str(text)
        for paragraph in text.splitlines() or [""]:
            buf=""
            for char in paragraph:
                if font.text_length(buf+char,fontsize=10)>500:
                    yield buf; buf=char
                else: buf+=char
            yield buf
    def write(text):
        nonlocal y
        for line in lines(text):
            if y>780: new_page()
            page.insert_text((45,y),line,fontname="KilicPDF",fontsize=10)
            y+=15
        y+=5
    new_page()
    write("Teklif Değerlendirme — alternatif PDF üretimi")
    for key in ["content_status","decision_assurance","comparison_status","profile"]: write(label(model.get(key)))
    for text in model.get("limitations",[])+model.get("integrity_findings",[]): write(text)
    write("Kayıtlı karar eylemi: " + str(model.get("recommendation_text") or "Kesin öneri yok"))
    if model.get("summary"): write(model["summary"])
    write("Rapor teslimi satınalma onayı değildir.")
    write("Birincil PDF motoru çalışmadı; bağımsız alternatif motor kullanıldı.")
    new_page()
    write("Kaynak envanteri, teklif ve şartname ayrıntıları")
    for d in model.get("documents",[]): write(d.get("relative_path","")+" | "+label(d.get("parse_status"))+" | "+d.get("sha256",""))
    names={s["supplier_id"]:s["display_name"] for s in model.get("suppliers",[])}
    for o in model.get("offers",[]): write(names.get(o["supplier_id"],o["supplier_id"])+" | "+o["offer_id"]+" | "+label(o.get("status")))
    from pdf_bound_values import header, fields, display_amount
    for offer in model.get("offers", []):
        if offer.get("status") != "active": continue
        write(header(names.get(offer["supplier_id"],offer["supplier_id"]),offer["offer_id"]))
        for title, value, currency in fields(model,offer["offer_id"]):
            write(title + ": " + display_amount(value) + " " + str(currency or "Para birimi belirtilmedi") + ";")
    from source_price_display import pdf_rows as source_price_rows
    source_prices=source_price_rows(model)
    if source_prices:
        write("Kaynak fiyat zinciri ve beyan mutabakatı")
        write("Beyan toplamıyla ayrıca toplanmaz; KDV indirilebilirliği, ödeme finansmanı veya tam maliyet varsayılmaz.")
        for row in source_prices: write(' | '.join(row))
    write("Kaynak olguları — kullanıcı varsayımlarından ayrı")
    for fact in model.get("facts", []):
        value = next((fact[key] for key in ("value_text", "value_number", "value_date") if fact.get(key) is not None), "Bilinmiyor")
        write(str(fact.get("offer_id")) + " | " + str(fact.get("field_key")) + " | " + str(value) + " | " + label(fact.get("evidence_status")))
    write("Uygulanan kullanıcı beyanları — kaynak olguları değiştirilmedi")
    for row in model.get('buyer_declarations',[]):
        write(row['offer_id']+' | '+row['kind']+' | '+str(row['value'])+' '+str(row.get('unit') or '')+
              ' | '+str(row.get('target') or '')+' | Kullanıcı beyanı; karar/hesap teyidi ayrı. Soru: '+row['issue_id'])
    for row in model.get('buyer_quantity_totals',[]):
        write(row['offer_id']+' | Kaynak toplamı '+row['source_total']+' | Miktar esası '+row['quantity_adjusted_total']+
              ' '+row['currency']+' | '+row['limitation'])
    for calc in model.get("calculations", []):
        if calc.get("calculation_type") != "cost_summary": continue
        result = calc.get("result") or json.loads(calc.get("result_json") or "{}")
        for key, value in (result.get("buyer_inputs") or {}).items():
            write(str(calc.get("offer_id")) + " | " + key + " | " + json.dumps(value,ensure_ascii=False,default=str))
    for r in model.get("matrix",[]):
        write(r["supplier"]+" | "+r["offer_id"]+" | "+r["requirement_id"]+" | "+label(r["status"])+" | "+label(r["severity"]))
        write(r["expected"]+" | "+r["reason"])
        for key in ["spec_evidence","offer_evidence"]:
            if r.get(key):
                ev = r[key]
                write("Kanıt: " + ev["evidence_id"] + " | Belge: " + ev["document_id"] +
                      " | Konum: " + json.dumps(ev["locator"],ensure_ascii=False) + " | " + str(ev["quote"]))
    for i in model.get("open_issues",[]): write(str(i.get("question"))+" | "+label(i.get("status")))
    if not model.get("documents"): write("Güvenilir kaynak ayrıntısı bulunmuyor; veri uydurulmadı. Kaynakları ve çalışma deposunu doğrulayın.")
    write("Maliyet: doğrulanmış baz yoksa hesaplanamadı; bilinmeyen sıfır değildir.")
    write("Excel yeniden hesaplama: " + label(model.get("recalculation") or "PENDING_NATIVE_RECALC"))
    write("Kullanıcı senaryoları:")
    for sid,ref in model.get("scenario_reference",{}).items():
        assumptions=model.get('scenario_assumptions',{}).get(sid)
        if assumptions:
            write("Senaryo dayanağı ve varsayımları — " + str(assumptions['id']))
            if assumptions.get('basis'):
                write("Senaryo dayanağı: " + str(assumptions['basis']))
            for title,value in assumption_rows(assumptions):write(title+": "+value)
        write("Senaryo satırı " + sid + " — Python referans hesabı")
        for title, value in scenario_rows(ref): write(title + ": " + value)
    doc.save(path); pages=len(doc); doc.close()
    return {"available":True,"path":str(path),"renderer":"pymupdf_fallback","pages":pages,"primary_error":primary_error}
