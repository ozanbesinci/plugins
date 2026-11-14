-- Internal working drafts are separate from corporate authority and synthetic P5 grants.
CREATE TABLE ic_taslaklar (
 draft_id UUID PRIMARY KEY, case_id UUID NOT NULL, request_id UUID NOT NULL,
 context_version BIGINT NOT NULL, request_digest VARCHAR NOT NULL,
 state VARCHAR NOT NULL, request JSON NOT NULL, evaluation JSON NOT NULL,
 source_fingerprint VARCHAR NOT NULL, binding JSON NOT NULL,
 manifest JSON, manifest_sha256 VARCHAR, review JSON, review_digest VARCHAR,
 error_code VARCHAR, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
 UNIQUE(case_id,request_id),
 FOREIGN KEY(case_id) REFERENCES dosyalar(case_id),
 CHECK(state IN ('PREPARING','REVIEW_PENDING','PUBLISHING','PUBLISHED','REJECTED','QUARANTINED')),
 CHECK(regexp_full_match(request_digest,'[0-9a-f]{64}')),
 CHECK(regexp_full_match(source_fingerprint,'[0-9a-f]{64}')),
 CHECK(manifest_sha256 IS NULL OR regexp_full_match(manifest_sha256,'[0-9a-f]{64}')),
 CHECK(review_digest IS NULL OR regexp_full_match(review_digest,'[0-9a-f]{64}'))
);
CREATE TABLE ic_taslak_istekleri (
 case_id UUID NOT NULL, request_id UUID NOT NULL, draft_id UUID NOT NULL,
 request_kind VARCHAR NOT NULL, request_digest VARCHAR NOT NULL,
 PRIMARY KEY(case_id,request_id),
 CHECK(request_kind IN ('PREPARE','REVIEW')),
 CHECK(regexp_full_match(request_digest,'[0-9a-f]{64}'))
);
