CREATE TABLE IF NOT EXISTS run_meta (
  key VARCHAR PRIMARY KEY,
  value VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS task_dispatches (
  task_id VARCHAR PRIMARY KEY,
  packet_sha256 VARCHAR NOT NULL,
  schema_sha256 VARCHAR NOT NULL,
  execution_sha256 VARCHAR NOT NULL,
  context_path VARCHAR NOT NULL,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS source_relations (
  relation_id VARCHAR PRIMARY KEY,
  source_document_id VARCHAR NOT NULL,
  target_document_id VARCHAR NOT NULL,
  relation_type VARCHAR NOT NULL,
  source_sha256 VARCHAR NOT NULL,
  target_sha256 VARCHAR NOT NULL,
  declaration_json VARCHAR NOT NULL,
  previous_offer_id VARCHAR,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_confirmations (
  confirmation_id VARCHAR PRIMARY KEY,
  fact_id VARCHAR NOT NULL,
  original_evidence_id VARCHAR NOT NULL,
  confirmation_evidence_id VARCHAR NOT NULL,
  relation_id VARCHAR NOT NULL,
  original_sha256 VARCHAR NOT NULL,
  confirmation_sha256 VARCHAR NOT NULL,
  value_json VARCHAR NOT NULL,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_state (
  phase VARCHAR PRIMARY KEY,
  status VARCHAR NOT NULL,
  started_at VARCHAR,
  completed_at VARCHAR,
  detail_json VARCHAR
);

CREATE TABLE IF NOT EXISTS documents (
  document_id VARCHAR PRIMARY KEY,
  parent_document_id VARCHAR,
  relative_path VARCHAR NOT NULL,
  source_path VARCHAR,
  filename VARCHAR NOT NULL,
  extension VARCHAR,
  mime_type VARCHAR,
  format_family VARCHAR NOT NULL,
  document_role VARCHAR,
  role_confidence DOUBLE,
  supplier_id VARCHAR,
  offer_id VARCHAR,
  revision_label VARCHAR,
  revision_status VARCHAR,
  sha256 VARCHAR NOT NULL,
  size_bytes BIGINT NOT NULL,
  parser_name VARCHAR,
  parser_version VARCHAR,
  parse_status VARCHAR NOT NULL,
  parse_notes VARCHAR,
  source_mtime DOUBLE,
  metadata_json VARCHAR,
  active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS document_units (
  unit_id VARCHAR PRIMARY KEY,
  document_id VARCHAR NOT NULL,
  unit_type VARCHAR NOT NULL,
  unit_index INTEGER,
  locator_json VARCHAR NOT NULL,
  text_content VARCHAR,
  structured_json VARCHAR,
  content_sha256 VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
  supplier_id VARCHAR PRIMARY KEY,
  display_name VARCHAR NOT NULL,
  normalized_name VARCHAR,
  identification_status VARCHAR DEFAULT 'provisional'
);

CREATE TABLE IF NOT EXISTS offers (
  offer_id VARCHAR PRIMARY KEY,
  supplier_id VARCHAR NOT NULL,
  display_name VARCHAR,
  quote_number VARCHAR,
  quote_date VARCHAR,
  validity_end VARCHAR,
  revision_label VARCHAR,
  status VARCHAR DEFAULT 'active',
  source_document_ids_json VARCHAR
);

CREATE TABLE IF NOT EXISTS requirements (
  requirement_id VARCHAR PRIMARY KEY,
  source_document_id VARCHAR,
  source_unit_id VARCHAR,
  category VARCHAR,
  section VARCHAR,
  text VARCHAR NOT NULL,
  critical BOOLEAN DEFAULT FALSE,
  evidence_id VARCHAR
);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id VARCHAR PRIMARY KEY,
  document_id VARCHAR NOT NULL,
  unit_id VARCHAR,
  locator_json VARCHAR NOT NULL,
  quote VARCHAR,
  evidence_status VARCHAR NOT NULL,
  extraction_path VARCHAR NOT NULL,
  confidence DOUBLE,
  source_sha256 VARCHAR
);

CREATE TABLE IF NOT EXISTS facts (
  fact_id VARCHAR PRIMARY KEY,
  offer_id VARCHAR,
  supplier_id VARCHAR,
  requirement_id VARCHAR,
  field_key VARCHAR NOT NULL,
  value_text VARCHAR,
  value_number DOUBLE,
  value_date VARCHAR,
  unit VARCHAR,
  currency VARCHAR,
  evidence_status VARCHAR NOT NULL,
  critical BOOLEAN DEFAULT FALSE,
  evidence_id VARCHAR,
  extraction_path VARCHAR NOT NULL,
  normalized_json VARCHAR,
  updated_at VARCHAR
);

CREATE TABLE IF NOT EXISTS scope_items (
  scope_id VARCHAR PRIMARY KEY,
  cost_role VARCHAR,
  offer_id VARCHAR,
  classification VARCHAR NOT NULL,
  description VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  amount DOUBLE,
  currency VARCHAR,
  payment_date VARCHAR,
  evidence_ids_json VARCHAR,
  critical BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS exclusions (
  exclusion_id VARCHAR PRIMARY KEY,
  offer_id VARCHAR,
  requirement_id VARCHAR,
  decision VARCHAR NOT NULL,
  reason VARCHAR NOT NULL,
  evidence_ids_json VARCHAR,
  status VARCHAR DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS review_facts (
  review_id VARCHAR NOT NULL,
  fact_id VARCHAR NOT NULL,
  value_text VARCHAR,
  value_number DOUBLE,
  value_date VARCHAR,
  evidence_status VARCHAR NOT NULL,
  evidence_id VARCHAR,
  review_path VARCHAR NOT NULL,
  PRIMARY KEY(review_id, fact_id)
);

CREATE TABLE IF NOT EXISTS differences (
  difference_id VARCHAR PRIMARY KEY,
  review_id VARCHAR,
  fact_id VARCHAR,
  difference_type VARCHAR NOT NULL,
  main_json VARCHAR,
  independent_json VARCHAR,
  critical BOOLEAN DEFAULT FALSE,
  status VARCHAR DEFAULT 'open',
  generation INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS adjudications (
  difference_id VARCHAR PRIMARY KEY,
  decision VARCHAR NOT NULL,
  reason VARCHAR NOT NULL,
  replacement_json VARCHAR,
  evidence_ids_json VARCHAR,
  adjudicated_at VARCHAR
);

CREATE TABLE IF NOT EXISTS calculations (
  calculation_id VARCHAR PRIMARY KEY,
  offer_id VARCHAR,
  calculation_type VARCHAR NOT NULL,
  inputs_json VARCHAR NOT NULL,
  result_json VARCHAR NOT NULL,
  calculation_version VARCHAR NOT NULL,
  input_hash VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  updated_at VARCHAR
);

CREATE TABLE IF NOT EXISTS open_issues (
  issue_id VARCHAR PRIMARY KEY,
  owner VARCHAR NOT NULL,
  severity VARCHAR NOT NULL,
  issue_type VARCHAR NOT NULL,
  question VARCHAR NOT NULL,
  fact_ids_json VARCHAR,
  evidence_ids_json VARCHAR,
  status VARCHAR DEFAULT 'open',
  created_at VARCHAR,
  resolved_at VARCHAR
);

CREATE TABLE IF NOT EXISTS task_queue (
  task_id VARCHAR PRIMARY KEY,
  phase VARCHAR NOT NULL,
  role VARCHAR NOT NULL,
  task_kind VARCHAR NOT NULL,
  document_id VARCHAR,
  offer_id VARCHAR,
  requirement_id VARCHAR,
  payload_json VARCHAR NOT NULL,
  priority INTEGER DEFAULT 100,
  critical BOOLEAN DEFAULT FALSE,
  status VARCHAR DEFAULT 'pending',
  attempts INTEGER DEFAULT 0,
  result_path VARCHAR,
  created_at VARCHAR,
  completed_at VARCHAR
);

CREATE TABLE IF NOT EXISTS model_receipts (
  receipt_id VARCHAR PRIMARY KEY,
  task_id VARCHAR NOT NULL,
  model_name VARCHAR NOT NULL,
  reasoning_effort VARCHAR NOT NULL,
  response_id VARCHAR,
  input_tokens BIGINT,
  cached_input_tokens BIGINT,
  output_tokens BIGINT,
  telemetry_status VARCHAR DEFAULT 'measured',
  telemetry_reason VARCHAR,
  recorded_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_findings (
  finding_id VARCHAR PRIMARY KEY,
  artifact_id VARCHAR,
  finding_type VARCHAR NOT NULL,
  locator_json VARCHAR,
  severity VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  message VARCHAR NOT NULL,
  finding_hash VARCHAR,
  created_at VARCHAR
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id VARCHAR PRIMARY KEY,
  artifact_type VARCHAR NOT NULL,
  relative_path VARCHAR NOT NULL,
  sha256 VARCHAR NOT NULL,
  parent_hashes_json VARCHAR,
  status VARCHAR NOT NULL,
  created_at VARCHAR
);

CREATE TABLE IF NOT EXISTS render_hashes (
  artifact_id VARCHAR NOT NULL,
  render_key VARCHAR NOT NULL,
  render_sha256 VARCHAR NOT NULL,
  qa_status VARCHAR,
  qa_note VARCHAR,
  PRIMARY KEY(artifact_id, render_key)
);

CREATE TABLE IF NOT EXISTS cache_index (
  cache_key VARCHAR PRIMARY KEY,
  source_sha256 VARCHAR NOT NULL,
  parser_name VARCHAR NOT NULL,
  parser_version VARCHAR NOT NULL,
  schema_version VARCHAR NOT NULL,
  result_json VARCHAR NOT NULL,
  created_at VARCHAR
);

CREATE TABLE IF NOT EXISTS workflow_events (
  event_id VARCHAR PRIMARY KEY,
  phase VARCHAR,
  event_type VARCHAR NOT NULL,
  payload_json VARCHAR,
  created_at VARCHAR NOT NULL
);


CREATE TABLE IF NOT EXISTS source_authority (
  document_id VARCHAR PRIMARY KEY,
  authority_scope VARCHAR NOT NULL,
  authority_class VARCHAR NOT NULL,
  authority_status VARCHAR NOT NULL,
  precedence_rank INTEGER,
  rationale VARCHAR,
  assessed_by VARCHAR NOT NULL,
  assessed_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS data_quality_findings (
  finding_id VARCHAR PRIMARY KEY,
  check_id VARCHAR NOT NULL,
  entity_type VARCHAR NOT NULL,
  entity_id VARCHAR,
  severity VARCHAR NOT NULL,
  confidence VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  evidence_json VARCHAR,
  risk VARCHAR NOT NULL,
  remediation VARCHAR,
  finding_hash VARCHAR NOT NULL,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_result_validations (
  validation_id VARCHAR PRIMARY KEY,
  task_id VARCHAR NOT NULL,
  task_kind VARCHAR NOT NULL,
  schema_version VARCHAR NOT NULL,
  result_sha256 VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  errors_json VARCHAR,
  validated_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS scope_ledger (
  scope_item_id VARCHAR PRIMARY KEY,
  scope_type VARCHAR NOT NULL,
  entity_id VARCHAR,
  label VARCHAR NOT NULL,
  expected_json VARCHAR,
  observed_json VARCHAR,
  status VARCHAR NOT NULL,
  critical BOOLEAN DEFAULT FALSE,
  evidence_json VARCHAR,
  revision VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS comparability_checks (
  check_id VARCHAR PRIMARY KEY,
  dimension VARCHAR NOT NULL,
  offer_id VARCHAR,
  reference_value VARCHAR,
  observed_value VARCHAR,
  status VARCHAR NOT NULL,
  critical BOOLEAN DEFAULT TRUE,
  normalization VARCHAR,
  evidence_json VARCHAR,
  revision VARCHAR NOT NULL,
  assessed_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS independent_calculations (
  independent_id VARCHAR PRIMARY KEY,
  calculation_id VARCHAR NOT NULL,
  offer_id VARCHAR,
  calculation_type VARCHAR NOT NULL,
  method VARCHAR NOT NULL,
  expected_json VARCHAR NOT NULL,
  recomputed_json VARCHAR NOT NULL,
  tolerance DOUBLE NOT NULL,
  status VARCHAR NOT NULL,
  detail_json VARCHAR,
  input_hash VARCHAR NOT NULL,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS cost_bridges (
  bridge_id VARCHAR PRIMARY KEY,
  offer_id VARCHAR NOT NULL,
  currency VARCHAR,
  stated_total DOUBLE,
  bridge_total DOUBLE,
  comparable_total DOUBLE,
  residual DOUBLE,
  tolerance DOUBLE NOT NULL,
  status VARCHAR NOT NULL,
  components_json VARCHAR NOT NULL,
  calculation_id VARCHAR,
  revision VARCHAR NOT NULL,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id VARCHAR PRIMARY KEY,
  claim_type VARCHAR NOT NULL,
  claim_text VARCHAR NOT NULL,
  support_status VARCHAR NOT NULL,
  fact_ids_json VARCHAR,
  calculation_ids_json VARCHAR,
  requirement_ids_json VARCHAR,
  evidence_ids_json VARCHAR,
  assertions_json VARCHAR,
  caveat VARCHAR,
  source_task_id VARCHAR,
  revision VARCHAR NOT NULL,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS reviewed_snapshots (
  snapshot_id VARCHAR PRIMARY KEY,
  relative_path VARCHAR NOT NULL,
  sha256 VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  source_revision VARCHAR NOT NULL,
  decision_status VARCHAR,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact_bindings (
  binding_id VARCHAR PRIMARY KEY,
  artifact_id VARCHAR NOT NULL,
  component_id VARCHAR NOT NULL,
  component_type VARCHAR NOT NULL,
  locator_json VARCHAR NOT NULL,
  fact_ids_json VARCHAR,
  calculation_ids_json VARCHAR,
  requirement_ids_json VARCHAR,
  claim_ids_json VARCHAR,
  snapshot_sha256 VARCHAR NOT NULL,
  created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS grain_checks (
  check_id VARCHAR PRIMARY KEY,
  check_type VARCHAR NOT NULL,
  relation_name VARCHAR NOT NULL,
  expected_grain VARCHAR,
  rows_before BIGINT,
  rows_after BIGINT,
  distinct_keys_before BIGINT,
  distinct_keys_after BIGINT,
  expansion_factor DOUBLE,
  status VARCHAR NOT NULL,
  critical BOOLEAN DEFAULT FALSE,
  evidence_json VARCHAR,
  revision VARCHAR NOT NULL,
  checked_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_finding_supersessions (
 finding_id VARCHAR PRIMARY KEY, previous_artifact_id VARCHAR NOT NULL,
 replacement_artifact_id VARCHAR NOT NULL, replacement_sha256 VARCHAR NOT NULL,
 render_hashes_json VARCHAR NOT NULL, superseded_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS visual_rechecks (
 recheck_id VARCHAR PRIMARY KEY, task_id VARCHAR NOT NULL UNIQUE,
 previous_task_id VARCHAR NOT NULL, previous_task_payload_hash VARCHAR NOT NULL,
 previous_receipt_id VARCHAR NOT NULL, finding_id VARCHAR NOT NULL,
 finding_hash VARCHAR NOT NULL,
 artifact_id VARCHAR NOT NULL, artifact_sha256 VARCHAR NOT NULL,
 render_key VARCHAR NOT NULL, render_sha256 VARCHAR NOT NULL,
 reason VARCHAR NOT NULL, created_at VARCHAR NOT NULL,
 result_status VARCHAR, result_note VARCHAR, result_sha256 VARCHAR,
 adopted_reason VARCHAR, adopted_at VARCHAR
);
