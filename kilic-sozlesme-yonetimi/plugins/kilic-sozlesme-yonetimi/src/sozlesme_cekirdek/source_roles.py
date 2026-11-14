"""Explicit comparison reference and current target; byte delta grants no decision."""
import hashlib
from difflib import SequenceMatcher
from .errors import CoreError
from .safety import uuid_text, canonical, hash_value


def first_byte_difference(reference,target):
    if reference==target:return None
    return next((index for index,(a,b) in enumerate(zip(reference,target)) if a!=b),min(len(reference),len(target)))


def compare_source_roles(store,case_id,reference_version_id,current_target_version_id, *, format=None, view='RAW',
                         max_context_bytes=1048576, policy_version='1'):
    case,reference,target=map(uuid_text,(case_id,reference_version_id,current_target_version_id))
    def read(db):
        old,old_sha,old_document,old_current=store._verification_source(db,case,reference)
        new,new_sha,new_document,new_current=store._verification_source(db,case,target,current=True)
        if old_document!=new_document:
            raise CoreError('KAYNAK_KAPSAMI','Revizyon karşılaştırması aynı mantıksal belge içinde olmalı')
        if db.execute('SELECT 1 FROM surum_ebeveynleri WHERE case_id=? AND parent_id=? LIMIT 1',[case,target]).fetchone():
            raise CoreError('KARAR_KAYNAGI_ESKI','Güncel hedefin alt sürümü var; eski sürüm hedefe yükseltilmedi')
        if store._invalid(db,case,[target]):
            raise CoreError('YENIDEN_INCELE','Güncel hedef bağımlılığı geçersizleştirilmiş')
        return old,new,old_sha,new_sha,old_current,new_current,old_document
    with store._db() as db:
        revision=store._case(db,case)
        before=read(db)
    old,new,old_sha,new_sha,old_current,new_current,document=before
    difference=first_byte_difference(old,new)
    text_comparison = None
    if format is not None:
        from .readers import read_document
        from .verification import reading_profile
        if view not in {'RAW', 'BEFORE', 'AFTER', 'DISPLAY'} or type(max_context_bytes) is not int or not 64 <= max_context_bytes <= 1048576:
            raise CoreError('GECERSIZ_GIRDI', 'Karşılaştırma görünümü/bütçesi geçersiz')
        reports = [read_document(data, format) for data in (old, new)]
        selected = []
        for report in reports:
            if any(u['views'][view] is None for u in report['units']):
                raise CoreError('GORUNUM_GEREKLI', 'Seçilen görünüm bu kaynak biçiminde desteklenmiyor')
            rows = [{'unit_id': u['unit_id'], 'locator': u['locator'], 'kind': u['kind'],
                     'text': u['views'][view], 'attributes': u['attributes']}
                    for u in report['units'] if u['views'][view] is not None]
            if not rows or not any(r['text'].strip() for r in rows):
                raise CoreError('HEDEFLI_KANIT_GEREKLI', 'Metin kanıtı olmayan kaynaklar eşit metin sayılamaz')
            if len(rows) > 512:
                raise CoreError('BAGLAM_SINIRI', 'Karşılaştırma en fazla 512 metin birimi içerir; daha dar kaynak seç')
            selected.append(rows)
        text_comparison = {'format': format, 'view': view,
                           'reader_profile_digest': reading_profile(format, policy_version)[1],
                           'reference_reading_digest': hash_value(reports[0]), 'target_reading_digest': hash_value(reports[1]),
                           'reference_units': selected[0], 'target_units': selected[1],
                           'reference_issues': reports[0]['issues'], 'target_issues': reports[1]['issues'],
                           'changes': [], 'same_text': [r['text'] for r in selected[0]] == [r['text'] for r in selected[1]]}
        if len(canonical(text_comparison).encode('utf-8')) > max_context_bytes:
            raise CoreError('BAGLAM_SINIRI', 'İki sürümün tam metin kanıtı bütçeye sığmıyor; kırpılmadı')
        for op, a, b, c, d in SequenceMatcher(None, [r['text'] for r in selected[0]], [r['text'] for r in selected[1]], autojunk=False).get_opcodes():
            if op != 'equal':
                text_comparison['changes'].append({'operation': op, 'reference_start': a, 'reference_end': b, 'target_start': c, 'target_end': d})
    # Recheck after potentially long comparison without keeping the DB locked.
    with store._db() as db:
        store._case(db,case,revision)
        after=read(db)
        if before!=after:
            raise CoreError('KAYNAK_DEGISTI','Karşılaştırma sırasında kaynak/rol bağı değişti')
    result={'schema_version':'source-comparison-1.0','case_id':case,'document_id':document,'context_version':revision,
            'reference':{'role':'REFERENCE_ONLY','version_id':reference,'sha256':old_sha,'size_bytes':len(old),
                         'original_file_matches_snapshot':old_current,'decision_authority':'NONE'},
            'target':{'role':'SELECTED_CURRENT_TARGET','version_id':target,'sha256':new_sha,'size_bytes':len(new),
                      'original_file_matches_snapshot':new_current,'decision_authority':'NONE'},
            'same_bytes':old==new,'first_changed_byte':difference,'comparison_scope':'EXTRACTED_TEXT_ONLY' if text_comparison else 'BYTES_ONLY',
            'semantic_comparison':'NOT_RUN','critical_analysis_allowed':False,'authority':'NOT_VERIFIED',
            'business_acceptance':'NOT_GRANTED','source_mutation':False,
            'limitations':['Historical reference is not a current decision input.',
                           'Explicit target selection is not global latest-version or corporate approval.',
                           'Byte difference is not clause alignment, text fidelity or legal meaning.']}
    if text_comparison is not None:
        result['text_comparison'] = text_comparison
        result['limitations'].append('Extracted text alignment is deterministic, reference-only and not legal/semantic acceptance.')
        if len(canonical(result).encode('utf-8')) > max_context_bytes:
            raise CoreError('BAGLAM_SINIRI', 'Karşılaştırma sonucu bütçeye sığmıyor; kanıt kırpılmadı')
    from .workflows import checked
    return checked('source_comparison_result',result)
