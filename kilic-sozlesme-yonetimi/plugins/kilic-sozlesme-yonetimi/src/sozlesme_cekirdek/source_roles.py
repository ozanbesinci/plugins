"""Explicit comparison reference and current target; byte delta grants no decision."""
import hashlib
from .errors import CoreError
from .safety import uuid_text


def first_byte_difference(reference,target):
    if reference==target:return None
    return next((index for index,(a,b) in enumerate(zip(reference,target)) if a!=b),min(len(reference),len(target)))


def compare_source_roles(store,case_id,reference_version_id,current_target_version_id):
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
            'same_bytes':old==new,'first_changed_byte':difference,'comparison_scope':'BYTES_ONLY',
            'semantic_comparison':'NOT_RUN','critical_analysis_allowed':False,'authority':'NOT_VERIFIED',
            'business_acceptance':'NOT_GRANTED','source_mutation':False,
            'limitations':['Historical reference is not a current decision input.',
                           'Explicit target selection is not global latest-version or corporate approval.',
                           'Byte difference is not clause alignment, text fidelity or legal meaning.']}
    from .workflows import checked
    return checked('source_comparison_result',result)
