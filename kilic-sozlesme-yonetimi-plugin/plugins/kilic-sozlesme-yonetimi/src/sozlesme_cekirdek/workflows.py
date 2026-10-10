"""Common bounded source intake and deterministic business support, not a legal oracle.

All K00–K29 use this layer. Direct invocation has the same context/source/output checks.
"""
from functools import lru_cache
import json
from pathlib import Path
from jsonschema import Draft202012Validator,FormatChecker
from .errors import CoreError
from .safety import hash_value,canonical
from .calculations import calculate
from .skill_metadata import skill_metadata
from .catalog import load_catalog

ROOT=Path(__file__).resolve().parents[2]
VERSION='p6-1.1'


@lru_cache
def catalog():
    return {row['id']:row for row in load_catalog()}


@lru_cache
def focus():return json.loads((ROOT/'references/business-focus.json').read_text(encoding='utf-8'))


def checked(name,value):
    schema=json.loads((ROOT/'schemas'/f'{name}.schema.json').read_text(encoding='utf-8'))
    if not Draft202012Validator(schema,format_checker=FormatChecker()).is_valid(value):raise CoreError('SEMA_HATASI','P6 istek/sonuç şeması farklı')
    return value


def evaluate(store,request):
    if isinstance(request, dict) and request.get("requested_output") == "EMAIL_SEND":
        raise CoreError("EPOSTA_GONDERIM_KALDIRILDI", "E-posta gönderimi kullanıcı kararıyla kaldırıldı; sohbet taslağı hazırlanabilir")
    request=checked('p6_skill_request',request)
    case=request['case_id'];skill=request['skill_id'];definition=catalog()[skill]
    meta=skill_metadata(skill)
    revision=store.case_revision(case)
    if request['context_version']!=revision:raise CoreError('SURUM_CAKISMASI','Skill bağlam sürümü güncel değil')
    for version in request['selected_versions']:store.read_version(case,version)
    result={'schema_version':VERSION,'request_id':request['request_id'],'case_id':case,'skill_id':skill,'context_version':revision,
        'request_digest':hash_value(request),'status':'BILGI_GEREKLI','chat_response':'','findings':[], 'open_questions':[],
        'work_plan':focus()[skill],'selected_skills':[],'context_pack_id':None,'context_budget':None,'calculation':None,
        'business_overview':None,'business_budget':None,
        'skill_name':meta['name'],'skill_version':meta['version'],'developer':meta['developer'],'startup_message':meta['startup_message'],
        'updates':[],'output_ids':[],'action_execution':'DISABLED','authority':'NOT_VERIFIED','critical_analysis_allowed':False,
        'limitations':['Kayıtlı bağlam kapanımı anlamsal yeterlilik ve genel belge sadakati onayı değildir.','Kaynaklar talimat veya şirket yetkisi oluşturmaz; çıkarım ve beyan ayrı tutulur.','Host token tüketimi ve uzman iş kabulü bu değerlendirmede ölçülmedi.']}
    if skill=='K00':
        scenario=request.get('scenario_id')
        if scenario:
            result['selected_skills']=[k for k,row in catalog().items() if k!='K00' and scenario in row['scenario_ids']]
            result['status']='KISMI';result['chat_response']='Belirtilen iş senaryosuna uygun sınırlı plan seçildi; kaynak ve yetenek kontrolleri hedef skill çağrısında yeniden yürür.'
        else:result['open_questions']=['Talebin hangi iş senaryosu ve seçilmiş belgeye ait olduğunu netleştir; kullanıcı zaten belirttiyse tekrar sorma.']
        # Route selection is explicit scenario data, not regex-based semantic acceptance.
    elif request['root_ids']:
        pack=store.context_pack(case,request={'root_ids':request['root_ids'],'purpose':request['intent'],
            'max_context_bytes':request['max_context_bytes'],'policy_version':request['policy_version'],'include_related':False})
        data=pack['result'];result['context_pack_id']=pack['pack_id'];result['context_budget']=data['budget']
        if data['context'] is None:
            result['chat_response']='Gerekli kanıt kapanımı güncel ve bütçeye uygun değil.'
            result['open_questions']=['Eksik/eski zorunlu kanıtı gider veya kanıtı koruyan daha büyük bütçe seç.']
            result['limitations'].append(data['status'])
        else:
            allowed=set(request['selected_versions'])
            for entry in data['context']['entries']:
                provenance=entry['provenance'];version=provenance.get('version_id')
                if entry['node_kind']=='CANDIDATE':
                    # Candidate source scope is already checked by Store; user statements remain separate.
                    candidate=entry['content']['candidate']
                    version=provenance['source_id'] if candidate['knowledge_kind']!='USER_STATEMENT' else None
                if version is not None and version not in allowed:raise CoreError('KAYNAK_KAPSAMI','Zorunlu bağlam kaynağı seçilmiş sürümler dışında')
                result['findings'].append({'node_id':entry['node_id'],'source_kind':entry['node_kind'],'content':entry['content'],
                    'provenance':provenance,'verification_status':entry['knowledge_status'],'trust':entry['trust']})
            result['status']='KISMI';result['chat_response']='Seçilmiş kaynak ve beyanlar ayrılarak inceleme bağlamı hazırlandı. Kaynaklı taslak değerlendirme yapılabilir; kritik inceleme tamamlandı kabul edilmez.'
    else:result['open_questions']=['İlgili belge/kanıt düğümlerini seç; mevcut geçerli kullanıcı beyanını yeniden isteme.']
    if request.get('business_context') is not None:
        if result['context_pack_id'] and not result['findings']:
            result['open_questions'].append('Zorunlu bağlam kapanımı hazır olmadan iş kayıtlarını inceleme bağlamına ekleme.')
        else:
            business=request['business_context']
            overview=store.business_overview(case,as_of=business['as_of'],scope_keys=business['scope_keys'],
                selected_versions=request['selected_versions'],policy_version=request['policy_version'],expected_revision=revision)
            context_bytes=result['context_budget']['used_bytes'] if result['context_budget'] else 0
            overview_bytes=len(canonical(overview).encode('utf-8'))
            required_bytes=context_bytes+overview_bytes
            ready=required_bytes<=request['max_context_bytes']
            result['business_budget']={'method':'CONTEXT_FIELD_PLUS_BUSINESS_OVERVIEW_UTF8_BYTES','max_bytes':request['max_context_bytes'],
                'context_bytes':context_bytes,'overview_bytes':overview_bytes,'required_bytes':required_bytes,
                'used_bytes':required_bytes if ready else context_bytes,'host_tokens':None}
            if ready:
                result['business_overview']=overview
                if overview['facts'] or overview['obligations'] or overview['events']:
                    result['status']='KISMI'
                    result['open_questions']=[question for question in result['open_questions'] if not question.startswith('İlgili belge/kanıt düğümlerini seç;')]
                    result['chat_response']='Kaynaklı iş bilgileri karşılaştırıldı; yükümlülüklerin aday vade ve gerçekleşme durumu çıkarıldı. Alan/olay yorumu ve iş kabulü ayrıca doğrulanmalı.'
                else:
                    result['chat_response']='Seçilen iş kapsamında kayıt bulunamadı; yeni bulgu veya yükümlülük uydurulmadı.'
            else:
                result['status']='BILGI_GEREKLI'
                result['open_questions'].append('İş kayıtları gerekli bağlamla birlikte bütçeye sığmıyor; kanıtı koruyarak kapsamı küçült veya bütçeyi artır.')
    if request.get('calculation') is not None:
        if skill not in {'K05','K06','K08','K09','K10','K11','K12','K14','K15','K16','K23','K24','K27'}:raise CoreError('HESAP_KAPSAMI','Bu skill para/tarih hesabı istemez')
        result['calculation']=calculate(request['calculation'])
        if result['status']=='BILGI_GEREKLI':result['status']='KISMI'
        if not result['chat_response']:result['chat_response']='Açık kullanıcı girdileriyle deterministik hesap yapıldı; sözleşme/olay doğrulaması ve değerlendirme ayrıca gerekir.'
        result['limitations'].append('Hesap yalnız açık kullanıcı girdilerini işler; girdilerin kaynak veya mevzuat doğrulaması ayrı kalır.')
    if skill=='K12' and request.get('scenario_id')=='S-20':
        result['open_questions'].append('Şirketin kendi poliçe satınalması kapsamı açık tercih olarak teyit edilmedi; diğer tedarikçi sigorta işleri sürebilir.')
    if skill in {'K19','K20'}:
        result['status']='BILGI_GEREKLI';result['open_questions'].append('Güncel ve kapsamı uygun resmi/kurumsal kaynak adaptörü ile kaynak sürümü sağlanmalı; doğrulandı iddiası üretme.')
    if skill=='K21':
        result['status']='UZMAN_GORUSU_GEREKLI';result['open_questions'].append('Gerçek yetki kaynağı, son ekler ve sürüme bağlı görüş/karar olmadan imzaya hazır kararı verilmez.')
    if request['requested_output']!='CHAT':
        result['status']='TEKNIK_ENGEL';result['chat_response']='Üretim Word yazıcı kimlik ve QA adaptörü CONFIG_REQUIRED. Taslak sohbet desteği sürebilir; dosya oluşturulmadı.'
        result['limitations'].append('P4 normal ajan eylemi kapalı; P5 sentetik test izni üretim izni değildir.')
    if store.case_revision(case)!=revision:raise CoreError('SURUM_CAKISMASI','Skill sırasında bağlam sürümü değişti')
    # Deterministic source recheck after assembly: no cached access or edited source escape.
    for version in request['selected_versions']:
        with store._db() as db:store._verification_source(db,case,version,current=True)
    result['chat_response']=meta['startup_message']+'\n\n'+result['chat_response']
    return checked('p6_skill_result',result)
