-- P4 test-scoped action lifecycle. Corporate/production authority is not implied.
CREATE TABLE islemler (
 case_id UUID NOT NULL, record_id UUID NOT NULL, request_digest VARCHAR NOT NULL,
 payload JSON NOT NULL, state VARCHAR NOT NULL,
 artifact_sha256 VARCHAR, quarantine_key VARCHAR, output_key VARCHAR, provider_ref VARCHAR,
 PRIMARY KEY(case_id,record_id),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 CHECK(regexp_full_match(request_digest,'[0-9a-f]{64}')),
 CHECK(state IN ('AUTHORIZED','EXECUTING','QUARANTINED','QA_PASSED','SIMULATION_COMMITTED',
                 'SEND_ATTEMPTED','SIMULATED_PROVIDER_ACCEPTED','FAILED','OUTCOME_UNKNOWN','RECONCILE_REQUIRED'))
);
CREATE TABLE islem_izinleri (
 case_id UUID NOT NULL, record_id UUID NOT NULL, operation_id UUID NOT NULL,
 fingerprint VARCHAR NOT NULL, state VARCHAR NOT NULL,
 payload JSON NOT NULL, signature VARCHAR NOT NULL,
 PRIMARY KEY(case_id,record_id),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,operation_id) REFERENCES islemler(case_id,record_id),
 CHECK(state IN ('ISSUED','CONSUMED','REVOKED')),
 CHECK(regexp_full_match(fingerprint,'[0-9a-f]{64}')),
 CHECK(regexp_full_match(signature,'[0-9a-f]{64}'))
);
CREATE TABLE eylem_kararlari (
 case_id UUID NOT NULL, record_id UUID NOT NULL, operation_id UUID NOT NULL,
 stage VARCHAR NOT NULL, outcome VARCHAR NOT NULL, payload JSON NOT NULL,
 PRIMARY KEY(case_id,record_id),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 CHECK(stage IN ('PRE_ACTION','POST_ACTION','COMPLETION')),
 CHECK(outcome IN ('ALLOW','REQUIRE_CONFIRMATION','ESCALATE','BLOCK'))
);
