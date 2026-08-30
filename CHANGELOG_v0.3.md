# Critical Review Fixes — v0.3

Resolved:

1. Added `valid_from`, `valid_to`, `recorded_at`, and `applicability`.
2. Removed `agreement_version.is_authoritative`.
3. Added `persistence.py` bridge from execution result to PostgreSQL.
4. Added lineage-edge persistence and instruction status updates.
5. Added dedicated `reference_change` structure; renumbering no longer mutates commitment scope.
6. Added half-open temporal validity convention `[valid_from, valid_to)`.
7. Temporary waivers now carry bounded validity; persistence schedules restoration.
8. Expanded executor tests for duplicate adds, delete/reinstate, exceptions,
   partial failure, restatement rejection, renumbering, no-op, unresolved passthrough,
   and applicability.
9. Added schema consistency tests.
10. Parser baseline remains intentionally conservative; cross-reference resolution
    remains the critical parser work.
11. Formalized Upsilon/MO§E§ product and IP boundary.

12. Fixed multi-instruction/same-commitment persistence: one resulting version per amendment.
13. Added pure persistence planner and tests.
14. Temporary waiver restoration now preserves concurrent permanent amendment changes.
15. State-changing persistence now requires an effective timestamp.
16. Added optional live PostgreSQL integration test.
