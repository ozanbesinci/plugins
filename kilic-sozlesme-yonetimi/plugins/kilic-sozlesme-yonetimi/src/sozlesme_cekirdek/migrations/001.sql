CREATE TABLE sema_gecmisi (
 migration_no BIGINT PRIMARY KEY, schema_version VARCHAR NOT NULL,
 change_digest VARCHAR NOT NULL, applied_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE dosyalar (
 case_id UUID PRIMARY KEY, baslik VARCHAR NOT NULL,
 semantic_version BIGINT NOT NULL DEFAULT 0 CHECK (semantic_version >= 0),
 asama VARCHAR NOT NULL DEFAULT 'NEW' CHECK (asama IN ('NEW','ACTIVE','CLOSED')),
 created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE kayitlar (
 case_id UUID NOT NULL REFERENCES dosyalar(case_id), record_id UUID NOT NULL,
 record_type VARCHAR NOT NULL CHECK (record_type IN ('DOCUMENT','VERSION','STATEMENT','CANDIDATE','PROCESSING','EVENT','INVALIDATION')),
 recorded_at TIMESTAMPTZ NOT NULL, supersedes_id UUID,
 PRIMARY KEY (case_id,record_id),
 FOREIGN KEY (case_id,supersedes_id) REFERENCES kayitlar(case_id,record_id)
);
CREATE TABLE belgeler (
 case_id UUID NOT NULL, record_id UUID NOT NULL, title VARCHAR NOT NULL, document_type VARCHAR NOT NULL,
 PRIMARY KEY (case_id,record_id), FOREIGN KEY (case_id,record_id) REFERENCES kayitlar(case_id,record_id)
);
CREATE TABLE belge_surumu (
 case_id UUID NOT NULL, record_id UUID NOT NULL, document_id UUID NOT NULL,
 sha256 VARCHAR NOT NULL CHECK (regexp_full_match(sha256,'[0-9a-f]{64}')),
 size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0), media_type VARCHAR NOT NULL,
 storage_key VARCHAR NOT NULL UNIQUE, original_path VARCHAR NOT NULL, acquired_at TIMESTAMPTZ NOT NULL,
 business_status VARCHAR NOT NULL CHECK (business_status IN ('UNKNOWN','DRAFT','SUPPLIER_PROPOSAL','PURCHASING_PROPOSAL','SIGNED')),
 PRIMARY KEY (case_id,record_id), UNIQUE (case_id,document_id,sha256),
 FOREIGN KEY (case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY (case_id,document_id) REFERENCES belgeler(case_id,record_id)
);
CREATE TABLE surum_ebeveynleri (
 case_id UUID NOT NULL, child_id UUID NOT NULL, parent_id UUID NOT NULL,
 relation VARCHAR NOT NULL CHECK (relation IN ('REVISION','BRANCH','MERGE')),
 CHECK(child_id <> parent_id), PRIMARY KEY (case_id,child_id,parent_id),
 FOREIGN KEY(case_id,child_id) REFERENCES belge_surumu(case_id,record_id),
 FOREIGN KEY(case_id,parent_id) REFERENCES belge_surumu(case_id,record_id)
);
CREATE TABLE isleme_calismalari (
 case_id UUID NOT NULL, record_id UUID NOT NULL, document_version_id UUID NOT NULL,
 profile_digest VARCHAR NOT NULL, tool VARCHAR NOT NULL, tool_version VARCHAR NOT NULL,
 settings_digest VARCHAR NOT NULL, validation_version VARCHAR NOT NULL, policy_version VARCHAR NOT NULL,
 result JSON NOT NULL, status VARCHAR NOT NULL CHECK(status IN ('STRUCTURED_UNVERIFIED','PARTIAL','VERIFIED','FAILED')),
 finished_at TIMESTAMPTZ NOT NULL,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,document_version_id,profile_digest),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,document_version_id) REFERENCES belge_surumu(case_id,record_id)
);
CREATE TABLE beyanlar (
 case_id UUID NOT NULL, record_id UUID NOT NULL, excerpt VARCHAR NOT NULL,
 stated_at TIMESTAMPTZ NOT NULL, session_ref VARCHAR, message_ref VARCHAR,
 identity_status VARCHAR NOT NULL CHECK(identity_status='UNVERIFIED_LOCAL_STATEMENT'),
 PRIMARY KEY(case_id,record_id), FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id)
);
CREATE TABLE bilgiler (
 case_id UUID NOT NULL, record_id UUID NOT NULL, source_id UUID NOT NULL,
 field_code VARCHAR NOT NULL, value_type VARCHAR NOT NULL,
 value_text VARCHAR, value_decimal DECIMAL(24,6), value_rate DECIMAL(18,10), value_date DATE, value_bool BOOLEAN,
 unknown_reason VARCHAR, unit VARCHAR, currency VARCHAR,
 knowledge_kind VARCHAR NOT NULL CHECK(knowledge_kind IN ('DOCUMENT_TEXT','USER_STATEMENT','INFERENCE','PROPOSAL')),
 interpretation_status VARCHAR NOT NULL CHECK(interpretation_status IN ('CLEAR','UNCERTAIN','CONFLICTING')),
 verification_status VARCHAR NOT NULL CHECK(verification_status='UNVERIFIED'), payload JSON NOT NULL,
 PRIMARY KEY(case_id,record_id),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,source_id) REFERENCES kayitlar(case_id,record_id),
 CHECK (
  (value_type='text' AND value_text IS NOT NULL AND value_decimal IS NULL AND value_rate IS NULL AND value_date IS NULL AND value_bool IS NULL AND unknown_reason IS NULL) OR
  (value_type='decimal' AND value_text IS NULL AND ((value_decimal IS NOT NULL AND value_rate IS NULL) OR (value_decimal IS NULL AND value_rate IS NOT NULL)) AND value_date IS NULL AND value_bool IS NULL AND unknown_reason IS NULL) OR
  (value_type='date' AND value_text IS NULL AND value_decimal IS NULL AND value_rate IS NULL AND value_date IS NOT NULL AND value_bool IS NULL AND unknown_reason IS NULL) OR
  (value_type='boolean' AND value_text IS NULL AND value_decimal IS NULL AND value_rate IS NULL AND value_date IS NULL AND value_bool IS NOT NULL AND unknown_reason IS NULL) OR
  (value_type='unknown' AND value_text IS NULL AND value_decimal IS NULL AND value_rate IS NULL AND value_date IS NULL AND value_bool IS NULL AND length(unknown_reason)>0)
 )
);
CREATE TABLE kanit_baglari (
 case_id UUID NOT NULL, target_id UUID NOT NULL, source_id UUID NOT NULL,
 relation VARCHAR NOT NULL CHECK(relation IN ('SUPPORTS','CONTRADICTS','SUPERSEDES')),
 source_locator JSON NOT NULL, PRIMARY KEY(case_id,target_id,source_id,relation),
 FOREIGN KEY(case_id,target_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,source_id) REFERENCES kayitlar(case_id,record_id)
);
CREATE TABLE gecersizlestirmeler (
 case_id UUID NOT NULL, record_id UUID NOT NULL, target_id UUID NOT NULL, cause_id UUID NOT NULL,
 reason VARCHAR NOT NULL, detected_at TIMESTAMPTZ NOT NULL, state VARCHAR NOT NULL CHECK(state='NEEDS_REVIEW'),
 PRIMARY KEY(case_id,record_id), FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,target_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,cause_id) REFERENCES kayitlar(case_id,record_id)
);
CREATE TABLE islem_olaylari (
 case_id UUID NOT NULL, record_id UUID NOT NULL, event VARCHAR NOT NULL,
 occurred_at TIMESTAMPTZ NOT NULL, details JSON NOT NULL,
 PRIMARY KEY(case_id,record_id), FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id)
);
