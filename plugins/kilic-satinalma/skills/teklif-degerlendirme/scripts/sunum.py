"""Turkish display labels; source data and evidence identifiers stay unchanged."""
import re

LABELS = {'total':'Teklif toplamı','currency':'Para birimi','vat':'KDV',
 'quantity':'Miktar / tank sayısı','quote_date':'Teklif tarihi','validity':'Geçerlilik',
 'payment':'Ödeme','payment_terms':'Ödeme koşulları','delivery':'Teslim',
 'delivery_time':'Teslim süresi','warranty':'Garanti','incoterms':'Teslim şekli',
 'total_tanks':'Toplam tank','3500_ton':'3.500 tonluk tank','800_ton':'800 tonluk tank',
 '300_ton':'300 tonluk tank','quantity':'Miktar','unit_price':'Birim fiyat',
 'price_unit':'Fiyat birimi','vat_rate':'KDV oranı','cost':'Maliyet','quality':'Kalite',
 'advance-payment':'Avans ve ödeme','cancellation':'İptal',
 'delivery-payment':'Teslim ve ödeme','delivery-price':'Teslim ve fiyat',
 'document-precedence':'Belgelerin öncelik sırası','late-interest':'Gecikme faizi',
 'liability':'Sorumluluk','payment-risk-transfer':'Ödeme ve riskin devri',
 'price-update':'Fiyat güncellemesi','teminat-liability-termination':'Teminat, sorumluluk ve fesih',
 'termination-delay':'Fesih ve gecikme','time-extension':'Süre uzatımı',
 'warranty-delivery':'Garanti ve teslim','warranty-liability-termination':'Garanti, sorumluluk ve fesih'}
STATES = {'verified':'Doğrulandı','missing':'Belirtilmemiş','conflicting':'Çelişkili',
 'compliant':'Uygun','noncompliant':'Uygun değil','partial':'Kısmen uygun',
 'excluded':'Hariç','included':'Dahil','unknown':'Belirtilmemiş','unverified':'Doğrulanmadı',
 'not_applicable':'Uygulanmıyor','pending':'Yanıt bekleniyor'}

def text_value(value):
    if value is None: return 'Belirtilmemiş'
    if isinstance(value, bool): return 'Evet' if value else 'Hayır'
    if isinstance(value, (int,float)): return value
    if isinstance(value, dict):
        return '\n'.join(f'{LABELS.get(str(k),str(k).replace("_"," "))}: {text_value(v)}' for k,v in value.items())
    if isinstance(value, list): return '\n'.join(str(text_value(v)) for v in value)
    return STATES.get(str(value), str(value))

class Presentation:
    def __init__(self, data, display_names=None):
        display_names=display_names or {}
        unknown=set(display_names)-{o['id'] for o in data['offers']}
        if unknown: raise ValueError('Görünen firma adında bilinmeyen teklif kimliği.')
        self.names = {k:display_names.get(o['id'],o.get('display_name',o['name'])) for o in data['offers'] for k in (o['id'],o.get('supplier_id',o['id']),o['name'])}
        self.ids = {o['id']:self.names[o['id']] for o in data['offers']}
        # Expand an unambiguous commercial short name used in authored prose.
        candidates={}
        for o in data['offers']:
            for name in (o['name'],self.ids[o['id']]):
                token=name.split()[0]
                if len(token)>=4: candidates.setdefault(token,set()).add(self.ids[o['id']])
        self.aliases={k:next(iter(v)) for k,v in candidates.items() if len(v)==1}
        self.requirements = {r['id']:r for r in data.get('requirements',[])}
        self.rfi = {r['id']:f'BT-{i:03}' for i,r in enumerate(data.get('rfi',[]),1)}
    def name(self, key): return self.names.get(key, key or 'ORTAK')
    def fact(self, fid):
        parts=str(fid).split('/')
        owner=self.name(parts.pop(0)) if parts[0] in self.names else 'İDARE'
        category=parts.pop(0) if parts else ''
        key='/'.join(parts)
        if category=='requirement': label='Madde '+key.replace('_',' ')
        else: label=LABELS.get(key,key.replace('_',' ').replace('-',' '))
        return owner,label or category
    def ref(self, fid): return ' — '.join(self.fact(fid))
    def text(self, value):
        if not isinstance(value,str): return value
        result=self.names.get(value,value)
        names={**self.aliases,**{k:v for k,v in self.names.items() if len(k)>3}}
        names.update({v:v for v in self.ids.values()})
        if names:
            pattern=r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(names,key=len,reverse=True))+r')(?!\w)'
            result=re.sub(pattern,lambda m:names[m[0]],result)
        result=LABELS.get(result,result)
        if all(k in self.ids for k in ('A','F','G')):
            result=result.replace('A/F/G',' / '.join(self.ids[k] for k in ('A','F','G')))
        for old,new in sorted(self.rfi.items(),key=lambda p:-len(p[0])): result=result.replace(old,new)
        # Structured identifiers and explicit one-letter supplier references in
        # authored explanations; never expand letters within standards or words.
        result=re.sub(r'(?<![\w/])(?:'+ '|'.join(re.escape(k) for k in self.ids) +r')/(?:field|requirement|scope|contracts|technical)/[\w.\-]+',lambda m:self.ref(m[0]),result)
        for key,name in self.ids.items():
            result=result.replace(key+'/quote_date',name+' — teklif tarihi').replace(key+'/validity',name+' — geçerlilik')
            result=re.sub(r'(?<!\w)'+re.escape(key)+r':',name+':',result)
            if len(key)==1:
                result=re.sub(r'(?<![\w-])'+re.escape(key)+r"(?=(?:['’](?:da|de|nın|nin)|[,/] |/|\s+(?:faturayı|ödeme|sırasıyla|ve\b|ile\b|için\b|ayrıca\b|açık\b|dolaylı\b|geçerlilik\b|kapsam\b|fiyat\b|USD\b|tutarı\b|sorumluluk\b|['’])))",name,result)
        terms={'None':'Belirtilmemiş','verified':'Doğrulandı','missing':'Belirtilmemiş',
               'conflicting':'Çelişkili','noncompliant':'Uygun değil','compliant':'Uygun',
               'excluded':'Hariç','included':'Dahil','unknown':'Belirtilmemiş',
               'utilities':'yardımcı tesisler','Incoterms':'Uluslararası teslim kuralları',
               'RFI':'Bilgi talebi','TCO':'Toplam sahip olma maliyeti','QA':'Kontrol',
               'NDT':'Tahribatsız muayene','DFT':'Kuru film kalınlığı','ITP':'Muayene ve test planı',
               'Shell':'Gövde','Roof':'Çatı','Bottom':'Taban','Nozzle':'Nozul',
               'data sheet\'in':'teknik bilgi föyünün','data sheet':'teknik bilgi föyü',
               'Joint Effiency':'Kaynak birleşim verimi','Joint Efficiency':'Kaynak birleşim verimi',
               'hold pointleri':'zorunlu bekleme noktaları','hold noktalarını':'zorunlu bekleme noktalarını'}
        for old,new in terms.items(): result=re.sub(r'\b'+re.escape(old)+r'\b',new,result,flags=re.IGNORECASE)
        for name in set(self.ids.values()):
            letters=name.lower(); vowels=[v for v in letters if v in 'aeıioöuü']
            if not vowels: continue
            v=vowels[-1]; back=v in 'aıou'; last=letters[-1]
            loc=('t' if last in 'fstkçşhp' else 'd')+('a' if back else 'e')
            gen=('n' if last in 'aeıioöuü' else '')+({'a':'ı','ı':'ı','e':'i','i':'i','o':'u','u':'u','ö':'ü','ü':'ü'}[v])+'n'
            result=re.sub(re.escape(name)+r"['’](?:da|de|ta|te)\b",name+'’'+loc,result)
            result=re.sub(re.escape(name)+r"['’](?:nın|nin|nun|nün|ın|in|un|ün)\b",name+'’'+gen,result)
        result=re.sub(r'(\d+)(?:st|nd|rd|th) Edition',r'\1. baskı',result,flags=re.IGNORECASE)
        result=re.sub(r'(?<!\w)requirement/([\w.\-]+)',lambda m:'Şartname — Madde '+m[1],result)
        return result
