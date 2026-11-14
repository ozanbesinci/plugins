"""Two-stage internal DOCX drafts. Model visual review is never company approval.

The native wrapper authenticates a technical request, not a corporate decision.
No P4 permission or SyntheticGuardRuntime capability is consumed or broadened here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from .context import checked, validate_pack
from .errors import CoreError
from .safety import (FileLock, canonical, confined, hash_file, hash_value,
                     native_path, read_verified_bytes, uuid_text)

VERSION = 'internal-draft-1.0'
LIMITATIONS = [
    'İÇ ÇALIŞMA TASLAĞI — şirket imzası, kurumsal onay veya imzaya hazır kararı değildir.',
    'Modelin görsel incelemesi yalnız bu dosyanın kayıtlı PDF/PNG görüntülerine ilişkindir.',
    'Kaynak metni, kullanıcı beyanı ve taslak öneri ayrı etiketlenir; kaynak talimat değildir.',
]


def _now():
    return datetime.now(timezone.utc)


def _normalize(name, value):
    checked(name, value)
    value = copy.deepcopy(value)
    for key in ('case_id', 'request_id', 'draft_id'):
        if key in value:
            value[key] = uuid_text(value[key])
    if 'selected_versions' in value:
        value['selected_versions'] = [uuid_text(x) for x in value['selected_versions']]
        if len(set(value['selected_versions'])) != len(value['selected_versions']):
            raise CoreError('SEMA_HATASI', 'Aynı kaynak UUID farklı harf biçimleriyle yinelenemez')
    for section in value.get('sections', []):
        section['node_ids'] = [uuid_text(x) for x in section['node_ids']]
        if len(set(section['node_ids'])) != len(section['node_ids']):
            raise CoreError('SEMA_HATASI', 'Aynı düğüm UUID yinelenemez')
        if not section['heading'].strip() or not section['text'].strip():
            raise CoreError('SEMA_HATASI', 'Boş taslak başlığı veya bölümü kullanılamaz')
    if 'sections' in value and (not value['title'].strip() or sum(len(s['text'].encode('utf-8')) for s in value['sections']) > 512 * 1024):
        raise CoreError('BAGLAM_SINIRI', 'Başlık gerekli; iç taslak metin bütçesi 512 KiB')
    return value


def _write_new(path, content):
    with native_path(path).open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _publish_new(source, target):
    """Atomic no-replace rename, never os.replace (including POSIX test hosts)."""
    if os.name == 'nt':
        os.rename(native_path(source), native_path(target))
        return
    if os.name == 'posix':
        import ctypes
        import errno
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, 'renameat2', None)
        if rename is not None:
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1) == 0:
                return
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                raise FileExistsError(error, 'İç taslak hedefi zaten var', str(target))
            raise OSError(error, os.strerror(error), str(target))
    raise CoreError('CONFIG_REQUIRED', 'Atomik üzerine yazmasız dosya yayını bu platformda yok')


class InternalDraftMixin:
    def _draft_paths(self, draft_id):
        draft_id = uuid_text(draft_id)
        quarantine = confined(self.system / 'ic-taslak-karantina' / draft_id, [self.root])
        final = confined(self.root / 'ic-taslaklar' / (draft_id + '.docx'), [self.root])
        lock = confined(self.system / 'ic-taslak-kilitleri' / (draft_id + '.lock'), [self.root])
        native_path(lock.parent).mkdir(parents=True, exist_ok=True)
        return quarantine, final, lock

    @staticmethod
    def _draft_row(db, case_id, draft_id):
        # Timestamp conversion would add an undeclared pytz runtime dependency.
        cursor = db.execute('SELECT draft_id,case_id,request_id,context_version,request_digest,state,request,evaluation,source_fingerprint,binding,manifest,manifest_sha256,review,review_digest,error_code FROM ic_taslaklar WHERE case_id=? AND draft_id=?', [case_id, draft_id])
        item = cursor.fetchone()
        if item is None:
            raise CoreError('KAYNAK_KAPSAMI', 'İç taslak bu case içinde değil')
        row = dict(zip([x[0] for x in cursor.description], item))
        for key in ('draft_id', 'case_id', 'request_id'):
            row[key] = str(row[key])
        for key in ('request', 'evaluation', 'binding', 'manifest', 'review'):
            row[key] = json.loads(row[key]) if row[key] is not None else None
        return row

    def _draft_result(self, row, db=None):
        _, final, _ = self._draft_paths(row['draft_id'])
        if row['state'] == 'PUBLISHED':
            # Historical publication is not proof that today's delivery bytes survived.
            self._draft_artifacts(row)
            if db is None:
                with self._db() as current_db:
                    self._draft_current(current_db, row)
            else:
                self._draft_current(db, row)
        result = {key: row[key] for key in ('draft_id', 'case_id', 'request_id', 'context_version',
                                           'state', 'request_digest', 'manifest_sha256', 'manifest', 'error_code')}
        result.update(schema_version=VERSION, mode='INTERNAL_DRAFT',
                      final_path=str(final) if row['state'] == 'PUBLISHED' else None,
                      review_scope='MODEL_VISUAL_REVIEW_ONLY', authority='NOT_VERIFIED',
                      business_acceptance='NOT_GRANTED', critical_analysis_allowed=False, source_mutation='NONE')
        return checked('internal_draft_result', result)

    def _draft_evidence(self, db, request, evaluation):
        case = request['case_id']
        self._case(db, case, request['context_version'])
        if (uuid_text(evaluation.get('case_id')) != case or
                uuid_text(evaluation.get('request_id')) != request['request_id'] or
                evaluation.get('context_version') != request['context_version'] or
                evaluation.get('skill_id') != 'K28' or
                evaluation.get('authority') != 'NOT_VERIFIED' or evaluation.get('critical_analysis_allowed') is not False):
            raise CoreError('BAGLAM_BOZUK', 'İç taslak güncel K28 taslak değerlendirmesine bağlı olmalı')
        source_free = (not request['selected_versions'] and evaluation.get('context_pack_id') is None
                       and evaluation.get('findings') == [] and not request['partial_review']
                       and evaluation.get('partial_review') is None
                       and all(s['kind'] == 'DRAFT_TEXT' and not s['node_ids'] for s in request['sections']))
        if source_free and evaluation.get('status') in {'KISMI', 'BILGI_GEREKLI'}:
            return {'source_versions': [], 'node_bindings': [], 'context_pack_id': None,
                    'context_pack_digest': None, 'partial_review': None, 'source_free': True}
        if evaluation.get('status') != 'KISMI':
            raise CoreError('BAGLAM_BOZUK', 'Eksik seçilmiş bağlamdan taslak oluşturulamaz')
        sources = []
        for version in request['selected_versions']:
            _, sha, document, reasons = self._context_version(db, case, version, request['policy_version'])
            if reasons:
                raise CoreError('YENIDEN_INCELE', 'Taslak kaynağı güncel değil: ' + ', '.join(reasons))
            sources.append({'version_id': version, 'document_id': document, 'sha256': sha})
        pack_id = uuid_text(evaluation.get('context_pack_id'))
        saved = db.execute('SELECT payload_digest,payload FROM baglam_paketleri WHERE case_id=? AND record_id=?', [case, pack_id]).fetchone()
        if saved is None:
            raise CoreError('KAYNAK_KAPSAMI', 'İç taslak kayıtlı bağlam paketi gerektirir')
        pack = validate_pack(json.loads(saved[1]))
        if hash_value(pack) != saved[0] or pack['semantic_version'] != request['context_version']:
            raise CoreError('BAGLAM_BOZUK', 'İç taslak bağlam paketi hash/sürümü farklı')
        available = pack['context'] or pack.get('partial_context')
        if available is None:
            raise CoreError('BAGLAM_BOZUK', 'Eksik veya bütçeyi aşan bağlamdan iç taslak üretilmez')
        partial = None
        if pack.get('partial_context') is not None:
            if not request['partial_review']:
                raise CoreError('BAGLAM_BOZUK', 'Kısmi bağlam açık kısmi inceleme isteği gerektirir')
            partial = {'scope': 'AVAILABLE_REGISTERED_EVIDENCE_ONLY', 'registered_closure_complete': False,
                       'missing_dependencies': pack['missing_dependencies']}
        if evaluation.get('partial_review') != partial:
            raise CoreError('BAGLAM_BOZUK', 'Eksik kaynak sınırı değerlendirmeyle aynı değil')
        nodes, findings, bindings = {}, [], []
        allowed = set(request['selected_versions'])
        for entry in available['entries']:
            node = self._context_node(db, case, uuid_text(entry['node_id']), request['policy_version'])
            if node != entry or node['state'] != 'CURRENT_REGISTERED_SCOPE':
                raise CoreError('YENIDEN_INCELE', 'Taslak düğümü kayıtlı güncel içerikle eşleşmiyor')
            version = node['provenance'].get('version_id')
            if node['node_kind'] == 'CANDIDATE' and node['content']['candidate']['knowledge_kind'] != 'USER_STATEMENT':
                version = node['provenance']['source_id']
            if version is not None and uuid_text(version) not in allowed:
                raise CoreError('KAYNAK_KAPSAMI', 'Taslak kanıtı seçilmiş kaynaklar dışında')
            nodes[node['node_id']] = node
            findings.append({'node_id': node['node_id'], 'source_kind': node['node_kind'], 'content': node['content'],
                             'provenance': node['provenance'], 'verification_status': node['knowledge_status'], 'trust': node['trust']})
            bindings.append({'node_id': node['node_id'], 'kind': node['node_kind'], 'content_sha256': hash_value(node)})
        if not nodes or evaluation.get('findings') != findings:
            raise CoreError('BAGLAM_BOZUK', 'Taslak bulguları kayıtlı değerlendirme kapsamıyla eşleşmiyor')
        for section in request['sections']:
            if not set(section['node_ids']) <= nodes.keys():
                raise CoreError('KAYNAK_KAPSAMI', 'Taslak bölümü değerlendirme dışı düğüm kullanıyor')
            if section['kind'] in {'SOURCE_EXCERPT', 'USER_STATEMENT'}:
                if len(section['node_ids']) != 1:
                    raise CoreError('KAYNAK_ALINTISI', 'Alıntı ve beyan tek tam kaynak düğümüne bağlanmalı')
                node = nodes[section['node_ids'][0]]
                kind, field = ('SOURCE_UNIT', 'excerpt') if section['kind'] == 'SOURCE_EXCERPT' else ('USER_STATEMENT', 'statement')
                if node['node_kind'] != kind or section['text'] != node['content'].get(field):
                    raise CoreError('KAYNAK_ALINTISI', 'Alıntı/beyan metni tam bağlı kaynak metniyle eşleşmiyor')
        return {'source_versions': sources, 'node_bindings': bindings, 'context_pack_id': pack_id,
                'context_pack_digest': saved[0], 'partial_review': partial, 'source_free': False}

    def _draft_current(self, db, row):
        binding = self._draft_evidence(db, row['request'], row['evaluation'])
        if binding != row['binding'] or hash_value(binding) != row['source_fingerprint']:
            raise CoreError('YENIDEN_INCELE', 'İç taslak kanıt bağları değişti')

    def _draft_artifacts(self, row):
        quarantine, final, _ = self._draft_paths(row['draft_id'])
        manifest = checked('internal_draft_manifest', row['manifest'])
        if hash_value(manifest) != row['manifest_sha256']:
            raise CoreError('KAYNAK_BOZUK', 'İç taslak manifest hash farklı')
        if (manifest['draft_id'] != row['draft_id'] or manifest['case_id'] != row['case_id'] or
                manifest['context_version'] != row['context_version'] or
                manifest['request_digest'] != row['request_digest'] or
                manifest['source_fingerprint'] != row['source_fingerprint']):
            raise CoreError('KAYNAK_BOZUK', 'İç taslak manifest kimlik bağı farklı')
        manifest_path = confined(quarantine / 'manifest.json', [quarantine])
        if hash_file(manifest_path) != row['manifest_sha256']:
            raise CoreError('KAYNAK_BOZUK', 'Kalıcı manifest dosyası değişmiş')
        stage = confined(quarantine / 'draft.docx', [quarantine])
        if manifest['docx']['path'] != str(stage):
            raise CoreError('ERISIM_YOK', 'Taslak DOCX yolu kayıtlı karantina yolu değil')
        document = final if row['state'] in {'PUBLISHING', 'PUBLISHED'} and native_path(final).exists() else stage
        if hash_file(document) != manifest['docx']['sha256']:
            raise CoreError('KAYNAK_BOZUK', 'Taslak DOCX hash farklı')
        if native_path(final).exists() and native_path(stage).exists():
            raise CoreError('HEDEF_VAR', 'Karantina ve son çıktı aynı anda var; otomatik üzerine yazılmaz')
        paths = []
        for artifact in [manifest['pdf'], *manifest['pages']]:
            path = confined(artifact['path'], [quarantine / 'qa'])
            if hash_file(path) != artifact['sha256']:
                raise CoreError('KAYNAK_BOZUK', 'PDF/PNG inceleme dosyası değişmiş')
            paths.append(str(path).casefold())
        if len(paths) != len(set(paths)) or [p['page'] for p in manifest['pages']] != list(range(1, len(manifest['pages']) + 1)):
            raise CoreError('KAYNAK_BOZUK', 'İnceleme sayfaları sıralı/tam/benzersiz değil')
        rendered = {key: manifest[key] for key in ('renderer', 'pdf', 'pages')}
        if hash_value(rendered) != manifest['render_sha256']:
            raise CoreError('KAYNAK_BOZUK', 'Render zinciri hash farklı')
        return stage, final

    def _draft_quarantine(self, case, draft, code):
        with self._db() as db:
            row = self._draft_row(db, case, draft)
            # A final file left by a failed commit is returned to our quarantine only
            # when its bytes are bound to this draft. Unrelated existing files stay put.
            quarantine, final, _ = self._draft_paths(draft)
            stage = confined(quarantine / 'draft.docx', [self.root])
            if (row['state'] == 'PUBLISHING' and row['manifest'] is not None and
                    native_path(final).exists() and not native_path(stage).exists() and
                    hash_file(final) == row['manifest']['docx']['sha256']):
                _publish_new(final, stage)
            db.execute("UPDATE ic_taslaklar SET state='QUARANTINED',error_code=?,updated_at=? WHERE case_id=? AND draft_id=? AND state NOT IN ('PUBLISHED','REJECTED')", [code, _now(), case, draft])

    def prepare_internal_draft(self, request, evaluation):
        request = _normalize('internal_draft_request', request)
        digest, case = hash_value(request), request['case_id']
        draft = str(uuid4())
        quarantine, _, lock = self._draft_paths(draft)
        with FileLock(lock, self.lock_timeout):
            with self._db() as db:
                prior = db.execute('SELECT request_kind,request_digest,draft_id FROM ic_taslak_istekleri WHERE case_id=? AND request_id=?', [case, request['request_id']]).fetchone()
                if prior:
                    if prior[:2] != ('PREPARE', digest):
                        raise CoreError('GECERSIZ_GIRDI', 'İstek kimliği başka bir iç taslak isteğine bağlı')
                    return self._draft_result(self._draft_row(db, case, str(prior[2])), db)
                binding = self._draft_evidence(db, request, evaluation)
                fingerprint = hash_value(binding)
                db.execute('INSERT INTO ic_taslaklar VALUES(?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,?,?)',
                           [draft, case, request['request_id'], request['context_version'], digest, 'PREPARING',
                            canonical(request), canonical(evaluation), fingerprint, canonical(binding), _now(), _now()])
                db.execute("INSERT INTO ic_taslak_istekleri VALUES(?,?,?,'PREPARE',?)", [case, request['request_id'], draft, digest])
                self._event(db, case, 'INTERNAL_DRAFT_PREPARING', {'draft_id': draft, 'request_digest': digest, 'business_acceptance': 'NOT_GRANTED'})
            try:
                # No database transaction is held while Word runs.
                from .draft_document import build_docx, structural_qa, render_docx
                native_path(quarantine).mkdir(parents=True, exist_ok=False)
                stage = confined(quarantine / 'draft.docx', [self.root])
                qa_dir = confined(quarantine / 'qa', [self.root])
                native_path(qa_dir).mkdir(exist_ok=False)
                limitations = list(LIMITATIONS)
                if binding['source_free']:
                    limitations += ['Kaynak seçilmedi; tüm içerik taslak öneridir. Belge alıntısı veya doğrulanmış beyan içermez.']
                if binding['partial_review'] is not None:
                    limitations += ['KISMİ İNCELEME: eksik ek/kaynakların içeriği değerlendirilmedi.']
                provenance = dict(binding, draft_id=draft, case_id=case, context_version=request['context_version'],
                                  request_digest=digest, source_fingerprint=fingerprint, limitations=limitations)
                docx = build_docx(request['title'], request['sections'], provenance)
                if not isinstance(docx, bytes) or not 0 < len(docx) <= 32 * 1024 * 1024:
                    raise CoreError('RENDER_HATASI', 'İç taslak DOCX boyutu/biçimi uygun değil')
                qa = structural_qa(docx)
                if not isinstance(qa, dict) or qa.get('passed') is not True:
                    raise CoreError('RENDER_HATASI', 'İç taslak yapısal kontrolü geçmedi')
                _write_new(stage, docx)
                rendered = render_docx(stage, qa_dir)
                manifest = {'draft_id': draft, 'case_id': case, 'context_version': request['context_version'],
                            'request_digest': digest, 'source_fingerprint': fingerprint,
                            'docx': {'path': str(stage), 'sha256': hashlib.sha256(docx).hexdigest()},
                            'structural_qa': qa, **rendered, 'render_sha256': hash_value(rendered)}
                checked('internal_draft_manifest', manifest)
                # Normalize path checks and verify actual output bytes before binding them.
                if not read_verified_bytes(confined(manifest['pdf']['path'], [qa_dir])).startswith(b'%PDF-'):
                    raise CoreError('RENDER_HATASI', 'Render PDF biçimi farklı')
                for page in manifest['pages']:
                    if not read_verified_bytes(confined(page['path'], [qa_dir])).startswith(b'\x89PNG\r\n\x1a\n'):
                        raise CoreError('RENDER_HATASI', 'Render PNG biçimi farklı')
                manifest_hash = hash_value(manifest)
                _write_new(confined(quarantine / 'manifest.json', [self.root]), canonical(manifest).encode('utf-8'))
                with self._db() as db:
                    row = self._draft_row(db, case, draft)
                    row.update(manifest=manifest, manifest_sha256=manifest_hash)
                    self._draft_current(db, row)
                    self._draft_artifacts(row)
                    if row['state'] != 'PREPARING':
                        raise CoreError('SURUM_CAKISMASI', 'İç taslak hazırlanırken kayıt değişti')
                    db.execute("UPDATE ic_taslaklar SET state='REVIEW_PENDING',manifest=?,manifest_sha256=?,updated_at=? WHERE draft_id=? AND state='PREPARING'", [canonical(manifest), manifest_hash, _now(), draft])
                    self._event(db, case, 'INTERNAL_DRAFT_REVIEW_PENDING', {'draft_id': draft, 'manifest_sha256': manifest_hash})
                    return self._draft_result(self._draft_row(db, case, draft), db)
            except BaseException as exc:
                self._draft_quarantine(case, draft, exc.code if isinstance(exc, CoreError) else 'TEKNIK_HATA')
                raise

    def review_internal_draft(self, review):
        review = _normalize('internal_draft_review', review)
        if not review['observation'].strip():
            raise CoreError('SEMA_HATASI', 'Görsel inceleme gözlemi boş olamaz')
        case, draft, digest = review['case_id'], review['draft_id'], hash_value(review)
        _, _, lock = self._draft_paths(draft)
        with FileLock(lock, self.lock_timeout):
            with self._db() as db:
                row = self._draft_row(db, case, draft)
                prior = db.execute('SELECT request_kind,request_digest,draft_id FROM ic_taslak_istekleri WHERE case_id=? AND request_id=?', [case, review['request_id']]).fetchone()
                if prior:
                    if prior[0] != 'REVIEW' or prior[1] != digest or str(prior[2]) != draft:
                        raise CoreError('GECERSIZ_GIRDI', 'İstek kimliği farklı inceleme içeriğine bağlı')
                    return self._draft_result(row, db)
                if row['state'] != 'REVIEW_PENDING':
                    raise CoreError('GECERSIZ_DURUM', 'İç taslak görsel inceleme beklemiyor; durum/uzlaştırma gerekli')
                if review['context_version'] != row['context_version'] or review['manifest_sha256'] != row['manifest_sha256']:
                    raise CoreError('SURUM_CAKISMASI', 'İnceleme güncel taslak sürümü/manifestine bağlı değil')
                self._draft_current(db, row)
                self._draft_artifacts(row)
                pages = [{'page': p['page'], 'sha256': p['sha256']} for p in row['manifest']['pages']]
                if review['reviewed_pages'] != pages:
                    raise CoreError('RENDER_HATASI', 'Görsel inceleme tüm kayıtlı sayfaları sıralı ve aynı hash ile kapsamalı')
                state = 'PUBLISHING' if review['decision'] == 'ACCEPT' else 'REJECTED'
                db.execute('UPDATE ic_taslaklar SET state=?,review=?,review_digest=?,updated_at=? WHERE draft_id=? AND state=\'REVIEW_PENDING\'', [state, canonical(review), digest, _now(), draft])
                db.execute("INSERT INTO ic_taslak_istekleri VALUES(?,?,?,'REVIEW',?)", [case, review['request_id'], draft, digest])
                self._event(db, case, 'INTERNAL_DRAFT_MODEL_REVIEW', {'draft_id': draft, 'decision': review['decision'], 'manifest_sha256': row['manifest_sha256'], 'review_scope': 'MODEL_VISUAL_REVIEW_ONLY', 'business_acceptance': 'NOT_GRANTED'})
                if state == 'REJECTED':
                    return self._draft_result(self._draft_row(db, case, draft), db)
            # PUBLISHING is durable before touching the final path; a crash is reconciled.
            return self._finish_internal_draft(case, draft)

    def _finish_internal_draft(self, case, draft):
        # Caller holds per-draft lock. Transaction serializes the final source/CAS check.
        with self._db() as db:
            row = self._draft_row(db, case, draft)
            if row['state'] != 'PUBLISHING' or row['review'] is None or row['review']['decision'] != 'ACCEPT':
                raise CoreError('GECERSIZ_DURUM', 'Kalıcı kabul edilmiş iç taslak yayını bulunamadı')
            if hash_value(row['review']) != row['review_digest'] or row['review']['manifest_sha256'] != row['manifest_sha256']:
                raise CoreError('KAYNAK_BOZUK', 'İç taslak görsel inceleme bağı değişmiş')
            review = _normalize('internal_draft_review', row['review'])
            if (review['draft_id'] != draft or review['case_id'] != case or
                    review['context_version'] != row['context_version'] or
                    review['reviewed_pages'] != [{'page': p['page'], 'sha256': p['sha256']} for p in row['manifest']['pages']]):
                raise CoreError('KAYNAK_BOZUK', 'Kalıcı inceleme tam sayfa/case bağı farklı')
            self._draft_current(db, row)
            stage, final = self._draft_artifacts(row)
            if not native_path(final).exists():
                native_path(final.parent).mkdir(parents=True, exist_ok=True)
                confined(stage, [self.root]); confined(final, [self.root])
                _publish_new(stage, final)
            # If rename succeeded but commit failed, durable PUBLISHING retries this check.
            if hash_file(final) != row['manifest']['docx']['sha256']:
                raise CoreError('KAYNAK_BOZUK', 'Yayımlanan taslak hash farklı')
            self._draft_current(db, row)
            db.execute("UPDATE ic_taslaklar SET state='PUBLISHED',updated_at=? WHERE draft_id=? AND state='PUBLISHING'", [_now(), draft])
            self._event(db, case, 'INTERNAL_DRAFT_PUBLISHED', {'draft_id': draft, 'manifest_sha256': row['manifest_sha256'], 'business_acceptance': 'NOT_GRANTED'})
            return self._draft_result(self._draft_row(db, case, draft), db)

    def internal_draft_status(self, case_id, draft_id):
        case, draft = uuid_text(case_id), uuid_text(draft_id)
        with self._db() as db:
            return self._draft_result(self._draft_row(db, case, draft), db)

    def reconcile_internal_drafts(self, case_id=None):
        case_id = uuid_text(case_id) if case_id is not None else None
        with self._db() as db:
            # Terminal history may legitimately describe an older case revision.
            # It must not prevent another interrupted draft from being recovered.
            rows = db.execute("SELECT case_id,draft_id FROM ic_taslaklar WHERE state IN ('PREPARING','REVIEW_PENDING','PUBLISHING')" + (' AND case_id=?' if case_id else '') + ' ORDER BY created_at', [case_id] if case_id else []).fetchall()
        results = []
        for case, draft in rows:
            case, draft = str(case), str(draft)
            _, _, lock = self._draft_paths(draft)
            with FileLock(lock, self.lock_timeout):
                with self._db() as db:
                    row = self._draft_row(db, case, draft)
                if row['state'] == 'PUBLISHING':
                    try:
                        results.append(self._finish_internal_draft(case, draft))
                    except CoreError as exc:
                        self._draft_quarantine(case, draft, exc.code)
                        results.append(self.internal_draft_status(case, draft))
                elif row['state'] == 'PREPARING':
                    # No blind regeneration or implied successful review after interruption.
                    self._draft_quarantine(case, draft, 'HAZIRLAMA_KESILDI')
                    results.append(self.internal_draft_status(case, draft))
                elif row['state'] == 'REVIEW_PENDING':
                    try:
                        with self._db() as db:
                            self._draft_current(db, row)
                            self._draft_artifacts(row)
                    except CoreError as exc:
                        self._draft_quarantine(case, draft, exc.code)
                    results.append(self.internal_draft_status(case, draft))
                else:
                    results.append(self._draft_result(row))
        return results
