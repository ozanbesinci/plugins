-- P5 derived artifact versions are distinct from input/source document versions.
CREATE TABLE docx_turevleri (
 case_id UUID NOT NULL, record_id UUID NOT NULL, operation_id UUID NOT NULL,
 source_version_id UUID NOT NULL, artifact_sha256 VARCHAR NOT NULL,
 metadata JSON NOT NULL, metadata_digest VARCHAR NOT NULL, artifact BLOB NOT NULL,
 PRIMARY KEY(case_id,record_id), UNIQUE(case_id,operation_id),
 FOREIGN KEY(case_id,record_id) REFERENCES kayitlar(case_id,record_id),
 FOREIGN KEY(case_id,operation_id) REFERENCES islemler(case_id,record_id),
 FOREIGN KEY(case_id,source_version_id) REFERENCES belge_surumu(case_id,record_id),
 CHECK(regexp_full_match(artifact_sha256,'[0-9a-f]{64}')),
 CHECK(regexp_full_match(metadata_digest,'[0-9a-f]{64}'))
);
