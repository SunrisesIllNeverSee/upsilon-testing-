"""Transformation application.

Implements the Apply operation:

    C_t = Apply(C_{t-1}, Delta_t)

This is NOT the execution layer (Layer F).  This is a pure functional
application that produces the successor kernel from the predecessor
kernel and an authorized transformation.  The result must still pass
conservation validation and the authority gate before it becomes
authoritative.
"""
from __future__ import annotations

from upsilon.models import (
    AuthorizedTransformation,
    CommitmentKernel,
    TransformationFamily,
)


def apply_transformation(
    predecessor: CommitmentKernel,
    delta: AuthorizedTransformation,
) -> CommitmentKernel:
    """Apply an authorized transformation to a predecessor kernel.

    Produces the successor kernel C_t from C_{t-1} and Delta_t.

    The successor inherits all preserved fields from the predecessor.
    Only affected fields are modified.  Identity persists unless the
    transformation is identity-changing (CREATE, TERMINATE, RENUMBER).

    Conservation invariant (CONSERVATION_INVARIANTS.md §2.3):

        C_t[f] == C_{t-1}[f]  for all f not in affected(Delta_t)
    """
    # Deep copy the predecessor to preserve all fields
    successor = predecessor.model_copy(deep=True)

    # Apply affected fields
    for affected in delta.affected_fields:
        field_name = affected.field_name
        new_value = affected.new_value

        if delta.transformation_type == TransformationFamily.EXCEPTION_EXPANSION:
            # Append to exceptions list
            current_exceptions = list(successor.exceptions)
            if new_value is not None and new_value not in current_exceptions:
                current_exceptions.append(new_value)
            successor.exceptions = current_exceptions
        elif delta.transformation_type == TransformationFamily.EXCEPTION_CONTRACTION:
            # Remove from exceptions list
            current_exceptions = list(successor.exceptions)
            if new_value in current_exceptions:
                current_exceptions.remove(new_value)
            successor.exceptions = current_exceptions
        elif hasattr(successor, field_name):
            setattr(successor, field_name, new_value)

    # Handle status transitions
    if delta.transformation_type == TransformationFamily.TERMINATE:
        successor.status = "TERMINATED"
    elif delta.transformation_type == TransformationFamily.WAIVER:
        successor.status = "WAIVED"
    elif delta.transformation_type == TransformationFamily.REINSTATEMENT:
        successor.status = "ACTIVE"

    # Identity persists for non-identity-changing transformations
    # (CREATE, TERMINATE, RENUMBER are handled by the lineage layer)

    return successor
