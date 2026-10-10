-- Registered context graph; classifications and relations remain unverified.
CREATE TABLE icerik_birimleri (
 case_id UUID NOT NULL, record_id UUID NOT NULL, node_kind VARCHAR NOT NULL,
 node_digest VARCHAR NOT NULL, payload JSON NOT NULL,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,node_digest),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 CHECK(node_kind IN ('SOURCE_UNIT','USER_STATEMENT','CANDIDATE','CONTROL')),
 CHECK(regexp_full_match(node_digest,'[0-9a-f]{64}'))
);
CREATE TABLE iliskiler (
 case_id UUID NOT NULL, record_id UUID NOT NULL, from_id UUID NOT NULL, to_id UUID,
 relation VARCHAR NOT NULL, unresolved_reference VARCHAR, relation_digest VARCHAR NOT NULL,
 payload JSON NOT NULL,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,relation_digest),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,from_id) REFERENCES icerik_birimleri(case_id,record_id),
 FOREIGN KEY(case_id,to_id) REFERENCES icerik_birimleri(case_id,record_id),
 CHECK(relation IN ('DEFINITION','EXCEPTION','ANNEX','CROSS_REFERENCE','EVIDENCE','RELATED')),
 CHECK((to_id IS NOT NULL AND unresolved_reference IS NULL) OR
       (to_id IS NULL AND length(unresolved_reference)>0)),
 CHECK(regexp_full_match(relation_digest,'[0-9a-f]{64}'))
);
CREATE TABLE baglam_paketleri (
 case_id UUID NOT NULL, record_id UUID NOT NULL, semantic_version BIGINT NOT NULL,
 cache_digest VARCHAR NOT NULL, payload_digest VARCHAR NOT NULL, payload JSON NOT NULL,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,cache_digest),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 CHECK(regexp_full_match(cache_digest,'[0-9a-f]{64}')),
 CHECK(regexp_full_match(payload_digest,'[0-9a-f]{64}'))
);
