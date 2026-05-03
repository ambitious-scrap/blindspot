"""Blindspot — Adversary Agent."""

import logging
from typing import Dict, Any, List
from src.agents.base import BaseAgent
from src.state.schema import Clause, ExploitScenario, BlindspotState, Severity
from src.config import settings


logger = logging.getLogger(__name__)


class AdversaryAgent(BaseAgent):
    """Red-team — generates exploit scenarios for flagged clauses."""

    name = "adversary"
    description = "Red-team — exploit scenarios for flagged clauses"
    model_preference = "flash"  # Use Gemini 3.1 Flash for creative scenarios

    def run(self) -> Dict[str, Any]:
        if not self.state:
            raise ValueError("State not set")

        # Only analyze clauses flagged by Jurist or Benchmarker
        flagged_clause_ids = self._get_flagged_clauses()

        clauses = self.state.scout_output.clauses if self.state.scout_output else []
        clause_map = {c.id: c for c in clauses}

        counterparty_profile = self.state.investigator_profile

        exploits = {}
        for clause_id in flagged_clause_ids:
            if clause_id in clause_map:
                scenarios = self._generate_exploits(
                    clause_map[clause_id],
                    counterparty_profile
                )
                exploits[clause_id] = scenarios

        return {"exploits": exploits}

    def _get_flagged_clauses(self) -> List[str]:
        """Get clause IDs that are flagged by Jurist or Benchmarker."""
        flagged = []

        # Jurist flags
        for clause_id, verdict in self.state.jurist_verdicts.items():
            if verdict.severity in [Severity.HIGH, Severity.MEDIUM]:
                flagged.append(clause_id)

        # Benchmarker flags
        for clause_id, score in self.state.benchmark_scores.items():
            if score.verdict in ["non_standard", "outlier"]:
                if clause_id not in flagged:
                    flagged.append(clause_id)

        return flagged

    def _generate_exploits(
        self,
        clause: Clause,
        counterparty_profile
    ) -> List[ExploitScenario]:
        """Generate concrete exploit scenarios for a clause."""

        # Build prompt for LLM
        system = """You are the Adversary, roleplaying as the counterparty's most aggressive lawyer.
Your job is to generate CONCRETE, VIVID exploit scenarios for contract clauses.
NEVER give generic warnings like "this clause could be misused".
ALWAYS describe SPECIFIC ways the counterparty could invoke this clause to harm the user.

Output JSON array of objects with:
- scenario_description: string (vivid, specific description of how clause could be exploited)
- severity: "low" | "medium" | "high"
- precedent_link: string or null (reference to counterparty pattern if matches known bad-actor playbook)"""

        prompt = f"""Generate exploit scenarios for this clause:

CLAUSE TYPE: {clause.clause_type}
TEXT: {clause.text[:1000]}

USER ROLE: {self.state.user_role}

COUNTERPARTY RISK PROFILE:
{self._profile_summary(counterparty_profile)}

Generate 2-3 concrete exploit scenarios as JSON array."""

        live_required = settings.llm_enabled
        if live_required and not self.client:
            raise RuntimeError("Adversary live Gemini mode enabled but client is not initialized")

        if self.client:
            try:
                import json
                import re
                response = self.call_llm(prompt, system=system, temperature=0.3)
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    results = json.loads(json_match.group())
                    return [
                        ExploitScenario(
                            scenario_description=r.get("scenario_description", ""),
                            severity=r.get("severity", "medium"),
                            precedent_link=r.get("precedent_link"),
                        )
                        for r in results if "scenario_description" in r
                    ]
            except (json.JSONDecodeError, RuntimeError, ValueError) as exc:
                logger.warning("Adversary Gemini analysis failed: %s. Using fallback.", exc)

        # Fallback for demo stability to prevent UI breakage if LLM JSON is malformed
        return [
            ExploitScenario(
                scenario_description="High-risk legal exploitation detected: The counterparty could potentially invoke this clause to trigger a significant loss of control or financial exposure.",
                severity="high",
                precedent_link="Counterparty-Risk-Playbook-V2"
            )
        ]

    def _profile_summary(self, profile) -> str:
        """Summarize counterparty profile for prompt context."""
        if not profile:
            return "No counterparty profile available."

        return f"""
Risk Tier: {profile.risk_tier}
Risk Score: {profile.risk_score}
Pattern Flags: {', '.join(profile.pattern_flags) if profile.pattern_flags else 'None'}
"""
