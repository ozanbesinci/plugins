"""Explicit, one-claim synthetic recovery. No agent-facing writer or blind retry."""
import hashlib
import json
import os
from .errors import CoreError
from .runtime_identity import component_identity
from .safety import atomic_json,canonical,confined,hash_file,hash_value,native_path,read_verified_bytes,uuid_text


def recover_document(runtime,spec):
    from .guard import checked,TestQA,MAX_ARTIFACT
    store=runtime.store
    hint={'plan':{'case_id':spec.get('case_id') if isinstance(spec,dict) else None,
                  'operation_id':spec.get('operation_id') if isinstance(spec,dict) else None}}
    claimed=False
    try:
        runtime._identity() # Includes TEST_ROOT confinement before any artefact read.
        spec=checked('p4_recovery_request',spec)
        build_digest=component_identity()['source_digest']
        case,operation,permission,recovery_id=map(uuid_text,(spec['case_id'],spec['operation_id'],spec['permission_id'],spec['recovery_id']))
        capsule_path=confined(store.system/'eylem-karantina'/operation/'capsule.json',[store.root])
        quarantine=confined(capsule_path.with_name('artifact.bin'),[store.root])
        claims=confined(store.system/'recovery',[store.root])
        claim_path=confined(claims/(operation+'.claim.json'),[store.root])
        final_path=confined(claims/(operation+'.final.json'),[store.root])

        def bindings(db):
            store._case(db,case,spec['context_version'])
            row,previous=runtime._operation(db,case,operation)
            request=previous['request']
            if row[2] not in {'QUARANTINED','QA_PASSED','RECONCILE_REQUIRED'}:
                raise CoreError('RECOVERY_STATE','Tamamlanmış/başarısız/kanıtsız işlem yeniden yürütülemez')
            if row[3]!=spec['artifact_sha256'] or row[4]!='eylem-karantina/'+operation+'/artifact.bin' or hash_value(request)!=spec['request_digest']:
                raise CoreError('RECOVERY_BINDING','Recovery istek/artefakt/karantina bağı farklı')
            permit=runtime._permission(db,case,permission)
            if permit['operation_id']!=operation or permit['state']!='CONSUMED':
                raise CoreError('IZIN_BOZUK','Recovery aynı işlemde tüketilmiş tek izin gerektirir')
            _,sources,target=runtime._fresh(db,request,previous,allow_published_target=True)
            registered=[json.loads(value[0]) for value in db.execute("SELECT details FROM islem_olaylari WHERE case_id=? AND event='ARTIFACT_RECOVERY_CAPSULE_REGISTERED'",[case]).fetchall()]
            registered=[value for value in registered if value.get('operation_id')==operation]
            if len(registered)!=1:
                raise CoreError('RECOVERY_EVIDENCE_REQUIRED','Tek kalıcı capsule bağı yok; metadata tahmin edilmedi')
            evidence=registered[0]
            if (evidence['request_digest']!=spec['request_digest'] or evidence['artifact_sha256']!=spec['artifact_sha256']
                    or evidence['backend_version']!=runtime.backend.version or evidence.get('build_digest')!=build_digest
                    or evidence['capsule_sha256']!=hash_file(capsule_path)):
                raise CoreError('RECOVERY_BINDING','Capsule audit/hash/backend bağı farklı')
            return row,request,sources,target,evidence

        with store._db() as db:
            row,request,sources,target,evidence=bindings(db)
            hint=request
            if native_path(claim_path).exists() or native_path(final_path).exists():
                raise CoreError('RECOVERY_ALREADY_CLAIMED','Recovery claim tüketildi; otomatik ikinci onarım yok')
        capsule=checked('p4_recovery_capsule',json.loads(read_verified_bytes(capsule_path,1024*1024).decode('utf-8')))
        if (capsule['case_id']!=case or capsule['operation_id']!=operation or capsule['request_digest']!=spec['request_digest']
                or capsule['artifact_sha256']!=spec['artifact_sha256'] or capsule['backend_version']!=runtime.backend.version
                or capsule['build_digest']!=build_digest):
            raise CoreError('RECOVERY_BINDING','Capsule alanları recovery kapsamıyla eşleşmiyor')
        data=read_verified_bytes(quarantine,MAX_ARTIFACT)
        if hashlib.sha256(data).hexdigest()!=spec['artifact_sha256']:
            raise CoreError('QA_FAILED','Recovery karantina baytları değişmiş')
        restorer=getattr(runtime.backend,'restore_recovery_payload',None)
        if capsule['backend_payload'] is not None:
            if restorer is None:raise CoreError('RECOVERY_BACKEND_REQUIRED','Capsule backend restore adaptörü yok')
            restorer(request,sources,data,capsule['backend_payload'])
        qa=runtime.backend.verify_document(request,data)
        if type(qa) is not TestQA or qa.passed is not True or qa.digest!=spec['artifact_sha256']:
            raise CoreError('QA_FAILED','Recovery güncel sentetik QA kanıtı geçmedi')
        ready=confined(target.with_name(target.name+'.'+operation+'.ready'),[store.root])
        with store._db() as db:
            row,request,sources,target,evidence=bindings(db)
            if hash_file(quarantine)!=spec['artifact_sha256']:
                raise CoreError('QA_FAILED','Recovery QA sonrası karantina değişti')
            existing=native_path(target).exists()
            if existing and (not native_path(target).is_file() or hash_file(target)!=spec['artifact_sha256']):
                raise CoreError('HEDEF_VAR','Yabancı/değişmiş final ezilemez')
            if native_path(ready).exists() and hash_file(ready)!=spec['artifact_sha256']:
                raise CoreError('QA_FAILED','Recovery ready baytları farklı')
            native_path(claims).mkdir(parents=True,exist_ok=True)
            claim={'schema_version':'p4-recovery-claim-1.0','recovery_id':recovery_id,'spec':spec,'status':'STARTED',
                   'capsule_sha256':evidence['capsule_sha256'],'retry_safety':'NO_BLIND_RETRY','production_ready':False}
            # A native crash preserves this consumed claim even if the DB rolls back.
            with native_path(claim_path).open('xb') as writer:
                claimed=True;writer.write(canonical(claim).encode('utf-8'));writer.flush();os.fsync(writer.fileno())
            store._event(db,case,'SYNTHETIC_RECOVERY_STARTED',{'operation_id':operation,'recovery_id':recovery_id,'spec_digest':hash_value(spec)})
        with store._db() as db:
            row,request,sources,target,evidence=bindings(db)
            if hash_file(quarantine)!=spec['artifact_sha256']:
                raise CoreError('QA_FAILED','Recovery yayın öncesi karantina değişti')
            adopted=native_path(target).exists()
            if adopted:
                if hash_file(target)!=spec['artifact_sha256']:raise CoreError('HEDEF_VAR','Recovery final hash farklı')
            else:
                if os.name!='nt':raise CoreError('PLATFORM_PUBLICATION','Yalnız Windows atomik yayın desteklenir')
                native_path(target.parent).mkdir(parents=True,exist_ok=True)
                if not native_path(ready).exists():
                    with native_path(ready).open('xb') as writer:
                        writer.write(data);writer.flush();os.fsync(writer.fileno())
                if hash_file(ready)!=spec['artifact_sha256']:raise CoreError('QA_FAILED','Recovery ready hash farklı')
                os.rename(native_path(ready),native_path(target))
            if hash_file(target)!=spec['artifact_sha256']:raise CoreError('QA_FAILED','Recovery final hash farklı')
            _,previous=runtime._operation(db,case,operation)
            runtime._fresh(db,request,previous,allow_published_target=True)
            runtime._stage(db,case,operation,{'QUARANTINED','QA_PASSED','RECONCILE_REQUIRED'},'QA_PASSED')
            persister=getattr(runtime.backend,'persist_document',None)
            if persister is not None:persister(db,store,request,data,target)
            runtime._stage(db,case,operation,{'QA_PASSED'},'SIMULATION_COMMITTED',output_key=target.relative_to(store.root).as_posix())
            store._event(db,case,'SYNTHETIC_RECOVERY_COMPLETED',{'operation_id':operation,'recovery_id':recovery_id,'artifact_sha256':spec['artifact_sha256'],'existing_final_adopted':adopted})
            proof=runtime._emit(db,request,'ALLOW',['SYNTHETIC_RECOVERY_ONLY_NOT_PRODUCTION_ACCEPTANCE'],stage='COMPLETION',enabled=True)
        result={'state':'SIMULATION_COMMITTED','recovery_id':recovery_id,'decision':proof,'existing_final_adopted':adopted,
                'backend_prepare_called':False,'output_path':str(target),'artifact_sha256':spec['artifact_sha256'],
                'production_ready':False,'business_acceptance':'NOT_GRANTED'}
        atomic_json(final_path,{'schema_version':'p4-recovery-final-1.0','recovery_id':recovery_id,'spec_digest':hash_value(spec),
                               'status':'COMPLETED','result':result,'retry_safety':'NO_BLIND_RETRY'})
        return result
    except Exception as exc:
        code=exc.code if isinstance(exc,CoreError) else 'RECOVERY_TECHNICAL_ERROR'
        return {'state':'RECONCILE_REQUIRED' if claimed else 'BLOCKED','decision':runtime._blocked(hint,code,stage='COMPLETION'),
                'delivery_confirmed':False,'recovery_claimed':claimed,'production_ready':False,'business_acceptance':'NOT_GRANTED'}
