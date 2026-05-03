"""Blindspot — Chief Counsel Agent

Orchestration meta-agent operating in four modes:
1. Planner — after Scout, decides which downstream agents to run
2. Router — after Jurist+Benchmarker, decides which clauses need Adversary
3. Reconciler — before final synthesis, surfaces inter-agent disagreements
4. Negotiation Strategist — during negotiation, decides auto-respond/escalate/close
"""

import json
import re
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
        num_clauses = len(self.state.scout_output.clauses)

        system = """You are the Chief Counsel. Your task is to plan the review strategy.
Given the document type and number of clauses, provide reasoning for why we must run Jurist, Benchmarker, and Investigator.

Output a JSON object:
{
  "reasoning": "string (brief justification for running the parallel agents)"
}"""
        prompt = f"Doc type: {doc_type}\nClauses: {num_clauses}"
        
        try:
            resp = self.call_llm(prompt, system=system, temperature=0.1)
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            reasoning = json.loads(match.group()).get("reasoning", "Standard execution plan.") if match else "Standard execution plan."
        except Exception:
            reasoning = "Executing standard parallel review."

        return ExecutionPlan(
            agents_to_run=["jurist", "benchmarker", "investigator"],
            parallel_groups=[["jurist", "benchmarker", "investigator"]],
            reasoning=reasoning,
        )

    def run_router(self) -> RoutingDecision:
        """Mode 2: Decide which clauses warrant Adversary analysis via LLM."""
        if not self.state:
            raise ValueError("State not set")

        system = """You are the Chief Counsel Router. Review the Jurist verdicts and Benchmarker scores for the clauses.
Decide which clause IDs require Adversary (red-team) analysis.
Flag clauses that are high/medium severity OR non-standard/outlier.

Output a JSON object:
{
  "clauses_for_adversary": ["clause_id_1", "clause_id_2"],
  "reasoning": "string (brief explanation of why these were flagged)"
}"""
        
        verdicts_summary = {
            cid: {
                "jurist_severity": v.severity, 
                "benchmarker_verdict": self.state.benchmark_scores[cid].verdict if cid in self.state.benchmark_scores else "unknown"
            }
            for cid, v in self.state.jurist_verdicts.items()
        }

        prompt = f"Clause Analysis Summaries:\n{json.dumps(verdicts_summary, indent=2)}"

        try:
            resp = self.call_llm(prompt, system=system, temperature=0.1)
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            if match:
                data = json.loads(match.group())
                flagged = data.get("clauses_for_adversary", [])
                reasoning = data.get("reasoning", "Flagged clauses for adversary.")
            else:
                raise ValueError()
        except Exception:
            # Fallback heuristic
            flagged = [
                cid for cid, v in self.state.jurist_verdicts.items() 
                if v.severity in ["high", "medium"] or 
                (cid in self.state.benchmark_scores and self.state.benchmark_scores[cid].verdict in ["non_standard", "outlier"])
            ]
            reasoning = "Automated fallback routing based on severity."

        return RoutingDecision(
            clauses_for_adversary=flagged,
            reasoning=reasoning,
        )

    def run_reconciler(self) -> Dict[str, Any]:
        """Mode 3: Identify and reconcile inter-agent disagreements via LLM."""
        if not self.state:
            raise ValueError("State not set")

        system = """You are the Chief Counsel Reconciler. Analyze Jurist verdicts vs Benchmarker scores to find conflicts.
A conflict occurs when Jurist says 'standard' but Benchmarker says 'outlier', or Jurist says 'predatory' but Benchmarker says 'market_standard'.
If there are conflicts, provide a reconciliation strategy for each.

Output a JSON object:
{
  "conflicts": [
    {
      "clause_id": "string",
      "reconciliation": "string (how to resolve this disagreement for the user)"
    }
  ],
  "synthesis_summary": "string (overall summary of the contract's risk profile)"
}"""

        verdicts_summary = {
            cid: {
                "jurist": self.state.jurist_verdicts[cid].verdict_label,
                "benchmarker": self.state.benchmark_scores[cid].verdict if cid in self.state.benchmark_scores else "unknown"
            }
            for cid in self.state.jurist_verdicts
        }

        prompt = f"Verdicts:\n{json.dumps(verdicts_summary, indent=2)}"

        conflicts = []
        try:
            resp = self.call_llm(prompt, system=system, temperature=0.1)
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            if match:
                data = json.loads(match.group())
                for c in data.get("conflicts", []):
                    cid = c.get("clause_id")
                    if cid in self.state.jurist_verdicts:
                        j_label = self.state.jurist_verdicts[cid].verdict_label
                        b_label = self.state.benchmark_scores[cid].verdict if cid in self.state.benchmark_scores else "unknown"
                        conflicts.append(Conflict(
                            clause_id=cid,
                            agent_a="Jurist",
                            agent_b="Benchmarker",
                            verdict_a=j_label,
                            verdict_b=b_label,
                            reconciliation=c.get("reconciliation", "Resolved by Chief Counsel.")
                        ))
                summary = data.get("synthesis_summary", "Review complete.")
            else:
                raise ValueError()
        except Exception:
            # Fallback
            summary = "Automated fallback synthesis."

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
        """Mode 4: Decide auto-respond / escalate / close via LLM."""
        
        system = """You are the Chief Counsel Strategist. Review the counterparty's latest response.
Determine if we should 'auto_respond', 'escalate' (if it hits a walk-away threshold), or 'close' (if terms are acceptable).

Output JSON:
{
  "decision": "auto_respond" | "escalate" | "close",
  "reasoning": "string"
}"""
        prompt = f"Inbound Analysis: {json.dumps(inbound_analysis)}\nUser Params: {user_params}"
        
        try:
            resp = self.call_llm(prompt, system=system, temperature=0.1)
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return NegotiationDecision(
                    decision=data.get("decision", "auto_respond"),
                    reasoning=data.get("reasoning", "Proceeding with negotiation."),
                    escalation_details=None
                )
        except Exception:
            pass

        return NegotiationDecision(
            decision="auto_respond",
            reasoning="Fallback decision.",
            escalation_details=None,
        )

    def _extract_key_risks(self) -> List[str]:
        """Extract key risks from all verdicts."""
        risks = []
        for clause_id, verdict in self.state.jurist_verdicts.items():
            if verdict.severity == "high":
                risks.append(f"Clause {clause_id}: {verdict.reasons[0] if verdict.reasons else 'High risk'}")
        return risks[:5]

    def _extract_recommendations(self) -> List[str]:
        """Extract recommended actions from rewrites."""
        recommendations = []
        if self.state.rewrites:
            for clause_id, rewrite in self.state.rewrites.items():
                if rewrite.proposed_text != rewrite.original_text:
                    recommendations.append(
                        f"Clause {clause_id}: {rewrite.rationale[:100]}"
                    )
        return recommendations[:5]
