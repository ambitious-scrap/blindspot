"""Blindspot v2.0 — Chief Counsel Agent

Orchestration meta-agent operating in four modes:
1. Planner — after Scout, decides which downstream agents to run
2. Router — after Jurist+Benchmarker, decides which clauses need Adversary
3. Reconciler — before final synthesis, surfaces inter-agent disagreements
4. Negotiation Strategist — during negotiation, decides auto-respond/escalate/close
"""

from typing import Dict, Any, List
from src.agents.base import BaseAgent
from src.state.schema import (
    BlindspotState, ExecutionPlan, RoutingDecision, Conflict,
    Synthesis, NegotiationDecision, VerdictLabel, Severity,
)


class ChiefCounselAgent(BaseAgent):
    """Orchestration and strategy meta-agent."""

    name = "chief_counsel"
    description = "Orchestration — planner, router, reconciler, strategist"

    def run(self) -> Dict[str, Any]:
        return {"plan": self.run_planner()}

    def run_planner(self) -> ExecutionPlan:
        """Mode 1: Plan which agents to run after Scout."""
        if not self.state or not self.state.scout_output:
            raise ValueError("Scout output not available for planning")

        doc_type = self.state.scout_output.doc_type
        clauses = self.state.scout_output.clauses

        # Always run Jurist and Benchmarker (in parallel)
        agents_to_run = ["jurist", "benchmarker"]
        parallel_groups = [["jurist", "benchmarker"]]

        # Always run Investigator (in parallel with Jurist/Benchmarker)
        agents_to_run.append("investigator")
        parallel_groups[0].append("investigator")

        # Adversary and Negotiator will be decided by Router later
        # Chief Counsel itself will run as Reconciler at the end

        reasoning = f"Document type: {doc_type}. Running Jurist + Benchmarker + Investigator in parallel. " \
                   f"Adversary will be conditionally executed based on Router decision after verdicts."

        return ExecutionPlan(
            agents_to_run=agents_to_run,
            parallel_groups=parallel_groups,
            reasoning=reasoning,
        )

    def run_router(self) -> RoutingDecision:
        """Mode 2: Decide which clauses warrant Adversary analysis."""
        if not self.state:
            raise ValueError("State not set")

        clauses_to_flag = []

        for clause_id, verdict in self.state.jurist_verdicts.items():
            # Flag clauses with medium or high severity
            if verdict.severity in [Severity.HIGH, Severity.MEDIUM]:
                clauses_to_flag.append(clause_id)

        for clause_id, score in self.state.benchmark_scores.items():
            # Flag clauses that are non-standard or outlier
            if score.verdict in ["non_standard", "outlier"]:
                if clause_id not in clauses_to_flag:
                    clauses_to_flag.append(clause_id)

        reasoning = f"Flagged {len(clauses_to_flag)} clauses for Adversary analysis based on " \
                   f"Jurist severity (medium/high) and Benchmarker verdict (non-standard/outlier)."

        return RoutingDecision(
            clauses_for_adversary=clauses_to_flag,
            reasoning=reasoning,
        )

    def run_reconciler(self) -> Dict[str, Any]:
        """Mode 3: Identify and reconcile inter-agent disagreements."""
        if not self.state:
            raise ValueError("State not set")

        conflicts = []
        synthesis_points = []

        for clause_id in self.state.jurist_verdicts:
            if clause_id not in self.state.benchmark_scores:
                continue

            jurist = self.state.jurist_verdicts[clause_id]
            benchmarker = self.state.benchmark_scores[clause_id]

            # Check for disagreement
            if self._is_disagreement(jurist, benchmarker):
                conflict = Conflict(
                    clause_id=clause_id,
                    agent_a="Jurist",
                    agent_b="Benchmarker",
                    verdict_a=f"{jurist.verdict_label} (severity: {jurist.severity})",
                    verdict_b=f"{benchmarker.verdict} (deviation: {benchmarker.deviation_score:.1f})",
                    reconciliation=self._reconcile(jurist, benchmarker, clause_id),
                )
                conflicts.append(conflict)
                synthesis_points.append(
                    f"Clause {clause_id}: {conflict.reconciliation}"
                )

        # Generate final synthesis
        summary = self._generate_synthesis(conflicts, synthesis_points)

        return {
            "inter_agent_conflicts": conflicts,
            "final_synthesis": Synthesis(
                summary=summary,
                key_risks=self._extract_key_risks(),
                recommended_actions=self._extract_recommendations(),
            ),
        }

    def run_negotiation_strategist(
        self,
        inbound_analysis: Dict[str, Any],
        user_params
    ) -> NegotiationDecision:
        """Mode 4: Decide auto-respond / escalate / close during negotiation."""

        # Check walk-away thresholds
        if self._hits_walk_away(inbound_analysis, user_params):
            return NegotiationDecision(
                decision="escalate",
                reasoning="Counterparty offer hits user walk-away threshold. Human judgment required.",
                escalation_details={
                    "reason": "walk_away_threshold_exceeded",
                    "clause": inbound_analysis.get("clause_id"),
                },
            )

        # Check if acceptable
        if self._is_acceptable(inbound_analysis, user_params):
            return NegotiationDecision(
                decision="close",
                reasoning="Counterparty has agreed to acceptable terms. Deal ready to close.",
                escalation_details=None,
            )

        # Default: auto-respond within authority
        authority = user_params.authority_level if user_params else "balanced"
        return NegotiationDecision(
            decision="auto_respond",
            reasoning=f"Counterparty offer within authority level ({authority}). Negotiator to draft response.",
            escalation_details=None,
        )

    def _is_disagreement(self, jurist, benchmarker) -> bool:
        """Check if Jurist and Benchmarker disagree."""
        # Standard vs outlier = disagreement
        if jurist.verdict_label == "standard" and benchmarker.verdict == "outlier":
            return True
        if jurist.verdict_label in ["predatory", "unenforceable"] and benchmarker.verdict == "market_standard":
            return True
        return False

    def _reconcile(self, jurist, benchmarker, clause_id) -> str:
        """Reconcile inter-agent disagreement."""
        if jurist.verdict_label == "standard" and benchmarker.verdict == "outlier":
            return "Clause is legally standard per Indian law but statistically rare in market. " \
                   "Proceed with awareness that this is an outlier, but not legally risky."
        if jurist.verdict_label in ["predatory", "unenforceable"] and benchmarker.verdict == "market_standard":
            return "Clause is legally risky despite being market-common. The 'market standard' may reflect " \
                   "power imbalance, not fairness. Recommend renegotiation to reduce legal risk."
        return "Agents aligned — no reconciliation needed."

    def _generate_synthesis(self, conflicts: List[Conflict], points: List[str]) -> str:
        """Generate final synthesis summary."""
        if not conflicts:
            return "All agents agree on clause assessments. Contract review complete with no major inter-agent disagreements."

        summary = f"Review complete. {len(conflicts)} inter-agent disagreements were identified and reconciled:\n"
        for point in points:
            summary += f"- {point}\n"
        return summary

    def _extract_key_risks(self) -> List[str]:
        """Extract key risks from all verdicts."""
        risks = []
        for clause_id, verdict in self.state.jurist_verdicts.items():
            if verdict.severity == "high":
                risks.append(f"Clause {clause_id}: {verdict.reasons[0] if verdict.reasons else 'High risk'}")
        return risks[:5]  # Top 5

    def _extract_recommendations(self) -> List[str]:
        """Extract recommended actions from rewrites."""
        recommendations = []
        for clause_id, rewrite in self.state.rewrites.items():
            if rewrite.proposed_text != rewrite.original_text:
                recommendations.append(
                    f"Clause {clause_id}: {rewrite.rationale[:100]}"
                )
        return recommendations[:5]

    def _hits_walk_away(self, analysis, params) -> bool:
        """Check if analysis hits walk-away thresholds."""
        if not params or not params.walk_away_thresholds:
            return False
        # Simplified check
        return False

    def _is_acceptable(self, analysis, params) -> bool:
        """Check if counterparty offer is acceptable."""
        # Simplified — in real implementation, compare to user's must-haves
        return False
