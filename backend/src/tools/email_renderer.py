"""Blindspot — Email Renderer

Renders the negotiation email draft from Negotiator agent outputs.
"""

from typing import Dict
from src.state.schema import Rewrite


class EmailRenderer:
    """Renders copy-paste-ready negotiation email."""

    def render_email(
        self,
        rewrites: Dict[str, Rewrite],
        user_role: str = "freelancer",
        counterparty: str = "the client"
    ) -> str:
        """Generate a professional negotiation email."""

        # Count how many clauses need rewriting
        needs_rewrite = [
            (cid, r) for cid, r in rewrites.items()
            if r.proposed_text != r.original_text
        ]

        if not needs_rewrite:
            return self._render_acceptance_email(counterparty)

        email = f"""Subject: Re: Contract Review — Proposed Revisions

Dear {counterparty or "Hiring Team"},

Thank you for sharing the contract. I've reviewed the agreement carefully and have a few proposed revisions to ensure our mutual interests are protected and the terms align with market standards.

PROPOSED CHANGES:

"""

        for clause_id, rewrite in needs_rewrite:
            email += f"""
{clause_id.upper().replace('_', ' ')}:
Original: {rewrite.original_text[:200]}...
Proposed: {rewrite.proposed_text[:200]}...
Rationale: {rewrite.rationale}

"""

        email += f"""
These adjustments will ensure our agreement is fair, enforceable, and consistent with industry standards under Indian law.

I'm available to discuss these changes at your convenience. Please let me know if you'd like to negotiate any of these points.

Best regards,
[{user_role.title()}]
"""

        return email

    def _render_acceptance_email(self, counterparty: str) -> str:
        """Render email when no changes needed."""
        return f"""Subject: Re: Contract Review — Ready to Sign

Dear {counterparty or "Hiring Team"},

I've completed my review of the contract. The terms are fair, market-standard, and enforceable under Indian law.

I'm ready to sign and begin work. Please send the final version for signature.

Best regards,
[Your Name]
"""
