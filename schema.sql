CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE agreement_version_kind AS ENUM (
  'ORIGINAL',
  'AMENDMENT',
  'AMENDED_AND_RESTATED',
  'COMPOSITE',
  'OTHER'
);

CREATE TYPE commitment_status AS ENUM (
  'ACTIVE',
  'WAIVED',
  'SUSPENDED',
  'DELETED',
  'SUPERSEDED'
);

CREATE TYPE instruction_type AS ENUM (
  'REPLACE_VALUE',
  'REPLACE_TEXT',
  'ADD',
  'ADD_COMMITMENT',
  'DELETE',
  'DELETE_COMMITMENT',
  'WAIVE_TEMPORARILY',
  'SUSPEND',
  'REINSTATE',
  'RESTATE_SECTION',
  'RENUMBER_REFERENCE',
  'FIND_REPLACE_REFERENCE',
  'UNRESOLVED'
);

-- Domain effect: what changed in the commitment domain (separate from the
-- legal-document transformation operation). See models.DomainEffect.
CREATE TYPE domain_effect AS ENUM (
  'covenant_threshold_change',
  'commitment_amount_change',
  'deadline_change',
  'exception_expansion',
  'exception_removal',
  'party_change',
  'frequency_change',
  'scope_change',
  'definition_change',
  'unknown'
);

CREATE TYPE instruction_status AS ENUM (
  'PARSED',
  'VALIDATED',
  'REJECTED',
  'APPLIED',
  'UNRESOLVED'
);

CREATE TYPE lineage_edge_type AS ENUM (
  'ORIGINATES_FROM',
  'MODIFIES',
  'SUPERSEDES',
  'WAIVES',
  'REINSTATES',
  'DERIVES_FROM',
  'PROPAGATES_TO'
);

CREATE TYPE propagation_status AS ENUM (
  'CURRENT',
  'STALE',
  'PARTIAL',
  'MISSING',
  'UNKNOWN'
);

CREATE TYPE validation_status AS ENUM (
  'OPEN',
  'APPROVED',
  'REJECTED',
  'NEEDS_SECOND_REVIEW'
);

CREATE TABLE agreement (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  issuer_cik TEXT,
  issuer_name TEXT NOT NULL,
  agreement_name TEXT NOT NULL,
  executed_at DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE source_document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id UUID REFERENCES agreement(id) ON DELETE CASCADE,
  accession_number TEXT,
  exhibit_number TEXT,
  filing_type TEXT,
  filed_at DATE,
  source_url TEXT,
  sha256 TEXT NOT NULL,
  storage_uri TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (sha256)
);

CREATE TABLE agreement_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id UUID NOT NULL REFERENCES agreement(id) ON DELETE CASCADE,
  source_document_id UUID REFERENCES source_document(id),
  kind agreement_version_kind NOT NULL,
  version_number INTEGER NOT NULL,
  effective_at TIMESTAMPTZ,
  prior_version_id UUID REFERENCES agreement_version(id),
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (agreement_id, version_number)
);

CREATE TABLE source_span (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_document_id UUID NOT NULL REFERENCES source_document(id) ON DELETE CASCADE,
  section_ref TEXT,
  start_offset INTEGER,
  end_offset INTEGER,
  quoted_text TEXT,
  locator JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE commitment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id UUID NOT NULL REFERENCES agreement(id) ON DELETE CASCADE,
  canonical_key TEXT NOT NULL,
  commitment_type TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (agreement_id, canonical_key)
);

CREATE TABLE commitment_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  commitment_id UUID NOT NULL REFERENCES commitment(id) ON DELETE CASCADE,
  agreement_version_id UUID NOT NULL REFERENCES agreement_version(id) ON DELETE CASCADE,
  source_span_id UUID REFERENCES source_span(id),
  parent_commitment_version_id UUID REFERENCES commitment_version(id),
  status commitment_status NOT NULL DEFAULT 'ACTIVE',

  -- Bitemporal model.
  -- Legal/effective validity uses half-open interval [valid_from, valid_to).
  valid_from TIMESTAMPTZ,
  valid_to TIMESTAMPTZ,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Conditional applicability for springing covenants, step-downs, waivers, etc.
  applicability JSONB NOT NULL DEFAULT '{}'::jsonb,

  party JSONB NOT NULL DEFAULT '[]'::jsonb,
  modality TEXT,
  action TEXT,
  subject TEXT,
  operator TEXT,
  threshold NUMERIC,
  unit TEXT,
  frequency TEXT,
  deadline TEXT,
  scope JSONB NOT NULL DEFAULT '{}'::jsonb,
  exceptions JSONB NOT NULL DEFAULT '[]'::jsonb,
  trigger JSONB NOT NULL DEFAULT '{}'::jsonb,
  grace_period TEXT,
  cure JSONB NOT NULL DEFAULT '{}'::jsonb,
  application_order JSONB NOT NULL DEFAULT '[]'::jsonb,

  normalized_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  extraction_confidence NUMERIC CHECK (extraction_confidence BETWEEN 0 AND 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from)
);

CREATE TABLE amendment_instruction (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  amendment_version_id UUID NOT NULL REFERENCES agreement_version(id) ON DELETE CASCADE,
  source_span_id UUID REFERENCES source_span(id),
  instruction_order INTEGER NOT NULL,
  instruction_type instruction_type NOT NULL,
  domain_effect domain_effect,
  target_commitment_id UUID REFERENCES commitment(id),
  target_section_ref TEXT,
  old_value JSONB,
  new_value JSONB,
  effective_start TIMESTAMPTZ,
  effective_end TIMESTAMPTZ,
  parser_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  parser_confidence NUMERIC CHECK (parser_confidence BETWEEN 0 AND 1),
  status instruction_status NOT NULL DEFAULT 'PARSED',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (amendment_version_id, instruction_order)
);

CREATE TABLE lineage_edge (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_commitment_version_id UUID NOT NULL REFERENCES commitment_version(id) ON DELETE CASCADE,
  to_commitment_version_id UUID NOT NULL REFERENCES commitment_version(id) ON DELETE CASCADE,
  amendment_instruction_id UUID REFERENCES amendment_instruction(id),
  edge_type lineage_edge_type NOT NULL,
  authority_version_id UUID NOT NULL REFERENCES agreement_version(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (from_commitment_version_id <> to_commitment_version_id)
);

-- Section/cross-reference renumbering is metadata, not a mutation of commitment scope.
CREATE TABLE reference_change (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id UUID NOT NULL REFERENCES agreement(id) ON DELETE CASCADE,
  amendment_version_id UUID NOT NULL REFERENCES agreement_version(id) ON DELETE CASCADE,
  amendment_instruction_id UUID REFERENCES amendment_instruction(id),
  commitment_id UUID REFERENCES commitment(id),
  source_span_id UUID REFERENCES source_span(id),
  old_section_ref TEXT NOT NULL,
  new_section_ref TEXT NOT NULL,
  effective_at TIMESTAMPTZ,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE downstream_representation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id UUID NOT NULL REFERENCES agreement(id) ON DELETE CASCADE,
  representation_type TEXT NOT NULL,
  external_id TEXT,
  name TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  source_uri TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE representation_commitment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  downstream_representation_id UUID NOT NULL REFERENCES downstream_representation(id) ON DELETE CASCADE,
  canonical_key TEXT NOT NULL,
  represented_payload JSONB NOT NULL,
  source_span_id UUID REFERENCES source_span(id),
  extraction_confidence NUMERIC CHECK (extraction_confidence BETWEEN 0 AND 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE propagation_check (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id UUID NOT NULL REFERENCES agreement(id) ON DELETE CASCADE,
  authoritative_commitment_version_id UUID NOT NULL REFERENCES commitment_version(id),
  downstream_representation_id UUID NOT NULL REFERENCES downstream_representation(id),
  representation_commitment_id UUID REFERENCES representation_commitment(id),
  status propagation_status NOT NULL,
  diff JSONB NOT NULL DEFAULT '{}'::jsonb,
  materiality TEXT,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE validation_task (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  object_type TEXT NOT NULL,
  object_id UUID NOT NULL,
  reason TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 50,
  status validation_status NOT NULL DEFAULT 'OPEN',
  assigned_to TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE validation_decision (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  validation_task_id UUID NOT NULL REFERENCES validation_task(id) ON DELETE CASCADE,
  reviewer TEXT NOT NULL,
  decision validation_status NOT NULL,
  rationale TEXT,
  corrected_payload JSONB,
  decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_commitment_version_commitment ON commitment_version(commitment_id);
CREATE INDEX idx_commitment_version_agreement_version ON commitment_version(agreement_version_id);
CREATE INDEX idx_commitment_version_validity ON commitment_version(commitment_id, valid_from, valid_to);
CREATE INDEX idx_instruction_amendment ON amendment_instruction(amendment_version_id);
CREATE INDEX idx_lineage_from ON lineage_edge(from_commitment_version_id);
CREATE INDEX idx_lineage_to ON lineage_edge(to_commitment_version_id);
CREATE INDEX idx_reference_change_agreement ON reference_change(agreement_id, effective_at);
CREATE INDEX idx_propagation_status ON propagation_check(status);
CREATE INDEX idx_downstream_agreement ON downstream_representation(agreement_id);
