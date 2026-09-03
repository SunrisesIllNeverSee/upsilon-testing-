"""Semantic loss detection.

Detects silent semantic loss between predecessor and successor kernels.
This is a specialized detector for the "no silent semantic loss"
invariant (CONSERVATION_INVARIANTS.md §2.5), providing detailed
field-by-field loss reporting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from upsilon.models import (
    AuthorizedTransformation,
    CommitmentKernel,
    TransformationFamily,
)


@dataclass
class FieldLoss:
    """A detected semantic loss in one field."""

    field_name: str
    lost_value: Any
    loss_type: str  # "list_shrink", "dict_shrink", "value_drop", "status_drop"


@dataclass
class LossDetectionResult:
    """Result of semantic loss detection."""

    losses: list[FieldLoss] = field(default_factory=list)

    @property
    def has_losses(self) -> bool:
        return len(self.losses) > 0

    def summary(self) -> str:
        if not self.losses:
            return "No semantic losses detected"
        lines = [f"  {l.field_name}: {l.loss_type} (lost: {l.lost_value})" for l in self.losses]
        return f"{len(self.losses)} semantic losses detected:\n" + "\n".join(lines)


class LossDetector:
    """Detects silent semantic loss between predecessor and successor.

    Existing semantics may not disappear without evidence of
    removal/change.  If the predecessor has exceptions, the successor
    must either preserve them, expand them, or explicitly contract
    them with evidence.
    """

    # Fields where loss is semantically meaningful
    LIST_FIELDS: ClassVar[list[str]] = ["exceptions", "party", "application_order", "defined_term_support"]
    DICT_FIELDS: ClassVar[list[str]] = ["scope", "trigger", "cure", "applicability"]
    SCALAR_FIELDS: ClassVar[list[str]] = ["threshold", "rate", "operator", "unit", "frequency", "deadline"]

    def detect(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> LossDetectionResult:
        """Detect semantic losses between predecessor and successor."""
        if predecessor is None or successor is None:
            return LossDetectionResult()
        if delta.transformation_type == TransformationFamily.CREATE:
            return LossDetectionResult()

        affected = set(delta.affected_field_names)
        losses: list[FieldLoss] = []

        # Check list fields for shrinkage
        for field_name in self.LIST_FIELDS:
            if field_name in affected:
                continue
            pred_val = predecessor.field_value(field_name)
            succ_val = successor.field_value(field_name)
            if isinstance(pred_val, list) and isinstance(succ_val, list):
                if len(succ_val) < len(pred_val):
                    lost = [x for x in pred_val if x not in succ_val]
                    losses.append(FieldLoss(
                        field_name=field_name,
                        lost_value=lost,
                        loss_type="list_shrink",
                    ))

        # Check dict fields for key loss
        for field_name in self.DICT_FIELDS:
            if field_name in affected:
                continue
            pred_val = predecessor.field_value(field_name)
            succ_val = successor.field_value(field_name)
            if isinstance(pred_val, dict) and isinstance(succ_val, dict):
                lost_keys = set(pred_val.keys()) - set(succ_val.keys())
                if lost_keys:
                    losses.append(FieldLoss(
                        field_name=field_name,
                        lost_value={k: pred_val[k] for k in lost_keys},
                        loss_type="dict_shrink",
                    ))

        # Check scalar fields for value drop
        for field_name in self.SCALAR_FIELDS:
            if field_name in affected:
                continue
            pred_val = predecessor.field_value(field_name)
            succ_val = successor.field_value(field_name)
            if pred_val is not None and succ_val is None:
                losses.append(FieldLoss(
                    field_name=field_name,
                    lost_value=pred_val,
                    loss_type="value_drop",
                ))

        return LossDetectionResult(losses=losses)
