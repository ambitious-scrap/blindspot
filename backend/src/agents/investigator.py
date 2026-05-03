"""Blindspot — Investigator Agent

Counterparty intelligence using publicly available data sources.
"""

import hashlib
from typing import Dict, Any
from src.agents.base import BaseAgent
from src.state.schema import CounterpartyProfile, RiskTier, BlindspotState
from src.config import settings


class InvestigatorAgent(BaseAgent):
    """Builds counterparty profile from public data sources."""

    name = "investigator"
    description = "Counterparty intelligence — risk profiling"

    def run(self) -> Dict[str, Any]:
        if not self.state:
            raise ValueError("State not set")

        counterparty = self.state.counterparty_info
        profile = self._investigate(counterparty)

        return {"investigator_profile": profile}

    def _investigate(self, counterparty_info) -> CounterpartyProfile:
        """Investigate counterparty using available data sources or mock data."""
        
        # In demo or mock mode, return the pre-determined profile
        if settings.investigator_mock_mode or settings.demo_mode:
            return CounterpartyProfile(
                risk_tier=RiskTier.CAUTION,
                risk_score=45,
                litigation_summary=["2 prior disputes in court records"],
                pattern_flags=["history of invoking IP assignment clauses against contractors", "4 recent Reddit complaints about IP grabs"],
                data_confidence="high",
                sources_consulted=["Indian Kanoon", "Reddit", "MCA"]
            )
            
        # TODO: Implement real investigation using public APIs
        # For now, return a basic profile with low confidence
        return CounterpartyProfile(
            risk_tier=RiskTier.STANDARD,
            risk_score=40,
            litigation_summary=[],
            pattern_flags=[],
            data_confidence="low",
            sources_consulted=[],
        )
