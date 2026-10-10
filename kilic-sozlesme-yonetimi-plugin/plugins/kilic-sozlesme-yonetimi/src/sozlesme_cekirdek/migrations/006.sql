-- Source-anchored business projection; no corporate approval or verified completion.
CREATE TABLE is_bilgisi_baglari (
 case_id UUID NOT NULL, record_id UUID NOT NULL, source_node_id UUID NOT NULL,
 scope_key VARCHAR NOT NULL, plane VARCHAR NOT NULL, fact_digest VARCHAR NOT NULL,
 payload JSON NOT NULL, payload_digest VARCHAR NOT NULL,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,fact_digest),
 FOREIGN KEY(case_id,record_id) REFERENCES bilgiler(case_id,record_id),
 FOREIGN KEY(case_id,source_node_id) REFERENCES icerik_birimleri(case_id,record_id),
 CHECK(plane IN ('PLANNED','WRITTEN','REPORTED_EVENT','DOCUMENTED_EVENT','USER_POSITION')),
 CHECK(regexp_full_match(fact_digest,'[0-9a-f]{64}')),
 CHECK(regexp_full_match(payload_digest,'[0-9a-f]{64}'))
);
CREATE TABLE yukumlulukler (
 case_id UUID NOT NULL, record_id UUID NOT NULL, source_node_id UUID NOT NULL,
 scope_key VARCHAR NOT NULL, obligation_digest VARCHAR NOT NULL,
 payload JSON NOT NULL, payload_digest VARCHAR NOT NULL,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,obligation_digest),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,source_node_id) REFERENCES icerik_birimleri(case_id,record_id),
 CHECK(regexp_full_match(obligation_digest,'[0-9a-f]{64}')),
 CHECK(regexp_full_match(payload_digest,'[0-9a-f]{64}'))
);
CREATE TABLE gerceklesmeler (
 case_id UUID NOT NULL, record_id UUID NOT NULL, obligation_id UUID NOT NULL,
 source_node_id UUID NOT NULL, event_digest VARCHAR NOT NULL,
 payload JSON NOT NULL, payload_digest VARCHAR NOT NULL,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,event_digest),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,obligation_id) REFERENCES yukumlulukler(case_id,record_id),
 FOREIGN KEY(case_id,source_node_id) REFERENCES icerik_birimleri(case_id,record_id),
 CHECK(regexp_full_match(event_digest,'[0-9a-f]{64}')),
 CHECK(regexp_full_match(payload_digest,'[0-9a-f]{64}'))
);
