from __future__ import annotations

import hashlib
import json

from backend.apps.support_api.core.errors import ApiError
from backend.apps.support_api.walking_skeleton.contracts import Proposal, TicketRecord


class FakeAgentAdapter:
    """Fixed UC-01 proposal; replaced before the v0.1 release profile."""

    def propose(self, ticket: TicketRecord) -> Proposal:
        action = {
            "action_type": "sync_payment_status",
            "target": {"ticket_id": str(ticket.id), "order_ref": "ORDER-SKELETON-001"},
            "desired_status": "PAID",
        }
        canonical = json.dumps(action, sort_keys=True, separators=(",", ":"))
        proposal_hash = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        return Proposal(
            version=1,
            proposal_hash=proposal_hash,
            summary="Synchronize the synthetic order after a fixed Payment Mismatch review.",
            action=action,
            evidence=(
                "Synthetic payment fixture reports SUCCEEDED.",
                "Walking Skeleton policy fixture permits review of payment synchronization.",
            ),
        )


class FakeApprovalAdapter:
    """Validates the final decision envelope without production approval persistence."""

    def validate_decision(
        self,
        *,
        decision: str,
        expected_version: int,
        expected_proposal_hash: str,
        proposal: Proposal,
    ) -> None:
        if decision == "edit":
            raise ApiError(
                status_code=422,
                code="REQUEST_VALIDATION_ERROR",
                message="Proposal editing is outside the Walking Skeleton scope.",
            )
        if expected_version != proposal.version or expected_proposal_hash != proposal.proposal_hash:
            raise ApiError(
                status_code=409,
                code="APPROVAL_STALE",
                message="The approval proposal version or hash is stale.",
            )


class FakeActionAdapter:
    """Returns deterministic VERIFIED without making a commerce request or write."""

    def execute(self, proposal: Proposal) -> str:
        del proposal
        return "VERIFIED"
