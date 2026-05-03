"""Blindspot — Negotiator Agent

Synthesizes all prior agent outputs into actionable counter-proposals.
Generates rewrites, redlined .docx, and negotiation email draft.
"""

import json
import re
import logging
from typing import Dict, Any, List
from src.agents.base import BaseAgent
from src.state.schema import (
    BlindspotState, Rewrite, Clause, LegalVerdict,
    BenchmarkResult, ExploitScenario
)
from src.tools.docx_generator import DocxRedliner
from src.tools.email_renderer import EmailRenderer
from src.config import settings


logger = logging.getLogger(__name__)


class NegotiatorAgent(BaseAgent):
    """Counter-proposal drafting — synthesizes all agent outputs."""

    name = "negotiator"
    description = "Counter-proposal drafting — rewrites, redline, email"

    def run(self) -> Dict[str, Any]:
        if not self.state:
            raise ValueError("State not set")

        clauses = self.state.scout_output.clauses if self.state.scout_output else []
        jurist_verdicts = self.state.jurist_verdicts
        benchmark_scores = self.state.benchmark_scores
        exploits = self.state.exploits

        rewrites = {}
        for clause in clauses:
            rewrite = self._synthesize_rewrite(
                clause,
                jurist_verdicts.get(clause.id),
                benchmark_scores.get(clause.id),
                exploits.get(clause.id, []),
            )
            rewrites[clause.id] = rewrite

        # Generate redlined .docx
        redline_path = self._generate_redline(clauses, rewrites)

        # Generate negotiation email draft
        email_draft = self._generate_email(rewrites)

        return {
            "rewrites": rewrites,
            "redlined_docx_path": redline_path,
            "negotiation_email_draft": email_draft,
        }

    def _synthesize_rewrite(
        self,
        clause: Clause,
        verdict: LegalVerdict,
        score: BenchmarkResult,
        exploit_scenarios: List[ExploitScenario],
    ) -> Rewrite:
        """Create rewrite based on all prior analysis using LLM."""

        if verdict and verdict.verdict_label == "standard" and (not score or score.verdict == "market_standard"):
            # Standard clause — no rewrite needed
            return Rewrite(
                original_text=clause.text,
                proposed_text=clause.text,
                rationale="Clause is market standard. No rewrite needed.",
                fallback_text=clause.text,
                walk_away_threshold="Not applicable — standard clause",
            )

        system = """You are the Negotiator Agent. Your task is to rewrite a problematic clause based on legal analysis and benchmarks.
Output a JSON object with:
{
  "proposed_text": "string (the primary rewrite to propose)",
  "rationale": "string (brief explanation of the change)",
  "fallback_text": "string (a compromise version if counterparty pushes back)",
  "walk_away_threshold": "string (at what point we should abandon negotiation on this point)"
}"""
        
        prompt = f"Clause Type: {clause.clause_type}\nOriginal Text: {clause.text}\n"
        if verdict:
            prompt += f"Jurist Verdict: {verdict.verdict_label} (Severity: {verdict.severity})\n"
            prompt += f"Jurist Reasons: {verdict.reasons}\n"
        if score:
            prompt += f"Benchmarker Score: {score.deviation_score} ({score.verdict})\n"
        if exploit_scenarios:
            prompt += f"Exploits: {[e.scenario_description for e in exploit_scenarios]}\n"

        try:
            resp = self.call_llm(prompt, system=system, temperature=0.2)
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return Rewrite(
                    original_text=clause.text,
                    proposed_text=data.get("proposed_text", clause.text),
                    rationale=data.get("rationale", "Revised based on legal analysis."),
                    fallback_text=data.get("fallback_text", clause.text),
                    walk_away_threshold=data.get("walk_away_threshold", "Unacceptable terms.")
                )
        except Exception as e:
            logger.error(f"Negotiator LLM failed for clause {clause.id}: {e}")
        
        # Fallback if LLM fails
        return Rewrite(
            original_text=clause.text,
            proposed_text=f"[REVISED] {clause.text[:100]}...",
            rationale="Revision required based on legal/benchmark analysis.",
            fallback_text=clause.text,
            walk_away_threshold="Unacceptable clause terms"
        )

    def _generate_redline(self, clauses: List[Clause], rewrites: Dict[str, Rewrite]) -> str:
        """Generate redlined .docx file."""
        try:
            generator = DocxRedliner()
            return generator.create_redline(
                clauses, rewrites,
                output_path=settings.redline_output_path
            )
        except Exception as exc:
            logger.warning("Redline generation failed: %s", exc)
            return None

    def _generate_email(self, rewrites: Dict[str, Rewrite]) -> str:
        """Generate negotiation email draft."""
        renderer = EmailRenderer()
        return renderer.render_email(
            rewrites,
            user_role=self.state.user_role,
            counterparty=self.state.counterparty_info.name,
        )
