-- Coordinator transaction rebuilds historical tables without content-hash uniqueness.
-- Version IDs, historical row values, primary keys and all foreign keys are preserved.
CREATE TABLE surum_edinim_islemleri (
 case_id UUID NOT NULL, document_id UUID NOT NULL, request_key VARCHAR NOT NULL,
 request_digest VARCHAR NOT NULL, version_id UUID NOT NULL,
 PRIMARY KEY(case_id,document_id,request_key),
 FOREIGN KEY(case_id,document_id) REFERENCES belgeler(case_id,record_id),
 FOREIGN KEY(case_id,version_id) REFERENCES belge_surumu(case_id,record_id)
);
