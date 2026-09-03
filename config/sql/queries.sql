-- 1. Leverage covenant relaxed in Amendment >= 2 but risk representation stale/missing.
WITH leverage_changes AS (
  SELECT
    a.id AS agreement_id,
    a.issuer_name,
    c.id AS commitment_id,
    c.canonical_key,
    av.version_number,
    prev.threshold AS prior_threshold,
    curr.threshold AS current_threshold,
    curr.id AS current_commitment_version_id
  FROM commitment c
  JOIN agreement a ON a.id = c.agreement_id
  JOIN commitment_version curr ON curr.commitment_id = c.id
  JOIN agreement_version av ON av.id = curr.agreement_version_id
  JOIN commitment_version prev ON prev.id = curr.parent_commitment_version_id
  WHERE c.commitment_type = 'financial_covenant'
    AND curr.subject = 'total_leverage_ratio'
    AND av.version_number >= 2
    AND curr.threshold > prev.threshold
)
SELECT
  lc.issuer_name,
  lc.canonical_key,
  lc.version_number,
  lc.prior_threshold,
  lc.current_threshold,
  dr.name AS downstream_system,
  pc.status,
  pc.checked_at
FROM leverage_changes lc
JOIN downstream_representation dr
  ON dr.agreement_id = lc.agreement_id
 AND dr.representation_type = 'risk_model'
LEFT JOIN propagation_check pc
  ON pc.authoritative_commitment_version_id = lc.current_commitment_version_id
 AND pc.downstream_representation_id = dr.id
WHERE pc.id IS NULL
   OR pc.status IN ('STALE','MISSING','PARTIAL')
ORDER BY lc.issuer_name, lc.version_number;


-- 2. Trace complete lineage of a commitment.
WITH RECURSIVE lineage AS (
  SELECT
    cv.id, cv.parent_commitment_version_id, cv.agreement_version_id,
    cv.threshold, cv.status, cv.valid_from, cv.valid_to, 0 AS depth
  FROM commitment_version cv
  WHERE cv.id = :current_commitment_version_id

  UNION ALL

  SELECT
    parent.id, parent.parent_commitment_version_id, parent.agreement_version_id,
    parent.threshold, parent.status, parent.valid_from, parent.valid_to,
    l.depth + 1
  FROM commitment_version parent
  JOIN lineage l ON l.parent_commitment_version_id = parent.id
)
SELECT * FROM lineage ORDER BY depth DESC;


-- 3. Authoritative/effective kernel AS OF a timestamp.
-- Validity convention is half-open: [valid_from, valid_to).
SELECT DISTINCT ON (c.id)
  c.canonical_key,
  c.commitment_type,
  cv.*
FROM commitment c
JOIN commitment_version cv ON cv.commitment_id = c.id
JOIN agreement_version av ON av.id = cv.agreement_version_id
WHERE c.agreement_id = :agreement_id
  AND cv.status NOT IN ('DELETED','SUPERSEDED')
  AND (cv.valid_from IS NULL OR cv.valid_from <= :as_of)
  AND (cv.valid_to   IS NULL OR cv.valid_to   >  :as_of)
  AND (av.effective_at IS NULL OR av.effective_at <= :as_of)
ORDER BY c.id, av.version_number DESC, cv.recorded_at DESC;


-- 4. Reference renumberings created by amendments.
SELECT
  a.issuer_name,
  av.version_number,
  rc.old_section_ref,
  rc.new_section_ref,
  rc.effective_at
FROM reference_change rc
JOIN agreement a ON a.id = rc.agreement_id
JOIN agreement_version av ON av.id = rc.amendment_version_id
WHERE rc.agreement_id = :agreement_id
ORDER BY rc.effective_at, av.version_number;


-- 5. Unresolved instructions requiring validation.
SELECT
  a.issuer_name,
  av.version_number,
  ai.instruction_order,
  ai.instruction_type,
  ai.target_section_ref,
  ai.parser_confidence,
  ss.quoted_text
FROM amendment_instruction ai
JOIN agreement_version av ON av.id = ai.amendment_version_id
JOIN agreement a ON a.id = av.agreement_id
LEFT JOIN source_span ss ON ss.id = ai.source_span_id
WHERE ai.status = 'UNRESOLVED'
   OR ai.instruction_type = 'UNRESOLVED'
ORDER BY a.issuer_name, av.version_number, ai.instruction_order;
