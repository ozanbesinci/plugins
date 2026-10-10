"""Human presentation only. Canonical IDs, values and source quotes stay unchanged."""
import json,re
from decimal import Decimal,ROUND_HALF_UP
LABELS={
'SUFFICIENT':'Karar için yeterli','PRELIMINARY_ONLY':'Ön değerlendirme','UNKNOWN':'Bilinmiyor','hizli':'Hızlı','standart':'Standart','yuksek_guvence':'Yüksek güvence',
'verified':'Doğrulandı','missing':'Eksik','excluded':'Hariç','unreadable':'Okunamadı','conflicting':'Çelişkili','assumption':'Varsayım','requires_confirmation':'Teyit bekleniyor',
'pass':'Geçti','PASS':'Geçti','fail':'Başarısız','FAIL':'Başarısız','open':'Açık','resolved':'Çözüldü','pending':'Bekliyor','complete':'Tamamlandı','incomplete':'Eksik','active':'Aktif','ready':'Hazır','read':'Okundu','partial':'Kısmen okundu','not_applicable':'Uygulanmaz','not_stated':'Belirtilmedi','unverified':'Doğrulanmadı','passed':'Geçti','failed':'Başarısız','critical':'Kritik','high':'Yüksek','medium':'Orta','low':'Düşük',
'offer':'Teklif','specification':'Şartname','boq':'Miktar listesi','correspondence':'Yazışma','support':'Destek belgesi','unrelated':'İlgisiz',
'currency':'Para birimi','total':'Toplam','quantity':'Miktar','quote_date':'Teklif tarihi','validity':'Geçerlilik','delivery':'Teslim','payment':'Ödeme','incoterms':'Teslim şekli','warranty':'Garanti','vat':'KDV','scope_signature':'Kapsam tanımı','included':'Dahil',
'payment_basis':'Ödeme esası','scope_basis':'Kapsam esası','scope_identity':'Kapsam kimliği','incoterm':'Teslim şekli','vat_basis':'KDV esası','none':'Yok','verified_for_all_offers':'Bütün teklifler doğrulandı',
'deterministic':'Kurallarla çıkarım','semantic_llm':'Dil modeli çıkarımı','vision':'Görsel okuma','adjudicated':'Uyuşmazlık kararı','duckdb_pdf_secondary':'DuckDB ile ikinci PDF okuması','python_primary':'Birincil Python okuması',
'observation':'Gözlem','calculated':'Hesap','hypothesis':'Hipotez','recommendation':'Öneri','supported':'Desteklendi','unsupported':'Desteklenmedi','conditional':'Koşullu',
'cost_summary':'Maliyet özeti','scoring':'Puanlama','independent_decimal_float_pv_v1':'Bağımsız bugünkü değer hesabı','supplier_commitment':'Firma taahhüdü','supplier_offer':'Firma teklifi','controlling':'Esas kaynak','unresolved':'Çözülmedi','corroborating':'Teyit kaynağı','non_controlling':'Yardımcı kaynak',
'analysis_dimension':'Analiz boyutu','critical_fact':'Kritik veri','artifact':'Çıktı','supplier':'Firma','requirement':'Şartname maddesi','Comparison basis':'Karşılaştırma esası','Independent arithmetic':'Bağımsız hesap','Cost bridge':'Maliyet köprüsü','Claim support':'İddia desteği','Final artifact QA':'Nihai çıktı kontrolü',
'Fact ID':'Veri kimliği','Fact IDs':'Veri kimlikleri','Claim ID':'İddia kimliği','Calculation IDs':'Hesap kimlikleri','Requirement IDs':'Madde kimlikleri','Assertions':'Doğrulama ifadeleri','Caveat':'Çekince','Locator':'Kaynak konumu','Snapshot SHA':'İncelenen sürüm özeti','Reviewed Snapshot SHA256':'İncelenen sürüm özeti','Residual':'Fark','Sonuc JSON':'Hesap ayrıntısı','Event ID':'Olay kimliği','Acik RFI':'Açık bilgi talebi','RFI':'Bilgi talepleri',
'known':'Bilinen','complete':'Tamamlandı','stated_total':'Beyan toplamı','known_scope_adjustment':'Bilinen kapsam düzeltmesi','acquisition_cost_basis':'Alım maliyeti esası','acquisition_present_value':'Alım bugünkü değeri','tco_present_value':'Toplam sahip olma bugünkü değeri','comparable_total':'Karşılaştırılabilir toplam','unknown_scope_items':'Belirsiz kapsam kalemleri','base_currency':'Ortak para birimi','base_date':'Esas tarih','base_amount':'Ortak para birimindeki tutar','fx_used':'Kur bilgisi','rate':'Oran','unit':'Birim','source':'Kaynak','date':'Tarih','same_currency':'Aynı para birimi','payment_present_value_detail':'Ödeme bugünkü değer ayrıntısı','days':'Gün','amount':'Tutar','ratio':'Pay','present_value':'Bugünkü değer','warnings':'Uyarılar','steps':'Adımlar','stage':'Aşama','scope_5A_known':'Bilinen ek kapsam','unknown_items':'Belirsiz kalemler',
'status':'Durum','mismatches':'Uyumsuzluklar','ranking_allowed':'Sıralama yapılabilir','failed_dimensions':'Başarısız boyutlar','offer_id':'Teklif kimliği','fact_id':'Veri kimliği','field_key':'Alan','value_number':'Sayısal değer','value_text':'Metin değeri','value_date':'Tarih değeri','evidence_status':'Kanıt durumu','source_type':'Kaynak türü','source_id':'Kaynak kimliği','path':'Değer yolu','operator':'Karşılaştırma','equals':'Eşit','approx':'Yaklaşık eşit','contains':'İçerir','exists':'Mevcut','tolerance':'Tolerans','calculation':'Hesap','fact':'Veri','missing':'Eksik','fields':'Alanlar','price_scores':'Fiyat puanları','weighted_scores':'Ağırlıklı puanlar','price_score_0_10':'Fiyat puanı (0–10)','total_score_0_10':'Toplam puan (0–10)','cost_metric':'Maliyet ölçüsü','cost_ranking':'Maliyet sıralaması','cost_only':'Yalnız maliyet','method':'Yöntem','10_x_min_cost_over_offer_cost':'En düşük maliyetin teklif maliyetine oranı × 10','note':'Not',
'sheet':'Sayfa','cell':'Hücre','range':'Aralık','page':'Sayfa','region':'Bölge','paragraph':'Paragraf','table':'Tablo','row':'Satır','column':'Sütun','section':'Bölüm','block':'Blok','index':'Sıra','font':'Yazı tipi','size':'Boyut',
'critical_field':'Kritik alan','supplier_identity':'Firma kimliği','comparability_contract':'Karşılaştırma esası','critical_source_field_unverified':'Kritik kaynak alanı doğrulanmadı','source_authority':'Kaynak yetkisi','format':'Biçim','calculation_type':'Hesap türü','expected':'Beklenen','observed':'Gözlenen'
}
LABELS.update({'currency_basis': 'Para birimi esası', 'incoterm_basis': 'Teslim şekli esası', 'source_authority_conflict': 'Kaynak önceliği uyuşmazlığı', 'single_currency': 'Tek para birimi', 'same_or_not_stated': 'Aynı veya belirtilmemiş', 'same_payment_terms': 'Aynı ödeme koşulları', 'same quantity and explicit unit': 'Aynı miktar ve açık birim', 'relative_tolerance': 'Göreli tolerans', 'explicit_common_unit_required': 'Açık ortak birim gerekli', 'values': 'Değerler', 'units': 'Birimler', 'missing_units': 'Eksik birimler', 'relative_gap': 'Göreli fark', 'incomplete_offers': 'Eksik teklifler', '5A known-scope normalization': 'Bilinen kapsamın eşitlenmesi', 'complete_known_scope': 'Bilinen kapsam tamam', 'explicit scope identity': 'Açık kapsam tanımı', 'same_explicit_product_or_scope': 'Aynı açık ürün veya kapsam', 'same_or_not_stated_vat_basis': 'Aynı veya belirtilmemiş KDV esası', 'component': 'Bileşen', 'delta': 'Düzeltme tutarı', 'payment_npv': 'Ödemenin bugünkü değer farkı', 'independent_scoring_v2': 'Bağımsız puan kontrolü', 'document': 'Belge', 'source_inventory': 'Kaynak envanteri', 'accounted': 'Kaydı mevcut', 'role': 'Rol', 'parse_status': 'Okuma durumu', 'critical_fields': 'Kritik alanlar', 'bad': 'Sorunlu alanlar', 'sha256': 'SHA-256 özeti', 'size_bytes': 'Boyut (bayt)', 'present': 'Mevcut', 'document_id': 'Belge kimliği', 'comparability': 'Karşılaştırılabilirlik', 'partial_source_parse': 'Kısmi kaynak okuma', 'superseded': 'Yerine yeni kaynak geçmiş', 'TCO NBD': 'Toplam Sahip Olma NBD', 'Teklif Kanıt Durumu': 'Teklif Kanıt Durumu', 'Format': 'Biçim', 'Source was only partially parsed.': 'Kaynak kısmen okunabildi.', 'Use the targeted visual/semantic fallback for unresolved regions.': 'Çözülemeyen bölgeleri dar görsel veya metin incelemesiyle teyit edin.', 'Another offer is explicitly marked current.': 'Başka bir teklif açıkça güncel olarak işaretlendi.', 'Explicitly marked current supplier offer.': 'Firma teklifi açıkça güncel olarak işaretlendi.', 'Source is unreadable.': 'Kaynak okunamıyor.', 'supplemental': 'Tamamlayıcı kaynak', 'candidate': 'Aday kaynak', 'needs_input': 'Bilgi bekleniyor', 'needs_classification': 'Sınıflandırma bekleniyor', 'unusable': 'Kullanılamıyor', 'Multiple supplier offers/revisions; precedence is not explicit and is not inferred from filename/date.': 'Birden fazla firma teklifi veya revizyonu var; kaynak önceliği açık değil, dosya adı veya tarihten çıkarılmaz.', 'Only readable active specification source.': 'Okunabilir tek aktif şartname kaynağı.', 'Explicitly marked current specification.': 'Şartname açıkça güncel olarak işaretlendi.', 'Another specification is explicitly marked current.': 'Başka bir şartname açıkça güncel olarak işaretlendi.', 'Multiple active specifications; controlling revision is not explicit.': 'Birden fazla aktif şartname var; esas revizyon açık değil.', 'Supplemental evidence; does not silently override formal specification/offer.': 'Tamamlayıcı kanıt; resmî şartname veya teklifin önüne otomatik geçmez.', 'Scope/quantity source candidate.': 'Kapsam veya miktar için aday kaynak.', 'Document classified unrelated.': 'Belge ilgisiz olarak sınıflandırıldı.'})
LABELS['Image content requires vision/OCR for semantic extraction.']='Görsel içeriği okumak için görsel inceleme veya karakter tanıma gerekir.'
LABELS['Cost score is not a total decision score.']='Maliyet puanı toplam karar puanı değildir.'
LABELS.update({'buyer_declaration':'Alıcı beyanı','supplier_fact':'Firma kaynak verisi',
               'reference_quantity':'Esas alınan miktar','scope_cost':'Kapsam maliyeti',
               'payment_terms':'Ödeme koşulları','warranty_terms':'Garanti koşulları',
               'work_start':'İşe başlama','work_delivery':'İş teslimi',
               'buyer_quantity_adjustment':'Alıcı miktar düzeltmesi'})
# These are code-controlled columns; free source quotes and user/model prose are not translated.
CONTROLLED={
'Ozet':{1,2},'Envanter':{2,3,7,8,9},'Teklif Karsilastirma':{21},'Alici Beyanlari':{2},'Ticari Kosullar':{3,4,5},'Kapsam ve Riskler':{2,4},'Bilgi Talepleri':{2,3,5},'Kanitlar':{3,4,8},'Karsilastirma Sozlesmesi':{2,4,6,7},'Maliyet Koprusu':{8},'Bagimsiz Hesap Kontrolu':{2,3,4},'Iddia Kaydi':{2,4},'Kapsam Izleme':{1,2,3,4},'Hesap Detayi':{3},'Uzman Teyidi':{2,3,5},'Kaynak Otoritesi':{2,3,4},'Veri Kalitesi':{2,3,5,6,7,8,9},'Degisim Kaydi':{2,3}}
JSON_COLS={'Kanitlar':{6},'Karsilastirma Sozlesmesi':{7,8},'Maliyet Koprusu':{9},'Bagimsiz Hesap Kontrolu':{6},'Iddia Kaydi':{8},'Kapsam Izleme':{6,7},'Degisim Kaydi':{4}}
def label(value):
    if not isinstance(value,str):return value
    if value in LABELS:return LABELS[value]
    if value.startswith('Offer off_'):return 'Teklif '+value[6:]
    if value.startswith('cost_ranking.'):return 'Maliyet sıralaması.'+value.split('.',1)[1]
    return value

MAX_SHOWN_DECIMALS=6
NUMBER_TEXT=re.compile(r'-?\d+\.\d+')

def readable_number(obj):
    """Shorten arithmetic-precision artefacts for display (e.g. 28-digit Decimal strings).

    Only numbers with more than MAX_SHOWN_DECIMALS fraction digits change; they are
    shown rounded with an explicit '≈'. The canonical value stays in the reviewed snapshot.
    """
    if isinstance(obj,bool) or not isinstance(obj,(str,float)):return None
    text=str(obj).strip()
    if not NUMBER_TEXT.fullmatch(text) or len(text.split('.',1)[1])<=MAX_SHOWN_DECIMALS:return None
    number=Decimal(text)
    shown=number.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP) if abs(number)>=1 else number.quantize(Decimal('0.000001'),rounding=ROUND_HALF_UP).normalize()
    return '≈\u00a0'+format(shown,'f')  # no-break space keeps the marker with the value

def structured(value):
    def walk(obj):
        if isinstance(obj,dict):return '\n'.join(f'{label(k)}: {walk(v)}' for k,v in obj.items()) or 'Yok'
        # Records (dicts) are separated by a blank line so print keeps each record together.
        if isinstance(obj,list):return ('\n\n' if any(isinstance(v,dict) for v in obj) else '; ').join(walk(v) for v in obj) or 'Yok'
        if obj is None:return 'Belirtilmedi'
        if isinstance(obj,bool):return 'Evet' if obj else 'Hayır'
        shown=readable_number(obj)
        if shown:return shown
        if isinstance(obj,str):
            try:
                nested=json.loads(obj)
                if isinstance(nested,(dict,list)):return walk(nested)
            except (ValueError,TypeError):pass
        return str(label(obj))
    try:return walk(json.loads(value)) if isinstance(value,str) else walk(value)
    except (ValueError,TypeError):return label(value)

def display_cell(sheet,col,value,header=False):
    if header:return label(value)
    if sheet=='Teklif Karsilastirma' and col==19 and isinstance(value,str):
        return ', '.join(label(v.strip()) for v in value.split(','))
    if col in JSON_COLS.get(sheet,set()):return structured(value)
    if col in CONTROLLED.get(sheet,set()):return label(value)
    return value

def question(text):
    m=re.fullmatch(r'Confirm supplier identity for offer document (.+)\.',str(text or ''))
    if m:return f'{m[1]} teklif belgesindeki firma kimliğini teyit edin.'
    m=re.fullmatch(r'Confirm the (\w+) field for offer (.+)\.',str(text or ''))
    if m:return f'{m[2]} teklifinin {label(m[1])} alanını teyit edin.'
    m=re.fullmatch(r'Resolve comparison basis for (\w+) before (?:supplier ranking|ranking or final supplier recommendation)\.',str(text or ''))
    if m:return f'Firma sıralamasından önce {label(m[1])} karşılaştırma esasını çözün.'
    m=re.fullmatch(r'Confirm the controlling offer/revision for supplier (.+); multiple active offer sources exist.',str(text or ''))
    if m:return f'{m[1]} firmasının esas teklif veya revizyonunu teyit edin; birden fazla aktif teklif kaynağı var.'
    return text

def authority_reason(text):
    return {'Only readable active formal offer for this supplier.':'Bu firmanın okunabilir tek aktif resmî teklifi.', 'Latest readable formal offer controls supplier commitments.':'Firmanın taahhütlerinde okunabilir en güncel resmî teklif esas alınır.', 'No readable formal offer; authority unresolved.':'Okunabilir resmî teklif yok; kaynak yetkisi çözülmedi.'}.get(text,label(text))

def present_workbook(wb):
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            # An explicit empty-table row stays empty; do not fill its other cells with "Belirtilmedi".
            if row[0].row>1 and row[0].value=='Kayıt bulunmuyor.' and all(c.value is None for c in row[1:]):continue
            for c in row:
                c.value=display_cell(ws.title,c.column,c.value,c.row==1)
                if ws.title in {'Bilgi Talepleri','Uzman Teyidi'} and c.row>1 and c.column==4:c.value=question(c.value)
                if ws.title=='Kaynak Otoritesi' and c.row>1 and c.column==6:c.value=authority_reason(c.value)

