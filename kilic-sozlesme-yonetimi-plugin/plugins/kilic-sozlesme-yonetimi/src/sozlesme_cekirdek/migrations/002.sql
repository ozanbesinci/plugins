-- Append-only scoped controls. No change to migration 001 or its record types.
CREATE TABLE dogrulamalar (
 case_id UUID NOT NULL, record_id UUID NOT NULL, document_version_id UUID NOT NULL,
 reading_id UUID NOT NULL, parent_control_id UUID, request_digest VARCHAR NOT NULL,
 method VARCHAR NOT NULL CHECK(method IN ('EXTRACTED_TEXT_MATCH','PDF_PAGE_RENDER','LOCAL_VISUAL_OBSERVATION')),
 outcome VARCHAR NOT NULL CHECK(outcome IN ('PASS','FAIL','PARTIAL','NOT_RUN')),
 payload JSON NOT NULL, checked_at TIMESTAMPTZ NOT NULL,
 artifact BLOB, artifact_sha256 VARCHAR,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,document_version_id,request_digest),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,document_version_id) REFERENCES belge_surumu(case_id,record_id),
 FOREIGN KEY(case_id,reading_id) REFERENCES isleme_calismalari(case_id,record_id),
 FOREIGN KEY(case_id,parent_control_id) REFERENCES kayitlar(case_id,record_id),
 CHECK(regexp_full_match(request_digest,'[0-9a-f]{64}')),
 CHECK((method='PDF_PAGE_RENDER' AND artifact IS NOT NULL AND regexp_full_match(artifact_sha256,'[0-9a-f]{64}'))
       OR (method<>'PDF_PAGE_RENDER' AND artifact IS NULL AND artifact_sha256 IS NULL)),
 CHECK((method='LOCAL_VISUAL_OBSERVATION' AND parent_control_id IS NOT NULL)
       OR (method<>'LOCAL_VISUAL_OBSERVATION' AND parent_control_id IS NULL))
);
