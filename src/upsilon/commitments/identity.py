"""Commitment identity resolution.

Implements the agreement-local address map and identity resolution
specified in ``docs/moses/COMMITMENT_IDENTITY.md``.

Key principle: identity is resolved via

    (agreement_identity, section/address, time) -> commitment_identity

NOT via global section heuristics like "Section 7.10 -> leverage_ratio".

Each agreement maintains its own address map.  The same section number
can mean different things in different agreements.  Section numbers
are agreement-local addresses, not global semantic identifiers.

Resolution flow (COMMITMENT_IDENTITY.md §9):
    1. Retrieve predecessor commitments from current_state
    2. Use amendment evidence to establish target identity
       - Section references resolve through the agreement-local address map
       - Alias/text matches supply evidence, not authority
       - Predecessor state biases resolution toward existing commitments
    3. If target identity is established with sufficient confidence:
       - Inherit the predecessor commitment_id (identity persistence)
       - Proceed to transformation interpretation
    4. If target identity cannot be established:
       - Fail closed (UNRESOLVED)
       - Do NOT default to a guess
"""
from __future__ import annotations

from dataclasses import dataclass, field

from upsilon.models import (
    AddressBinding,
    CommitmentIdentity,
    IdentityProvenance,
)


@dataclass
class IdentityResolutionResult:
    """Result of an identity resolution attempt."""

    identity: CommitmentIdentity | None = None
    confidence: float = 0.0
    evidence_level: str = "INSUFFICIENT"  # SUFFICIENT, CORROBORATED, WEAK, INSUFFICIENT
    signals: list[str] = field(default_factory=list)
    fail_closed: bool = False
    failure_reason: str = ""

    @property
    def resolved(self) -> bool:
        """Whether a valid identity was established."""
        return self.identity is not None and not self.fail_closed


class AgreementAddressMap:
    """Agreement-local address map for commitment identity resolution.

    Maps (agreement_identity, section_ref) -> commitment_id.

    The address map is populated from the source agreement (S0) and
    updated by renumbering amendments.  Global section mappings may
    remain as weak discovery evidence only — they may supply a
    candidate identity to the interpretation layer, but they may not,
    by themselves, establish authoritative commitment identity.
    """

    def __init__(self, agreement_identity: str) -> None:
        self.agreement_identity = agreement_identity
        # section_ref -> commitment_id
        self._address_to_id: dict[str, str] = {}
        # commitment_id -> AddressBinding (current)
        self._id_to_address: dict[str, AddressBinding] = {}
        # renumbered addresses: old_section_ref -> commitment_id
        self._renumbered: dict[str, str] = {}

    def register(
        self,
        commitment_id: str,
        section_ref: str,
        established_at_version: str = "S0",
    ) -> AddressBinding:
        """Register a commitment at an address in this agreement."""
        binding = AddressBinding(
            section_ref=section_ref,
            established_at_version=established_at_version,
        )
        self._address_to_id[section_ref] = commitment_id
        self._id_to_address[commitment_id] = binding
        return binding

    def renumber(
        self,
        commitment_id: str,
        new_section_ref: str,
        amendment_id: str,
    ) -> AddressBinding | None:
        """Renumber a commitment's section reference.

        The commitment_id does NOT change.  Both old and new addresses
        resolve to the same identity.  A RENUMBER identity event should
        be recorded by the caller.
        """
        old_binding = self._id_to_address.get(commitment_id)
        if old_binding is None:
            return None

        old_ref = old_binding.section_ref
        new_binding = AddressBinding(
            section_ref=new_section_ref,
            established_at_version=old_binding.established_at_version,
            renumbered_from=old_ref,
        )
        self._id_to_address[commitment_id] = new_binding
        self._address_to_id[new_section_ref] = commitment_id
        self._renumbered[old_ref] = commitment_id
        return new_binding

    def resolve_by_address(self, section_ref: str) -> str | None:
        """Resolve a section reference to a commitment_id.

        Checks both current addresses and renumbered (old) addresses.
        Returns None if the address is not in this agreement's map.
        """
        if section_ref in self._address_to_id:
            return self._address_to_id[section_ref]
        if section_ref in self._renumbered:
            return self._renumbered[section_ref]
        return None

    def get_binding(self, commitment_id: str) -> AddressBinding | None:
        """Get the current address binding for a commitment."""
        return self._id_to_address.get(commitment_id)

    def known_commitments(self) -> list[str]:
        """All commitment_ids registered in this agreement."""
        return list(self._id_to_address.keys())


class IdentityResolver:
    """Resolves commitment identity from amendment evidence + predecessor state.

    The resolver uses the agreement-local address map as the primary
    resolution mechanism.  Alias/text matches supply evidence, not
    authority.  Predecessor state biases resolution toward existing
    commitments but does not determine it.

    The resolver does NOT use global section heuristics as authority.
    Global section mappings may supply a candidate identity as weak
    discovery evidence only.
    """

    def __init__(self, address_map: AgreementAddressMap) -> None:
        self._address_map = address_map

    def resolve(
        self,
        section_ref: str | None = None,
        alias_match: str | None = None,
        text_match: str | None = None,
        predecessor_commitment_ids: list[str] | None = None,
        canonical_key_hint: str | None = None,
    ) -> IdentityResolutionResult:
        """Resolve commitment identity from available evidence signals.

        Returns an IdentityResolutionResult.  If target identity cannot
        be established with sufficient confidence, the result fails
        closed (fail_closed=True, identity=None).

        Identity is established from amendment evidence signals
        (section_ref, alias, text_match) corroborated by the
        agreement-local address map.  ``canonical_key_hint`` is a
        WEAK hint only — it may corroborate an identity established
        by other signals but may NOT establish identity alone.  This
        prevents the circular dependency where the caller pre-selects
        the target via canonical_key_hint and the resolver merely
        certifies that pre-selection.
        """
        signals: list[str] = []
        candidate_ids: list[str] = []
        confidence = 0.0

        # Signal 1: agreement-local address map (strongest)
        # This is the primary identity authority.  A section reference
        # resolves through the agreement-local address map, NOT through
        # global section heuristics or canonical_key_hint.
        if section_ref:
            addr_id = self._address_map.resolve_by_address(section_ref)
            if addr_id:
                signals.append(f"address_map({section_ref} -> {addr_id})")
                candidate_ids.append(addr_id)
                confidence = max(confidence, 0.9)

        # Signal 2: predecessor state bias
        # Predecessor state biases resolution toward existing commitments
        # but does not determine it.  It is evidence, not authority.
        if predecessor_commitment_ids:
            for pid in predecessor_commitment_ids:
                binding = self._address_map.get_binding(pid)
                if binding and section_ref and binding.section_ref == section_ref:
                    signals.append(f"predecessor_bias({pid} at {section_ref})")
                    if pid not in candidate_ids:
                        candidate_ids.append(pid)
                    confidence = max(confidence, 0.85)

        # Signal 3: alias/text match (weak — evidence, not authority)
        # An alias match alone cannot establish authoritative identity.
        # It must be corroborated by address or predecessor evidence.
        if alias_match:
            signals.append(f"alias_match({alias_match})")
            # Alias match alone is WEAK — it does not add a candidate
            # unless corroborated
            if candidate_ids:
                confidence = max(confidence, min(confidence + 0.05, 0.95))
            else:
                confidence = max(confidence, 0.3)  # weak uncorroborated

        if text_match:
            signals.append(f"text_match({text_match})")
            if candidate_ids:
                confidence = max(confidence, min(confidence + 0.03, 0.95))

        # Signal 4: canonical_key_hint (WEAK — corroboration only)
        # This is a hint from the parser/curator, NOT authority.  It
        # may corroborate an identity already established by address
        # map or predecessor evidence, but it may NOT establish
        # identity alone.  This prevents the circular dependency
        # where the caller pre-selects the target and the resolver
        # merely certifies that pre-selection.
        if canonical_key_hint:
            if candidate_ids:
                # Corroborate: if the hint matches a candidate, boost
                # confidence slightly.  If it does NOT match, do not
                # override the address-map resolution.
                if canonical_key_hint in candidate_ids:
                    signals.append(
                        f"canonical_key_hint({canonical_key_hint}, corroborated)"
                    )
                    confidence = max(confidence, min(confidence + 0.02, 0.95))
                else:
                    signals.append(
                        f"canonical_key_hint({canonical_key_hint}, "
                        f"not corroborated by address map)"
                    )
            else:
                # No candidates from address map or predecessor —
                # canonical_key_hint alone is INSUFFICIENT.  Do not
                # add it as a candidate.  This is the key fix: the
                # hint cannot establish identity by itself.
                signals.append(
                    f"canonical_key_hint({canonical_key_hint}, "
                    f"uncorroborated — not authoritative)"
                )

        # Determine evidence level
        if confidence >= 0.85:
            evidence_level = "SUFFICIENT"
        elif confidence >= 0.7:
            evidence_level = "CORROBORATED"
        elif confidence >= 0.5:
            evidence_level = "WEAK"
        else:
            evidence_level = "INSUFFICIENT"

        # Fail closed if insufficient
        if evidence_level == "INSUFFICIENT" or not candidate_ids:
            return IdentityResolutionResult(
                identity=None,
                confidence=confidence,
                evidence_level=evidence_level,
                signals=signals,
                fail_closed=True,
                failure_reason="Insufficient target identity evidence",
            )

        # If we have candidates, pick the one with the most signals
        # (for now, the first candidate from address map is preferred)
        chosen_id = candidate_ids[0]
        binding = self._address_map.get_binding(chosen_id)

        if binding is None:
            return IdentityResolutionResult(
                identity=None,
                confidence=confidence,
                evidence_level=evidence_level,
                signals=signals,
                fail_closed=True,
                failure_reason=f"Commitment {chosen_id} not in address map",
            )

        # Determine provenance
        provenance = IdentityProvenance.S0_ORIGIN
        if binding.renumbered_from is not None:
            provenance = IdentityProvenance.AMENDMENT_RENUMBER

        identity = CommitmentIdentity(
            commitment_id=chosen_id,
            agreement_identity=self._address_map.agreement_identity,
            canonical_key=canonical_key_hint or "",
            local_address=binding,
            provenance=provenance,
            confidence=confidence,
        )

        return IdentityResolutionResult(
            identity=identity,
            confidence=confidence,
            evidence_level=evidence_level,
            signals=signals,
        )
