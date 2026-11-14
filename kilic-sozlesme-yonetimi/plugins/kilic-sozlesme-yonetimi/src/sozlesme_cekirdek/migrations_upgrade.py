"""Transactional migration 7: remove content uniqueness, preserving every FK and row.

DuckDB cannot DROP a UNIQUE constraint. Rebuild from the unchanged historical DDL,
inside the Store's existing lock/transaction. Never reconstruct DDL from duckdb_tables:
its SQL representation omits self-referencing constraints.
"""
import re
from .errors import CoreError


def separate_content_from_version(db, historical_scripts):
    definitions = []
    for script in historical_scripts:
        clean = re.sub(r'(?m)^\s*--[^\n]*', '', script)
        for statement in clean.split(';'):
            statement = statement.strip()
            if not statement:
                continue
            match = re.match(r'CREATE TABLE ([a-z_]+)\s*\(', statement)
            if match is None:
                raise CoreError('SEMA_DRIFT', 'Beklenmeyen tarihsel migration ifadesi')
            if match[1] != 'sema_gecmisi':
                definitions.append((match[1], statement))
    names = {name for name, _ in definitions}
    actual = {r[0] for r in db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE'").fetchall()}
    if actual != names | {'sema_gecmisi'}:
        raise CoreError('SEMA_DRIFT', 'Migration 7 tablo kümesi beklenen tarihsel şema değil')
    for name, _ in definitions:
        db.execute(f'CREATE TEMP TABLE migration7_{name} AS SELECT * FROM {name}')
    for name, _ in reversed(definitions):
        db.execute(f'DROP TABLE {name}')
    for name, ddl in definitions:
        if name == 'belge_surumu':
            old = 'UNIQUE (case_id,document_id,sha256),'
            if ddl.count(old) != 1:
                raise CoreError('SEMA_DRIFT', 'İçerik tekillik kısıtı tanınamadı')
            ddl = ddl.replace(old, '')
        db.execute(ddl)
        if name == 'kayitlar':
            pending = db.execute('SELECT case_id,record_id,supersedes_id FROM migration7_kayitlar').fetchall()
            inserted = set()
            while pending:
                ready = [r for r in pending if r[2] is None or (r[0], r[2]) in inserted]
                if not ready:
                    raise CoreError('SEMA_DRIFT', 'Kayıt ebeveyn sırası çözülemiyor')
                for row in ready:
                    db.execute('INSERT INTO kayitlar SELECT * FROM migration7_kayitlar WHERE case_id=? AND record_id=?', row[:2])
                inserted.update((r[0], r[1]) for r in ready)
                pending = [r for r in pending if (r[0], r[1]) not in inserted]
        else:
            db.execute(f'INSERT INTO {name} SELECT * FROM migration7_{name}')
        mismatch = db.execute(f'SELECT count(*) FROM ((SELECT * FROM {name} EXCEPT ALL SELECT * FROM migration7_{name}) UNION ALL (SELECT * FROM migration7_{name} EXCEPT ALL SELECT * FROM {name}))').fetchone()[0]
        if mismatch:
            raise CoreError('SEMA_DRIFT', 'Migration sırasında veri farklılaştı: ' + name)
    for name, _ in definitions:
        db.execute(f'DROP TABLE migration7_{name}')
