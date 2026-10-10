"""Native-task orchestration. No model API, CLI runner, resume or hidden fallback."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import sys
import uuid

from kayit_temeli import contained, inventory, load, lock, save, sha
from model_secimi import PROFILES, allowed_role, recommend, resolve
from butce import budget, read_session
from oturum_kaydi import native_receipt_valid, read_native_session
from veri_kontrol import apply_corrections, compare, digest, fact_map, validate
from teklif_motoru import json_ready
from cikti_denetimi import validate_pdf, validate_xlsx


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_run(run):
    run = Path(run).resolve()
    manifest = load(run/'run.json')
    if manifest.get('schema') != 'teklif-run/v4':
        raise ValueError('v4 koşu kaydı gerekli; eski koşu yerinde dönüştürülmez.')
    return run, manifest


def write_run(run, manifest):
    save(run/'run.json', manifest)


def tracked(run, path):
    path = contained(run, path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Koşuya ait normal dosya gerekli.')
    return {'path': str(path.relative_to(run)), 'sha256': sha(path)}


def file_for(run, item):
    path = contained(run, run/item['path'])
    if sha(path) != item['sha256']:
        raise ValueError('Kayıt sonrası dosya değişti: '+item['path'])
    return path


def assert_fresh(run, m):
    for source in m['inventory']['entries']:
        for root in (Path(m['inventory']['root']), run/'sources'):
            path = contained(root, root/source['relative_path'])
            if not path.is_file() or sha(path) != source['sha256']:
                raise ValueError('Kaynak değişti/eksik; yeni koşu gerekli: '+source['relative_path'])
    actual = inventory(run/'skill')
    if actual['dataset_sha256'] != m['skill_sha256']:
        raise ValueError('Sabitlenmiş skill kopyası değişti.')
    for name, item in m.get('artifacts', {}).items():
        file_for(run, item)


def assert_open(m):
    if m.get('closed_at'):
        raise ValueError('Koşu kapalı; yeni revizyon yeni koşu olmalı.')


def refresh_sessions(m):
    """Discover native descendants from metadata, including unplanned grandchildren."""
    known = {s['session_id'] for s in m['sessions']}
    rows = []
    for path in Path(m['session_log_root']).rglob('*.jsonl'):
        try:
            with path.open(encoding='utf-8') as stream:
                event = json.loads(stream.readline())
            p = event.get('payload', {})
            src = p.get('source')
            sub = src.get('subagent') if isinstance(src, dict) else None
            spawn = sub.get('thread_spawn') if isinstance(sub, dict) else None
            parent = spawn.get('parent_thread_id') if isinstance(spawn, dict) else None
            if event.get('type') == 'session_meta' and parent:
                rows.append((p.get('id'), parent, path))
        except (OSError, ValueError):
            continue
    while True:
        added = False
        for identity, parent, path in rows:
            if identity and identity not in known and parent in known:
                m['sessions'].append({'session_id': identity, 'log_path': str(path.resolve()),
                                      'baseline': {}, 'discovered': True, 'parent_id': parent})
                known.add(identity); added = True
        if not added:
            break


def budget_state(m):
    refresh_sessions(m)
    return budget(m)


def can_start(m):
    check_main_model(m)
    state = budget_state(m)
    if state['status'] in {'EXHAUSTED', 'UNVERIFIED'}:
        raise ValueError('Yeni model görevi engellendi: '+state['status'])
    if state['status'] == 'ASK_AT_80' and not m.get('budget_warning_ack'):
        raise ValueError('Bütçe %80: kullanıcıya bildirip yanıtını ack-budget ile kaydedin.')
    if any(t['state'] == 'PLANNED' for t in m['tasks']):
        raise ValueError('Önce planlanan görevin gerçek oturumunu bind ile bağlayın veya iptal edin.')
    if len([t for t in m['tasks'] if t['state'] == 'RUNNING']) >= 3:
        raise ValueError('En fazla üç alt ajan eşzamanlı çalışabilir.')
    return state


def check_main_model(m):
    if m.get('closed_at'): return
    main=next(s for s in m['sessions'] if s['session_id']==m['main_session_id'])
    expected=m['roles']['extraction']
    current=read_session(main['log_path'])
    if any(current[key] != expected[key] for key in ('model', 'reasoning_effort')):
        raise ValueError('Ana sohbet GPT-6.1/High dışında; model ve efor seçimini düzeltin.')
    raw=Path(main['log_path']).read_bytes()[main.get('baseline_bytes',0):]
    for line in raw.splitlines():
        try: event=json.loads(line)
        except ValueError: continue
        if event.get('type')=='turn_context':
            context=event.get('payload',{})
            if context.get('model') != expected['model'] or context.get('effort') != expected['reasoning_effort']:
                raise ValueError('Koşu sırasında ana sohbet model/eforu GPT-6.1/High dışına geçti; yeni koşu gerekli.')


def prepare(source, run, catalog, main_log, profile, context, *, selected=None, downgrade_reason=None, log_root=None):
    source, run, main_log = Path(source).resolve(), Path(run).resolve(), Path(main_log).resolve()
    if run.exists() or source == run or source.is_relative_to(run):
        raise ValueError('Yeni ve kaynağı içermeyen koşu klasörü gerekli.')
    if run.is_relative_to(source) and not run.is_relative_to(source/'analiz'):
        raise ValueError('Kaynak altında çıktı yalnız analiz altına yazılabilir.')
    if profile not in PROFILES:
        raise ValueError('Profil geçersiz.')
    skill = Path(__file__).resolve().parents[1]
    if (skill.parent/'.teklif-update.lock').exists():
        raise ValueError('Güncelleme sürüyor; snapshot alınamaz.')
    original_skill_sha=inventory(skill)['dataset_sha256']
    roles = resolve(catalog)
    session = read_session(main_log)
    if any(session[key] != roles['extraction'][key] for key in ('model', 'reasoning_effort')):
        raise ValueError('Ana sohbeti GPT-6.1 modeline ve High eforuna geçirip yeniden hazırlayın.')
    if not session.get('usage'):
        raise ValueError('Ana oturum başlangıç token sayacı yok.')
    suggested = recommend(**context)
    order = {'hizli': 0, 'standart': 1, 'yuksek_guvence': 2}
    if order[profile] < order[suggested] and not (downgrade_reason and downgrade_reason.strip()):
        raise ValueError('Düşük profil için uyarı sonrası kullanıcının açık gerekçesi gerekli.')
    inv = inventory(source, selected)
    if not inv['entries']:
        raise ValueError('Kaynak envanteri boş.')
    run.mkdir(parents=True)
    try:
        (run/'sources').mkdir()
        for row in inv['entries']:
            target = run/'sources'/row['relative_path']; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source/row['relative_path'], target)
        shutil.copytree(skill, run/'skill', ignore=shutil.ignore_patterns('__pycache__', '.git', '.*'))
        if (skill.parent/'.teklif-update.lock').exists():
            raise ValueError('Snapshot sırasında güncelleme başladı; koşu geçersiz.')
        if inventory(skill)['dataset_sha256']!=original_skill_sha or inventory(run/'skill')['dataset_sha256']!=original_skill_sha:
            raise ValueError('Snapshot sırasında skill ağacı değişti; yeni koşu gerekli.')
        m = {'schema': 'teklif-run/v4', 'run_id': uuid.uuid4().hex, 'created_at': now(),
             'closed_at': None, 'profile': profile, 'recommended_profile': suggested,
             'downgrade_reason': downgrade_reason, 'context': context, 'catalog': catalog,
             'roles': roles, 'inventory': inv, 'skill_sha256': inventory(run/'skill')['dataset_sha256'],
             'main_session_id': session['session_id'], 'session_log_root': str(Path(log_root).resolve() if log_root else main_log.parent.parent),
             'sessions': [{'session_id': session['session_id'], 'log_path': str(main_log), 'baseline': session['usage'], 'baseline_bytes':main_log.stat().st_size}],
             'tasks': [], 'artifacts': {}, 'correction_rounds': 0, 'controls': {}}
        refresh_sessions(m)
        if not main_log.is_relative_to(Path(m['session_log_root'])):
            raise ValueError('Oturum tarama kökü ana logu içermeli.')
        for binding in m['sessions'][1:]:
            observed = read_session(binding['log_path'])
            if not observed.get('usage'):
                raise ValueError('Önceden açılmış alt oturum başlangıç sayacı eksik.')
            binding['baseline'] = observed['usage']
            binding['preexisting'] = True
        assert_fresh(run, m)
        write_run(run, m)
        return {'run_id': m['run_id'], 'run': str(run), 'runner': str(run/'skill/scripts/ajan_yonetimi.py'),
                'profile': profile, 'recommended_profile': suggested, 'roles': roles, 'source_count': len(inv['entries'])}
    except BaseException:
        save(run/'preparation-failed.json', {'status': 'FAILED', 'at': now()})
        raise


def find_task(m, identity):
    matches = [t for t in m['tasks'] if t['task_id'] == identity]
    if len(matches) != 1:
        raise ValueError('Görev bulunamadı.')
    return matches[0]


def plan_task(run, role, purpose, *, phase='initial'):
    run, m = read_run(run)
    with lock(run):
        m = load(run/'run.json')
        assert_open(m); assert_fresh(run, m); state = can_start(m)
        if not allowed_role(m['profile'], role) or phase not in {'initial', 'revision'} or not purpose.strip():
            raise ValueError('Profil/rol/aşama/amaç geçersiz.')
        if role == 'blind_review' and any(k in m['artifacts'] for k in ('diff', 'verdict')):
            raise ValueError('Kör okuma karşılaştırmadan önce başlatılmalı; yeni koşu açın.')
        if role in {'adjudicator','decision_summary'}:
            qa_item = m['artifacts'].get('qa'); diff_item = m['artifacts'].get('diff')
            if not qa_item or (role=='adjudicator' and not diff_item):
                raise ValueError('Hakem öncesi kod QA ve fark listesi gerekli.')
            if load(file_for(run, qa_item))['status'] != 'PASS':
                raise ValueError('Kod QA geçmeden hakem başlatılamaz.')
            count = len([t for t in m['tasks'] if t['role'] == role and t['state'] != 'CANCELLED'])
            if role=='adjudicator' and count >= PROFILES[m['profile']]['max_revisions'] + 1:
                raise ValueError('Hakem/düzeltme tur sınırı doldu; açık konuları ön sonuçta bırakın.')
            if role=='decision_summary' and 'applied' not in m['artifacts']:
                raise ValueError('Karar özeti hakem sonrası güncel veriyle hazırlanmalı.')
        task_id = uuid.uuid4().hex[:12]
        directory = run/'tasks'/task_id; directory.mkdir(parents=True)
        task = {'task_id': task_id, 'role': role, 'phase': phase, 'purpose': purpose,
                'expected': m['roles'][role], 'state': 'PLANNED', 'created_at': now()}
        task['inputs'] = {k: v['sha256'] for k,v in m['artifacts'].items()} if role in {'adjudicator','decision_summary'} else {}
        m['tasks'].append(task); write_run(run, m)
        instructions = {'run_id': m['run_id'], **task, 'output_dir': str(directory),
                        'raw_sources': str(run/'sources'), 'source_inventory': m['inventory']['entries'],
                        'rule': 'Fresh native subagent; no resume, no descendant agents; report actual model+effort; seal-result in this child before returning.'}
        if role in {'blind_review', 'targeted_review'}:
            instructions['rule'] += ' Read original documents/images only. Do not open main data, other agent outputs, workbook, diff or verdict. Include free_notes.'
        save(directory/'assignment.json', instructions)
        return instructions


def bind(run, task_id, log):
    run, m = read_run(run)
    with lock(run):
        m = load(run/'run.json')
        assert_open(m); task = find_task(m, task_id)
        if task['state'] != 'PLANNED':
            raise ValueError('Yalnız yeni görev bağlanabilir.')
        actual = read_session(log)
        if any(s['session_id']==actual['session_id'] and s.get('preexisting') for s in m['sessions']):
            raise ValueError('Koşu öncesinde var olan oturum yeni görevde kullanılamaz.')
        if any(t.get('session_id') == actual['session_id'] for t in m['tasks']) or actual['session_id'] == m['main_session_id']:
            raise ValueError('Yeni ve benzersiz alt oturum gerekli; resume yasak.')
        if actual.get('parent_id') != m['main_session_id']:
            raise ValueError('Alt ajan ana koşu oturumunun doğrudan çocuğu olmalı.')
        for key in ('model', 'reasoning_effort'):
            if actual[key] != task['expected'][key]:
                raise ValueError('Gerçek '+key+' görev beklentisiyle uyuşmuyor.')
        task.update(session_id=actual['session_id'], state='RUNNING', log_path=actual['log_path'])
        if actual['session_id'] not in {s['session_id'] for s in m['sessions']}:
            m['sessions'].append({'session_id': actual['session_id'], 'log_path': actual['log_path'], 'baseline': {}, 'parent_id': actual['parent_id']})
        write_run(run, m)
        return {'status': 'BOUND', 'task_id': task_id, 'session_id': actual['session_id']}


def seal_result(run, task_id, artifact):
    run, m = read_run(run); assert_open(m); task = find_task(m, task_id)
    if task['state'] != 'RUNNING':
        raise ValueError('Görev gerçek oturuma bağlı değil.')
    artifact = contained(run/'tasks'/task_id, artifact)
    item = tracked(run, artifact)
    # The marker must be emitted as a tool result INSIDE the bound child's log.
    return {'run_id': m['run_id'], 'task_id': task_id, 'role': task['role'], **item}


def register(run, task_id, artifact):
    run, m = read_run(run)
    with lock(run):
        m = load(run/'run.json')
        task = find_task(m, task_id); seal = seal_result(run, task_id, artifact)
        receipt = read_native_session(task['log_path'], seal=seal)
        if receipt['session_id'] != task['session_id'] or any(receipt[k] != task['expected'][k] for k in ('model', 'reasoning_effort')):
            raise ValueError('Gerçek kabul oturumu/modeli/eforu yanlış.')
        for raw in Path(task['log_path']).read_bytes()[:receipt['log_bytes']].splitlines():
            event=json.loads(raw)
            if event.get('type')=='turn_context':
                p=event['payload']
                if p.get('model')!=task['expected']['model'] or p.get('effort')!=task['expected']['reasoning_effort']:
                    raise ValueError('Alt oturum içinde model/efor değiştirilmiş; yeni görev gerekli.')
        task.update(state='COMPLETED', receipt=receipt, result=tracked(run, artifact), completed_at=now())
        write_run(run, m)
        return {'status': 'REGISTERED', 'task_id': task_id}


def record(run, kind, path):
    run, m = read_run(run)
    allowed = {'data', 'workbook', 'excel_receipt', 'pdf', 'visual', 'coverage', 'blind', 'verdict', 'decision'}
    if kind not in allowed:
        raise ValueError('Artefakt türü geçersiz.')
    with lock(run):
        m = load(run/'run.json')
        assert_open(m)
        item = tracked(run, path)
        if m['artifacts'].get(kind) == item:
            return {'status': 'UNCHANGED', 'kind': kind}
        dependencies={
            'data': ('qa','diff','verdict','applied','workbook','excel_receipt','pdf','visual','decision'),
            'coverage': ('qa','diff','verdict','applied','workbook','excel_receipt','pdf','visual','decision'),
            'blind': ('diff','verdict','applied','workbook','excel_receipt','pdf','visual','decision'),
            'verdict': ('applied','workbook','excel_receipt','pdf','visual','decision'),
            'decision': ('workbook','excel_receipt','pdf','visual'),
            'workbook': ('excel_receipt','pdf','visual'), 'pdf': ('visual',)}
        for key in dependencies.get(kind,()): m['artifacts'].pop(key,None)
        m['artifacts'][kind] = item; write_run(run, m)
        return {'status': 'RECORDED', 'kind': kind, **item}


def coverage_check(m, coverage, data):
    expected = {s['source_id']: s['sha256'] for s in m['inventory']['entries']}
    rows = coverage.get('sources', [])
    if len(rows) != len(expected) or {r.get('source_id') for r in rows} != set(expected):
        raise ValueError('Bütün özgün dosyalar kapsama alınmalı.')
    for r in rows:
        if r.get('source_sha256') != expected[r['source_id']] or r.get('status') not in {'read', 'unreadable', 'not_applicable'}:
            raise ValueError('Kaynak kapsam kanıtı hatalı.')
        if not r.get('locations') or not r.get('notes'):
            raise ValueError('Dosya sayfa/sayfa adı kapsamı ve okuma notu gerekli.')
        if r.get('document_kind') not in {'offer','specification','support','unreadable'}:
            raise ValueError('Her dosya offer/specification/support/unreadable türünde sınıflanmalı.')
        if r['document_kind']=='offer' and not r.get('offer_ids'):
            raise ValueError('Teklif dosyası en az bir merkezi teklif kaydına bağlı olmalı.')
    ids={o['id'] for o in data['offers']}
    bound={oid for r in rows for oid in r.get('offer_ids',[])}
    if bound!=ids: raise ValueError('Kaynak teklifleri ile merkezi firmalar birebir kapsanmalı.')
    for o in data['offers']:
        source_ids={r['source_id'] for r in rows if o['id'] in r.get('offer_ids',[])}
        if set(o.get('source_ids',[]))!=source_ids: raise ValueError('Firma özgün kaynak listesi eksik/yanlış.')
    return [r['source_id'] for r in rows if r['status'] == 'unreadable']


def requirement_coverage(run,m,data):
    if not m['context']['has_spec']: return
    tasks=[t for t in m['tasks'] if t['role']=='requirements' and t['state']=='COMPLETED']
    if not tasks or not data.get('requirements'):
        raise ValueError('Şartname var: bağımsız şartname görevi ve boş olmayan hüküm listesi gerekli.')
    extracted={}
    for t in tasks:
        result=load(file_for(run,t['result']))
        for r in result.get('requirements',[]):
            if r['id'] in extracted and extracted[r['id']]!=r: raise ValueError('Şartname görevleri arasında çelişkili hüküm.')
            extracted[r['id']]=r
    actual={r['id']:r for r in data['requirements']}
    if extracted!=actual: raise ValueError('Şartname çıkarımı ile merkezi hüküm listesi uyuşmuyor.')


def qa(run):
    run, m = read_run(run)
    with lock(run):
        m = load(run/'run.json')
        assert_open(m); assert_fresh(run, m)
        data = load(file_for(run, m['artifacts']['data']))
        result = json_ready(validate(data, m['inventory']))
        result['coverage_sha256']=m['artifacts'].get('coverage',{}).get('sha256')
        try:
            unreadable = coverage_check(m, load(file_for(run, m['artifacts']['coverage'])),data)
            requirement_coverage(run,m,data)
            if unreadable:
                result['open_issues'].append('Okunamayan kaynaklar: '+', '.join(unreadable))
        except (ValueError, KeyError) as error:
            result['failures'].append(str(error)); result['status'] = 'FAIL'
        if result['status']=='PASS':
            try:
                from excel_uret import build
                from excel_dogrula import preflight
                draft=run/'checks'/('draft-'+digest(result)+'.xlsx')
                draft.parent.mkdir(parents=True,exist_ok=True)
                if not draft.exists(): build(data,draft,m['profile'],m['inventory'],result)
                preflight(draft,data)
                m['artifacts']['draft_workbook']=tracked(run,draft)
                m['artifacts']['draft_contract']=tracked(run,draft.with_suffix('.xlsx.contract.json'))
                result['excel_preflight']=True
            except (ValueError,OSError,KeyError) as error:
                result['failures'].append('Excel mekanik ön kontrol: '+str(error)); result['status']='FAIL'
        path = run/'checks'/('qa-'+result['data_sha256']+'.json')
        save(path, result); m['artifacts']['qa'] = tracked(run, path); write_run(run, m)
        return result


def compare_run(run):
    run, m = read_run(run)
    with lock(run):
        m = load(run/'run.json')
        assert_open(m); assert_fresh(run, m)
        data, independent = [load(file_for(run, m['artifacts'][k])) for k in ('data','blind')]
        role = 'targeted_review' if m['profile'] == 'hizli' else 'blind_review'
        matching = [t for t in m['tasks'] if t['role'] == role and t['state'] == 'COMPLETED' and t['result'] == m['artifacts']['blind']]
        if not matching or not native_receipt_valid(matching[-1]['receipt']):
            raise ValueError('Bağımsız okuma gerçek ayrı oturumdan gelmeli.')
        source_ids={s['source_id'] for s in m['inventory']['entries']}
        if set(independent.get('reviewed_source_ids',[])) != source_ids:
            raise ValueError('Bağımsız okuma bütün kaynakları kapsamalı; okunamayanları serbest notta belirtin.')
        if set(independent.get('offer_ids',[]))!={o['id'] for o in data['offers']}:
            raise ValueError('Bağımsız okuma ile merkezi teklif/firma kapsamı uyuşmuyor.')
        critical_ids={f for f,v in fact_map(data).items() if v.get('critical')}
        if not critical_ids.issubset(fact_map(independent)):
            raise ValueError('Bağımsız okumada kritik alan/hüküm kaydı atlanamaz; eksik ise açık missing kaydı girin.')
        if m['profile']=='hizli':
            critical_sources={v.get('source_id') for v in fact_map(data).values() if v.get('critical') and v.get('source_id')}
            reviewed=set()
            for row in independent.get('image_reviews',[]):
                image=file_for(run,{'path':row['image_path'],'sha256':row['image_sha256']})
                if image.suffix.lower() not in {'.png','.jpg','.jpeg'} or not row.get('location') or not row.get('observations'):
                    raise ValueError('Hedefli kontrolde gerçek sayfa görüntüsü ve gözlem gerekli.')
                reviewed.add(row.get('source_id'))
            if not critical_sources.issubset(reviewed):
                raise ValueError('Hızlı profilde her kritik kaynak için özgün sayfa görüntüsü kontrolü gerekli.')
        result = compare(data, independent)
        if m['profile'] == 'yuksek_guvence':
            result['decision_reasons'] = {'exclusions': data.get('exclusions', []), 'recommendation': data.get('recommendation'), 'decision_summary': data.get('decision_summary')}
        path = run/'checks'/('diff-'+digest(result)+'.json'); save(path, result)
        if m['artifacts'].get('diff') != tracked(run,path):
            for key in ('verdict','applied','workbook','excel_receipt','pdf','visual','decision'): m['artifacts'].pop(key,None)
        m['artifacts']['diff'] = tracked(run, path); write_run(run, m)
        return {'status': 'COMPARED', 'differences': len(result['differences']), 'path': str(path), 'sha256': digest(result)}


def apply_run(run, output):
    run, m = read_run(run)
    with lock(run):
        m = load(run/'run.json')
        assert_open(m); assert_fresh(run, m)
        data, diff, verdict = [load(file_for(run, m['artifacts'][k])) for k in ('data','diff','verdict')]
        tasks = [t for t in m['tasks'] if t['role']=='adjudicator' and t['state']=='COMPLETED' and t['result']==m['artifacts']['verdict']]
        if not tasks or not native_receipt_valid(tasks[-1]['receipt']) or tasks[-1]['inputs'].get('data') != m['artifacts']['data']['sha256'] or tasks[-1]['inputs'].get('diff') != m['artifacts']['diff']['sha256']:
            raise ValueError('Hakem güncel veri/fark listesi üzerinde gerçek ayrı oturumda çalışmalı.')
        if m['profile']=='yuksek_guvence' and verdict.get('decision_reasons_sha256') != digest(diff['decision_reasons']):
            raise ValueError('Yüksek güvencede eleme/karar gerekçeleri ayrıca onaylanmalı.')
        changed = any(d.get('replacement') for d in verdict.get('decisions', []))
        if changed and m['correction_rounds'] >= PROFILES[m['profile']]['max_revisions']:
            raise ValueError('Düzeltme tur sınırı doldu; açık farklarla ön sonuç hazırlayın.')
        sources = {s['source_id']:s['sha256'] for s in m['inventory']['entries']}
        result = apply_corrections(data, verdict, diff, sources)
        output = contained(run, output)
        if output.exists():
            raise ValueError('Yeni revizyon dosyası gerekli.')
        save(output, result)
        for key in ('qa','workbook','excel_receipt','pdf','visual','decision'):
            m['artifacts'].pop(key,None)
        m['artifacts']['data'] = tracked(run, output)
        proof = {'data_sha256': digest(result), 'verdict': m['artifacts']['verdict'], 'diff': m['artifacts']['diff'], 'task_id': tasks[-1]['task_id']}
        p = run/'checks'/('applied-'+digest(result)+'.json'); save(p,proof); m['artifacts']['applied'] = tracked(run,p)
        m['correction_rounds'] += int(changed); write_run(run,m)
        return {'status':'APPLIED','path':str(output),'requires':'qa, rebuild Excel, COM reconciliation'}


def verify(run, _locked=False):
    if not _locked:
        with lock(Path(run).resolve()):
            return verify(run, _locked=True)
    run,m = read_run(run)
    failures, open_issues = [], []
    try:
        assert_fresh(run,m)
        check_main_model(m)
        state=budget_state(m)
        if state['missing'] or state['status']=='UNVERIFIED':
            failures.append('Token telemetrisi eksik; bütçe doğrulanamadı.')
        if any(t['state'] in {'RUNNING','PLANNED'} for t in m['tasks']):
            failures.append('Bitmemiş görev var.')
        for t in m['tasks']:
            if t['state']=='COMPLETED':
                file_for(run,t['result'])
                if not native_receipt_valid(t['receipt']):
                    failures.append('Gerçek oturum makbuzu geçersiz: '+t['task_id'])
        required_roles = {'extraction','adjudicator','decision_summary', 'targeted_review' if m['profile']=='hizli' else 'blind_review'}
        if m['context']['has_spec']:
            required_roles.add('requirements')
        done={t['role'] for t in m['tasks'] if t['state']=='COMPLETED'}
        if 'extraction_difficult' in done: done.add('extraction')
        if required_roles-done:
            failures.append('Eksik görevler: '+', '.join(sorted(required_roles-done)))
        required={'data','qa','coverage','blind','diff','verdict','applied','workbook','excel_receipt','decision'}
        if m['profile']=='yuksek_guvence': required |= {'pdf','visual'}
        if required-set(m['artifacts']):
            failures.append('Eksik çıktılar: '+', '.join(sorted(required-set(m['artifacts']))))
        if failures: return {'status':'BLOCKED','failures':failures,'open_issues':open_issues,'budget':state}
        data=load(file_for(run,m['artifacts']['data']))
        checks=json_ready(validate(data,m['inventory']))
        coverage_check(m,load(file_for(run,m['artifacts']['coverage'])),data)
        requirement_coverage(run,m,data)
        failures.extend(checks['failures']); open_issues.extend(checks['open_issues'])
        qa_result=load(file_for(run,m['artifacts']['qa']))
        if qa_result['data_sha256']!=digest(data) or qa_result['status']!='PASS' or qa_result.get('coverage_sha256')!=m['artifacts']['coverage']['sha256']:
            failures.append('Kod QA güncel ve başarılı değil.')
        open_issues.extend(qa_result.get('open_issues',[]))
        applied=load(file_for(run,m['artifacts']['applied']))
        if applied['data_sha256']!=digest(data) or applied['verdict']!=m['artifacts']['verdict'] or applied['diff']!=m['artifacts']['diff']:
            failures.append('Hakem sonrası veri tekrar değişti.')
        comparison=load(file_for(run,m['artifacts']['diff']))
        independent=load(file_for(run,m['artifacts']['blind']))
        if comparison['blind_sha256']!=digest(independent): failures.append('Bağımsız okuma/fark zinciri bozuldu.')
        review_role='targeted_review' if m['profile']=='hizli' else 'blind_review'
        if not any(t['role']==review_role and t['state']=='COMPLETED' and t['result']==m['artifacts']['blind'] for t in m['tasks']):
            failures.append('Bağımsız okuma kaydı gerçek görevle eşleşmiyor.')
        verdict=load(file_for(run,m['artifacts']['verdict']))
        open_issues.extend('Çözülemeyen fark: '+d['difference_id'] for d in verdict['decisions'] if d['decision']=='open')
        workbook=file_for(run,m['artifacts']['workbook']); validate_xlsx(workbook)
        receipt=load(file_for(run,m['artifacts']['excel_receipt']))
        if receipt.get('status')!='PASS' or receipt.get('workbook_sha256')!=sha(workbook) or receipt.get('data_sha256')!=digest(data):
            failures.append('Excel gerçek hesap makbuzu güncel ve başarılı değil.')
        contract_path=workbook.with_suffix('.xlsx.contract.json')
        contract=load(contract_path)
        if receipt.get('contract_sha256')!=sha(contract_path) or contract.get('profile')!=m['profile'] or contract.get('inventory_sha256')!=digest(m['inventory']) or contract.get('qa_sha256')!=digest(qa_result):
            failures.append('Excel sözleşmesi profil/kaynak/QA veya gerçek hesap makbuzuyla uyuşmuyor.')
        for key in ('recalculation','reconciliation','parameter_restore','layout'):
            if receipt.get('checks',{}).get(key) is not True: failures.append('Excel kontrolü eksik: '+key)
        decision=load(file_for(run,m['artifacts']['decision']))
        summaries=[t for t in m['tasks'] if t['role']=='decision_summary' and t['state']=='COMPLETED' and t['result']==m['artifacts']['decision']]
        if not summaries or summaries[-1]['inputs'].get('data')!=m['artifacts']['data']['sha256']:
            failures.append('Karar özeti gerçek güncel görev çıktısı değil.')
        if decision.get('data_sha256')!=digest(data) or not decision.get('summary'):
            failures.append('Karar özeti güncel veriye bağlı değil.')
        if receipt.get('decision_sha256')!=digest(decision):
            failures.append('Excel karar özeti bağımsız karar artefaktıyla eşleşmiyor.')
        if m['downgrade_reason'] and m['downgrade_reason'] not in decision.get('summary',''):
            failures.append('Profil düşürme gerekçesi karar özetinde yok.')
        if open_issues and decision.get('recommendation') is not None:
            failures.append('Açık kritik konu varken kesin firma önerisi verilemez.')
        if m['profile']=='yuksek_guvence':
            pdf=file_for(run,m['artifacts']['pdf']); pdf_info=validate_pdf(pdf)
            visual=load(file_for(run,m['artifacts']['visual']))
            if receipt.get('pdf_sha256')!=sha(pdf) or not visual_review_valid(visual,sha(pdf),contract['sheets'],pdf_info['pages']):
                failures.append('Tüm sekme ve PDF sayfalarının görsel kontrolü güncel PDF ile doğrulanmadı.')
        if state['status']=='EXHAUSTED': open_issues.append('Bütçe sınırı doldu; ön sonuç.')
        return {'status':'BLOCKED' if failures else 'PRELIMINARY' if open_issues else 'VERIFIED',
                'failures':failures,'open_issues':sorted(set(open_issues)),'budget':state}
    except (OSError,ValueError,KeyError,TypeError) as error:
        return {'status':'BLOCKED','failures':failures+[str(error)],'open_issues':open_issues}


def visual_review_valid(visual, pdf_sha, sheets, pages):
    observations=visual.get('observations',[])
    return (visual.get('pdf_sha256')==pdf_sha and visual.get('status')=='PASS'
            and set(visual.get('sheets',[]))==set(sheets)
            and set(visual.get('pages',[]))==set(range(1,pages+1))
            and isinstance(observations,list)
            and all(any(isinstance(o,dict) and o.get('page')==p and o.get('sheet') in sheets
                        and str(o.get('finding','')).strip() for o in observations) for p in range(1,pages+1))
            and {o.get('sheet') for o in observations if isinstance(o,dict)}==set(sheets))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare')
    for name in ('source','run','catalog','main-log','context','profile'): a.add_argument('--'+name,required=True)
    a.add_argument('--sources'); a.add_argument('--downgrade-reason'); a.add_argument('--log-root')
    for name in ('task','bind','seal-result','register','record','qa','compare','apply','verify','status','close','ack-budget','cancel'):
        a=sub.add_parser(name); a.add_argument('--run',required=True)
        if name=='task':
            a.add_argument('--role',required=True); a.add_argument('--purpose',required=True); a.add_argument('--phase',default='initial')
        if name in {'bind','seal-result','register','cancel'}: a.add_argument('--task',required=True)
        if name=='bind': a.add_argument('--log',required=True)
        if name in {'seal-result','register','record'}: a.add_argument('--path',required=True)
        if name=='record': a.add_argument('--kind',required=True)
        if name=='apply': a.add_argument('--output',required=True)
        if name in {'ack-budget','cancel'}: a.add_argument('--reason',required=True)
    args=p.parse_args(argv)
    try:
        c=args.command
        if c!='prepare' and Path(__file__).resolve().parents[1] != (Path(args.run).resolve()/'skill'):
            raise ValueError('Bu koşunun sabit skill kopyasındaki scripts/ajan_yonetimi.py yolunu kullanın.')
        if c=='prepare':
            result=prepare(args.source,args.run,load(args.catalog),args.main_log,args.profile,load(args.context),selected=load(args.sources) if args.sources else None,downgrade_reason=args.downgrade_reason,log_root=args.log_root)
        elif c=='task': result=plan_task(args.run,args.role,args.purpose,phase=args.phase)
        elif c=='bind': result=bind(args.run,args.task,args.log)
        elif c=='seal-result':
            print('TEKLIF_RESULT_SEAL:'+json.dumps(seal_result(args.run,args.task,args.path),ensure_ascii=False)); return 0
        elif c=='register': result=register(args.run,args.task,args.path)
        elif c=='record': result=record(args.run,args.kind,args.path)
        elif c=='qa': result=qa(args.run)
        elif c=='compare': result=compare_run(args.run)
        elif c=='apply': result=apply_run(args.run,args.output)
        elif c=='verify': result=verify(args.run)
        else:
            run,m=read_run(args.run)
            with lock(run):
                m = load(run/'run.json')
                if c=='status': result={'profile':m['profile'],'budget':budget_state(m),'tasks':[{k:t.get(k) for k in ('task_id','role','state','session_id')} for t in m['tasks']],'artifacts':list(m['artifacts'])}
                elif c=='ack-budget':
                    assert_open(m)
                    if not args.reason.strip(): raise ValueError('Kullanıcı yanıtını kaydedin.')
                    m['budget_warning_ack']={'at':now(),'reason':args.reason}; result={'status':'ACKNOWLEDGED','limits_unchanged':True}
                elif c=='cancel':
                    assert_open(m); t=find_task(m,args.task)
                    if t['state']!='PLANNED': raise ValueError('Başlatılmış görevi önce native araçla bitirin; kaydı silinmez.')
                    t.update(state='CANCELLED',reason=args.reason); result={'status':'CANCELLED'}
                elif c=='close':
                    result=verify(run,_locked=True)
                    if result['status']=='BLOCKED': raise ValueError('Teslim kapısı BLOCKED; önce eksikleri düzeltin.')
                    if not m['closed_at']:
                        m['budget_final']=result['budget']; m['closed_at']=now()
                    m['result']=result
                write_run(run,m)
        print(json.dumps(json_ready(result),ensure_ascii=False,indent=2))
        return 2 if result.get('status') in {'FAIL','BLOCKED'} else 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'status':'BLOCKED','error':str(error)},ensure_ascii=False)); return 2


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
