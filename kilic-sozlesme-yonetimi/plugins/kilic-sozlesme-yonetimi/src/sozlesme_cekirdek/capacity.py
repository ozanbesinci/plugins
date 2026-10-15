"""Read-only retained-row quotas; no pruning, limit change or semantic approval."""
from .errors import CoreError
from .safety import uuid_text


def capacity_snapshot(store, case_id):
    from . import context, business, verification, guard
    case=uuid_text(case_id)
    limits={'icerik_birimleri':context.MAX_NODES,'iliskiler':context.MAX_RELATIONS,
            'baglam_paketleri':context.MAX_PACKS,'islemler':guard.MAX_OPERATIONS,
            'eylem_kararlari':guard.MAX_DECISIONS,**business.LIMITS}
    allowed={'icerik_birimleri','iliskiler','baglam_paketleri','islemler','eylem_kararlari',
             'is_bilgisi_baglari','yukumlulukler','gerceklesmeler'}
    if set(limits)!=allowed or any(type(limit) is not int or limit<0 for limit in limits.values()):
        raise CoreError('CONFIG_REQUIRED','Kapasite kaynakları beklenen kapalı tanımla eşleşmiyor')

    def row(resource,scope,identifier,used,limit,**extra):
        return dict(resource=resource,scope=scope,scope_id=identifier,used=used,limit=limit,
                    remaining=max(0,limit-used),status='OVER_LIMIT' if used>limit else 'AT_LIMIT' if used==limit else 'AVAILABLE',
                    quota_basis='ALL_RETAINED_ROWS',**extra)

    with store._db() as db:
        revision=store._case(db,case)
        rows=[]
        for table,limit in limits.items():
            used=db.execute(f'SELECT count(*) FROM {table} WHERE case_id=?',[case]).fetchone()[0]
            invalidated=db.execute(f'SELECT count(*) FROM {table} t WHERE t.case_id=? AND EXISTS '
                                   '(SELECT 1 FROM gecersizlestirmeler g WHERE g.case_id=t.case_id AND g.target_id=t.record_id)',[case]).fetchone()[0]
            extra={'dependency_invalidated_rows':invalidated,'semantic_validity_checked':False}
            if table=='baglam_paketleri':
                current=db.execute('SELECT count(*) FROM baglam_paketleri WHERE case_id=? AND semantic_version=?',[case,revision]).fetchone()[0]
                extra.update(current_revision_rows=current,older_revision_rows=used-current)
            rows.append(row(table,'CASE',case,used,limit,**extra))
        controls=db.execute('SELECT document_version_id,count(*) FROM dogrulamalar WHERE case_id=? GROUP BY document_version_id',[case]).fetchall()
        versions=[str(value[0]) for value in db.execute('SELECT record_id FROM belge_surumu WHERE case_id=? ORDER BY record_id',[case]).fetchall()]
        counts={str(identifier):used for identifier,used in controls}
        rows.extend(row('dogrulamalar','DOCUMENT_VERSION',version,counts.get(version,0),verification.MAX_CONTROLS) for version in versions)
        observations=db.execute('SELECT parent_control_id,count(*) FROM dogrulamalar WHERE case_id=? AND parent_control_id IS NOT NULL GROUP BY parent_control_id',[case]).fetchall()
        rows.extend(row('review_observations','RENDER_CONTROL',str(identifier),used,verification.MAX_OBSERVATIONS) for identifier,used in observations)
    result={'schema_version':'capacity-1.0','case_id':case,'context_version':revision,'resources':rows,
            'retention_action':'NONE','source_mutation':False,'limit_mutation':False,'production_ready':False,
            'authority':'NOT_VERIFIED','business_acceptance':'NOT_GRANTED',
            'limitations':['Retained history consumes the same quotas; invalidation does not free capacity.',
                           'Current revision counts are not semantic validity, source fidelity or business approval.',
                           'Retention policy and customer load/latency acceptance are NOT_RUN.']}
    from .workflows import checked
    return checked('capacity_result',result)
