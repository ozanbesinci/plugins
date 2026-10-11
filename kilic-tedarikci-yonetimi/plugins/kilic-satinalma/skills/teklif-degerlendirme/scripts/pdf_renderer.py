"""Platform-independent PDF from a frozen report model; no workbook execution."""
from __future__ import annotations
import json
from pathlib import Path
from xml.sax.saxutils import escape

LABELS = {"NO_DECISION":"Karar verilemedi","BLOCKED_INTEGRITY":"Bütünlük engeli",
          "PRELIMINARY":"Ön değerlendirme","SAFETY_NOTICE":"Güvenli bildirim","FULL":"Değerlendirme raporu",
          "BLOCKED":"Karşılaştırma yapılamadı","NO_ELIGIBLE_OFFERS":"Uygun teklif kalmadı",
          "NOT_APPLICABLE_SINGLE_SUPPLIER":"Tek bağımsız tedarikçi; rekabetçi sıralama uygulanamaz",
          "COMPLIANT":"Uygun","NONCOMPLIANT":"Uygunsuz","NOT_STATED":"Belirtilmemiş",
          "REQUIRES_CONFIRMATION":"Teyit bekliyor","CONFLICTING":"Çelişkili","UNREADABLE":"Okunamayan",
          "NOT_APPLICABLE":"Uygulanamaz","CRITICAL":"Kritik","MEDIUM":"Orta",
          "EXCLUDE_OFFER":"Teklifi ele","BLOCK_RECOMMENDATION":"Öneriyi engelle","WARNING":"Uyarı","NONE":"Yok"}
LABELS.update({"read":"Okundu", "active":"Aktif", "open":"Açık", "critical":"Kritik", "medium":"Orta",
               "PENDING_NATIVE_RECALC":"Excel yeniden hesaplama bekliyor",
               "NATIVE_RECALCULATED":"Excel ile yeniden hesaplandı"})

SCENARIO_LABELS = {"Miktar ve Kapsam!B":"Net kalem tutarı", "Kur Vergi Ithalat!B":"Hedef para net tutarı",
    "Kur Vergi Ithalat!C":"İthalat matrahı", "Kur Vergi Ithalat!D":"Gümrük ve indirilemeyen vergi",
    "Kur Vergi Ithalat!E":"Brüt nakit bedeli", "Kur Vergi Ithalat!F":"Maliyet baz tutarı",
    "Odeme NBD Nakit!B":"Nominal ödeme", "Odeme NBD Nakit!C":"Tek ödeme net bugünkü değeri",
    "TCO Yasam Dongusu!B":"Nominal yaşam döngüsü toplamı", "Puanlama Duyarlilik!B":"Ağırlıklı senaryo puanı",
    "Puanlama Duyarlilik!C":"Teknik ağırlık artınca senaryo puanı", "Senaryo Karsilastirma!B":"Baz tutar",
    "Senaryo Karsilastirma!C":"Senaryo toplamı", "Senaryo Karsilastirma!D":"Baza göre tutar farkı",
    "Senaryo Karsilastirma!E":"Baza göre oransal fark"}
SCENARIO_LABELS.update({"Finansal TCO!B":"Çok adımlı ödeme net bugünkü değeri",
    "Finansal TCO!C":"Geri kazanılan KDV net bugünkü değeri","Finansal TCO!D":"Seçili yaşam giderleri net bugünkü değeri",
    "Finansal TCO!E":"Kalıntı net bugünkü değeri","Finansal TCO!F":"Finansal toplam sahip olma maliyeti NBD",
    "Finansal Karsilastirma!B":"Kullanıcı finansal NBD bazı","Finansal Karsilastirma!C":"Finansal senaryo NBD toplamı",
    "Finansal Karsilastirma!D":"Finansal NBD farkı","Finansal Karsilastirma!E":"Finansal NBD oransal fark",
    "Finansal TCO!H":"Seçili yaşam giderleri nominal toplamı"})
SCENARIO_LABELS.update({'Tarihli Nakit Ozeti!G':'Bağımsız tarihli kullanıcı defteri: tam kapsam nominal net nakit',
 'Tarihli Nakit Ozeti!H':'Bağımsız tarihli kullanıcı defteri: tam kapsam NBD',
 'Tarihli Nakit Ozeti!I':'Tarihli defterin kullanıcı NBD bazına farkı',
 'Tarihli Nakit Ozeti!J':'Tarihli defterin oransal NBD farkı'})

def assumption_rows(scenario):
    from scenario_formulas import INPUTS,INPUT_LABELS
    shown=lambda value:"Bilinmiyor" if value is None else str(value)
    rows=[[title,shown(scenario.get('inputs',{}).get(key))] for key,title in zip(INPUTS,INPUT_LABELS)]
    financial=scenario.get('financial') or {};policy=financial.get('policy') or {}
    for key,title in (("base_currency","Hedef para"),("source_currency","Kaynak para"),("rate_date","Kur tarihi"),("rate_source","Kur dayanağı")):
        rows.append([title,shown(policy.get(key))])
    rows.append(["Kur yönü","1 kaynak para karşılığında hedef para" if policy.get('direction')=='TARGET_PER_SOURCE' else "Bilinmiyor"])
    rows.append(["KDV geri kazanım günü",shown(financial.get('vat_refund_days'))])
    rows.append(["Aynı kapsam/kur/dönem finansal NBD bazı",shown(financial.get('base_present_value'))])
    mode=financial.get('cost_mode','CONSTANT_ANNUAL')
    modes={'CONSTANT_ANNUAL':'Sabit yıllık enerji/bakım; diğer yaşam giderleri kapsam dışında',
           'YEARLY_SCHEDULE':'Her yıl enerji/bakım/diğer ayrı; hedef para, yıl sonu; kullanıcı varsayımı'}
    rows.append(['Yaşam gideri modeli',modes.get(mode,'Bilinmiyor; yaşam giderleri hesaplanamadı')])
    if mode=='YEARLY_SCHEDULE':
        rows.append(['Sabit enerji/bakım girdileri','Bu modelde kullanılmaz; aşağıdaki yıl bazlı giderler geçerlidir'])
        years=scenario.get('inputs',{}).get('years')
        by_year={item['year']:item for item in financial.get('annual_costs') or []}
        if isinstance(years,(int,float)) and not isinstance(years,bool) and years==int(years) and 1<=years<=100:
            for year in range(1,int(years)+1):
                item=by_year.get(year,{})
                rows.append(['Yıl '+str(year)+' giderleri','Enerji: '+shown(item.get('energy'))+'; bakım: '+shown(item.get('maintenance'))+'; diğer: '+shown(item.get('other'))])
        else:
            rows.append(['Yıllık yaşam giderleri','Analiz dönemi bilinmiyor; gider toplamı hesaplanamadı'])
    payments=financial.get('payments') or []
    for i,payment in enumerate(payments,start=1):
        value=payment.get('percent');percent="Bilinmiyor" if value is None else format(value*100,'.6g')+'%'
        rows.append(["Ödeme "+str(i),percent+"; analiz tarihinden gün: "+shown(payment.get('days'))])
    if not payments:rows.append(["Çok adımlı ödeme planı","Belirtilmemiş"])
    ledger=scenario.get('dated_costs')
    if ledger:
        from dated_cashflows import CATEGORY_LABELS,ledger_reference
        result=ledger_reference(ledger)
        rows.append(['Tarihli nakit defteri','Bağımsız kullanıcı kapsamı; diğer otomatik bedel/ödeme/yıllık gider toplamları eklenmez'])
        for key,title in (('valuation_date','NBD baz tarihi'),('base_currency','Hedef nakit para birimi'),('annual_rate','Hedef para yıllık efektif oran'),('baseline','Aynı kapsam kullanıcı NBD bazı')):
            rows.append([title,shown(ledger.get(key))])
        rows.append(['Kur/NBD yöntemi','Nakit tarihine açık kullanıcı kur projeksiyonu; hedef paraya çevrilmiş gelecekteki nakit, hedef para 365 gün efektif NBD. Gerçek kur tahmini veya onaylı şirket politikası değildir.'])
        rows.append(['Eksik maliyet türleri',', '.join(CATEGORY_LABELS[k] for k in result['missing_categories']) or 'Tür kapsamı beyan edilmiş; tutar/tarih/kur tamlığı ayrıca kontrol edilir'])
        for flow in ledger.get('flows') or []:
            rows.append([shown(flow.get('cost_id'))+' / '+CATEGORY_LABELS.get(flow.get('category'),'Tür bilinmiyor'),
                         'Tutar: '+shown(flow.get('amount'))+' '+shown(flow.get('currency'))+'; nakit tarihi: '+shown(flow.get('cash_date'))+'; kur tarihi: '+shown(flow.get('rate_date'))+'; hedef/kaynak kur: '+shown(flow.get('fx_rate'))+'; dayanak: '+shown(flow.get('rate_source'))])
    else:rows.append(['Tarihli nakit defteri','Belirtilmemiş; tarihli tam kapsam NBD hesaplanamadı'])
    return rows


def scenario_rows(reference):
    rows = []
    for key, title in SCENARIO_LABELS.items():
        value = reference.get(key)
        shown = "Hesaplanamadı" if value is None else format(value, ".6f").rstrip("0").rstrip(".")
        rows.append([title, shown])
    return rows
def label(value): return LABELS.get(str(value),str(value) if value is not None else "Bilinmiyor")

def render_pdf(model, path: Path):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, LongTable, TableStyle, KeepTogether
    fonts=[(Path("C:/Windows/Fonts/segoeui.ttf"),Path("C:/Windows/Fonts/segoeuib.ttf")),
           (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))]
    regular,bold=next(((a,b) for a,b in fonts if a.is_file() and b.is_file()),(None,None))
    if regular is None: raise RuntimeError("Türkçe PDF fontu bulunamadı")
    if "KilicReport" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("KilicReport",str(regular)))
        pdfmetrics.registerFont(TTFont("KilicReportBold",str(bold)))
        pdfmetrics.registerFontFamily("KilicReport",normal="KilicReport",bold="KilicReportBold")
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Kilic",fontName="KilicReport",fontSize=9,leading=13,alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="KilicTitle",fontName="KilicReportBold",fontSize=17,leading=22))
    styles.add(ParagraphStyle(name="KilicHeading",fontName="KilicReportBold",fontSize=12,leading=17,spaceBefore=10,spaceAfter=8,keepWithNext=True))
    story=[]
    def para(text,style="Kilic"): return Paragraph(escape(str(text) if text is not None else "Bilinmiyor").replace("\n","<br/>"),styles[style])
    def heading(text): story.append(para(text,"KilicHeading"))
    def table(headers,rows,widths=None):
        content=[[para(h) for h in headers]]+[[para(v) for v in row] for row in rows]
        if len(content)==1: content.append([para("Kayıt yok; veri uydurulmadı")]+[para("") for _ in headers[1:]])
        t=LongTable(content,colWidths=widths,repeatRows=1,hAlign="LEFT",splitInRow=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DFE8F0")),
                               ("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.3,colors.grey),
                               ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5)]))
        story.extend([t,Spacer(1,10)])
    story.append(para("Teklif Değerlendirme","KilicTitle"))
    heading("Karar ve rapor durumu")
    for text in [label(model.get("content_status")),label(model.get("decision_assurance")),
                 label(model.get("comparison_status")),"Profil: "+model.get("profile","standart"),
                 "Kesin satınalma önerisi: "+("Yok" if model.get("recommendation") is None else str(model["recommendation"])),
                 "Kaynak özeti: "+model.get("source_digest","Bütünlük doğrulanamadı")]:
        story.append(para(text))
    heading("Karar verilememe gerekçesi ve sınırlamalar")
    for text in model.get("limitations",[]) + model.get("integrity_findings",[]): story.append(para(text))
    if model.get("summary"): story.append(para(model["summary"]))
    story.append(para("Rapor teslimi; analitik doğrulama, satınalma veya harcama onayı anlamına gelmez."))
    story.append(PageBreak())
    heading("Kaynak envanteri")
    table(["Belge","Okunabilirlik","Kaynak hash"],[[d.get("relative_path"),label(d.get("parse_status")),d.get("sha256")]
                                                for d in model.get("documents",[])],[190,95,230])
    names={s["supplier_id"]:s["display_name"] for s in model.get("suppliers",[])}
    heading("Firma ve teklif evreni")
    table(["Firma","Teklif","Durum"],[[names.get(o["supplier_id"],o["supplier_id"]),o["offer_id"],label(o.get("status"))]
                                      for o in model.get("offers",[])],[180,220,115])
    from pdf_bound_values import header, fields, display_amount
    heading("Teklif bazında kritik bedeller")
    for offer in model.get("offers", []):
        if offer.get("status") != "active":
            continue
        heading(header(names.get(offer["supplier_id"], offer["supplier_id"]), offer["offer_id"]))
        amounts = fields(model, offer["offer_id"])
        for title, amount, currency in amounts:
            story.append(para(title + ": " + display_amount(amount) + " " + (currency or "Para birimi belirtilmedi") + ";"))
        if not amounts:
            story.append(para("Kaynaklı kritik bedel henüz doğrulanmadı; hesap ve karşılaştırma bekliyor."))
    heading("Maliyet ve hesaplanamayan alanlar")
    table(["Firma", "Teklif", "Kaynak toplam", "Para"],
          [[names.get(f.get("supplier_id"),f.get("supplier_id")),f.get("offer_id"),f.get("value_number"),f.get("currency")]
           for f in model.get("facts",[]) if f.get("field_key")=="total" and f.get("value_number") is not None],
          [150,165,110,90])
    costs=[]
    for c in model.get("calculations",[]):
        if c.get("calculation_type")!="cost_summary": continue
        result=c.get("result") or json.loads(c.get("result_json") or "{}")
        offer=next((o for o in model.get("offers",[]) if o["offer_id"]==c.get("offer_id")),{})
        costs.append([names.get(offer.get("supplier_id"),c.get("offer_id")),
                      c.get("offer_id"),str(result.get("stated_total") if result.get("stated_total") is not None else "Bilinmiyor"),
                      str(result.get("comparable_total") if result.get("comparable_total") is not None else "Hesaplanamadı"),
                      result.get("currency") or result.get("base_currency") or "Bilinmiyor"])
    table(["Firma","Teklif","Kaynak bedeli","Karşılaştırılabilir","Para"],costs,[115,100,100,110,90])
    if not costs: story.append(para("Doğrulanmış maliyet hesabı yok. Fiyat, miktar, kur, ödeme ve kapsam girdileri gereken alanlarda teyit edilmelidir; bilinmeyen bedel sıfır değildir."))
    from display_values import label as business_label, structured
    heading("Kaynak ticari koşullar")
    terms = []
    for fact in model.get("facts", []):
        if fact.get("field_key") not in {"currency", "payment", "delivery", "validity", "warranty", "quote_date"}:
            continue
        value = next((fact.get(key) for key in ("value_text", "value_date", "value_number") if fact.get(key) is not None), None)
        terms.append([names.get(fact.get("supplier_id"), fact.get("supplier_id")), fact.get("offer_id"),
                      business_label(fact.get("field_key")), value, business_label(fact.get("evidence_status"))])
    table(["Firma", "Teklif", "Koşul", "Kaynak gözlemi", "Kanıt durumu"], terms, [115,100,85,125,90])
    buyer_rows = []
    for row in model.get('buyer_declarations',[]):
        buyer_rows.append([row['offer_id'],business_label(row['kind']),str(row['value'])+' '+str(row.get('unit') or '')+
                           ' | '+str(row.get('target') or '')+' | '+str(row.get('answer_text') or '')+
                           ' | Kullanıcı beyanı; karar/hesap teyidi ayrı. Soru: '+row['issue_id']])
    for calc in model.get("calculations", []):
        if calc.get("calculation_type") != "cost_summary":
            continue
        value = calc.get("result") or json.loads(calc.get("result_json") or "{}")
        for kind, declarations in (value.get("buyer_inputs") or {}).items():
            buyer_rows.append([calc.get("offer_id"), business_label(kind), structured(declarations)])
    heading("Uygulanan kullanıcı beyanları")
    table(["Teklif", "Alan", "Kullanıcı beyanı ve hesap dayanağı"], buyer_rows, [100,115,300])
    if model.get('buyer_quantity_totals'):
        heading('Kullanıcı miktar esası — tam maliyet ve sıralama değildir')
        table(['Teklif','Kaynak bedeli / miktar esası / para','Sınır'],
              [[r['offer_id'],r['source_total']+' / '+r['quantity_adjusted_total']+' '+r['currency'],r['limitation']]
               for r in model['buyer_quantity_totals']],[100,180,235])
    heading("Şartname uygunsuzluk ve teyit matrisi")
    matrix=model.get("matrix",[])
    for r in matrix:
        group_start = len(story)
        table(["Firma / teklif / madde","Durum / önem / etki","Beklenen / gerekçe"],
              [[r["supplier"]+" / "+r["offer_id"]+" / "+r["requirement_id"],
                label(r["status"])+" / "+label(r["severity"])+" / "+label(r["decision_effect"]),
                r["expected"]+"\n"+r["reason"]]],[175,150,190])
        for key in ["spec_evidence","offer_evidence"]:
            ev=r.get(key)
            if ev: story.append(para("Kanıt: "+ev["evidence_id"]+" | "+json.dumps(ev["locator"],ensure_ascii=False)+" | "+str(ev["quote"])))
        story[group_start:] = [KeepTogether(story[group_start:])]
    if not matrix: story.append(para("Şartname hükmü yok veya güvenilir okunamadı; teknik uygunluk doğrulanmadı."))
    heading("Bilgi talepleri ve sonraki aksiyonlar")
    table(["Önem","Soru","Durum"],[[label(i.get("severity")),i.get("question"),label(i.get("status"))]
                                   for i in model.get("open_issues",[])],[70,370,75])
    if not model.get("open_issues"): story.append(para("Kaynak kapsamını ve gerekli fiyat/ödeme/şartname girdilerini tamamlayıp yeni rapor revizyonu oluşturun."))
    heading("Senaryo kapsamı")
    story.append(para("Excelde miktar, kur, vergi/ithalat, ödeme NBD, nominal ve finansal TCO, puan/duyarlılık ve baz farkı formülleri bulunur. Sabit kur modeli en çok 12 ödeme, 365 gün efektif oran, sabit veya yıl bazlı gider ve dönem sonu kalıntı kullanır. Bağımsız tarihli nakit defteri en çok 48 tekil maliyet kaydını ayrı para/tarih/kur dayanağıyla hesaplar; otomatik sayfa toplamları bu deftere eklenmez. Satınalma, navlun, sigorta, gümrük, KDV ödeme/geri kazanımı, enerji, bakım, sarf, yenileme, diğer ve kalıntı türleri açık beyan edilmeden tam defter toplamı verilmez; kapsam dışı veya sıfır tutar kullanıcı tarafından açıkça girilir. Kur yönü, tarih ve dayanak gereklidir. Kullanıcı varsayımları kaynak gerçeklerinden ayrıdır; senaryo puanı veya NBD resmî teklif sıralaması ve onaylı kurumsal politika değildir."))
    for sid,reference in model.get("scenario_reference",{}).items():
        assumptions=model.get('scenario_assumptions',{}).get(sid)
        if assumptions:
            heading("Senaryo " + str(assumptions['id']) + " — kullanıcı varsayımları")
            table(["Varsayım", "Kullanıcı girdisi"],assumption_rows(assumptions),[280,235])
        heading("Senaryo satırı " + sid + " — bağımsız Python referans hesabı")
        table(["Hesap", "Varsayımlara bağlı sonuç"], scenario_rows(reference), [350,165])
    story.append(para("Excel formül yeniden hesaplama durumu: "+label(model.get("recalculation","PENDING_NATIVE_RECALC"))))
    def footer(canvas,doc):
        canvas.setFont("KilicReport",8)
        canvas.drawString(40,25,"Teklif değerlendirme — "+label(model.get("content_status")))
        canvas.drawRightString(A4[0]-40,25,"Sayfa "+str(doc.page))
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=40,leftMargin=40,
                      topMargin=35,bottomMargin=40,title="Teklif Değerlendirme",
                      author="Kılıç Satınalma Departmanı").build(story,onFirstPage=footer,onLaterPages=footer)
    import fitz
    with fitz.open(path) as doc:
        if len(doc)<2 or any(not p.get_text().strip() for p in doc):
            raise ValueError("PDF en az iki anlamlı sayfa içermeli")
        pages=len(doc)
    return {"available":True,"path":str(path),"renderer":"reportlab","pages":pages}
