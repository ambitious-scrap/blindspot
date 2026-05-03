"""Blindspot — Shared State Schema

All agents read from and write to BlindspotState.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class ClauseType(str, Enum):
    IP_ASSIGNMENT = "ip_assignment"
    TERMINATION = "termination"
    NON_COMPETE = "non_compete"
    PAYMENT = "payment"
    CONFIDENTIALITY = "confidentiality"
    GOVERNING_LAW = "governing_law"
    INDEMNIFICATION = "indemnification"
    DISPUTE_RESOLUTION = "dispute_resolution"
    FORCE_MAJEURE = "force_majeure"
    OTHER = "other"


class VerdictLabel(str, Enum):
    STANDARD = "standard"
    NON_STANDARD = "non_standard"
    PREDATORY = "predatory"
    UNENFORCEABLE = "unenforceable"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskTier(str, Enum):
    TRUSTED = "trusted"
    STANDARD = "standard"
    CAUTION = "caution"
    HIGH_RISK = "high_risk"


class DocType(str, Enum):
    FREELANCE = "freelance_services_agreement"
    NDA = "nda"
    EMPLOYMENT = "employment_agreement"
    VENDOR_MSA = "vendor_msa"
    UNKNOWN = "unknown"


class NegotiationDecision(str, Enum):
    AUTO_RESPOND = "auto_respond"
    ESCALATE = "escalate"
    CLOSE = "close"


class NegotiationStatus(str, Enum):
    AWAITING_COUNTERPARTY = "awaiting_counterparty"
    ANALYZING = "analyzing"
    RESPONDING = "responding"
    ESCALATED = "escalated"
    CLOSED = "closed"
    ABANDONED = "abandoned"


class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    COMPLETE = "complete"
    ERROR = "error"


# ── Inputs ─────────────────────────────────────────────────────────────────

class DealContext(BaseModel):
    size: Optional[float] = None
    location: str = "India"
    urgency: str = "normal"
    currency: str = "INR"


class CounterpartyInfo(BaseModel):
    name: str = ""
    email: str = ""
    registration_number: str = ""
    jurisdiction: str = "India"


# ── Scout Output ───────────────────────────────────────────────────────────

class Clause(BaseModel):
    id: str
    section_header: Optional[str] = None
    text: str
    position: Dict[str, int]  # {start, end}
    clause_type: ClauseType = ClauseType.OTHER


class ScoutOutput(BaseModel):
    doc_type: DocType
    doc_type_confidence: float = Field(ge=0.0, le=1.0)
    clauses: List[Clause]


# ── Investigator Output ────────────────────────────────────────────────────

class CounterpartyProfile(BaseModel):
    risk_tier: RiskTier
    risk_score: int = Field(ge=0, le=100)
    litigation_summary: List[str] = Field(default_factory=list)
    pattern_flags: List[str] = Field(default_factory=list)
    data_confidence: str = "low"  # low | medium | high
    sources_consulted: List[str] = Field(default_factory=list)


# ── Jurist Output ──────────────────────────────────────────────────────────

class LegalVerdict(BaseModel):
    verdict_label: VerdictLabel
    severity: Severity
    reasons: List[str]
    citations: List[str]  # corpus entry IDs
    enforceability_note: Optional[str] = None


# ── Benchmarker Output ────────────────────────────────────────────────────

class BenchmarkResult(BaseModel):
    deviation_score: float  # 1.0 = median
    comparable_clause_ids: List[str]
    numerical_features_extracted: Dict[str, Any] = Field(default_factory=dict)
    verdict: str  # market_standard | non_standard | outlier
    reasoning: str


# ── Adversary Output ──────────────────────────────────────────────────────

class ExploitScenario(BaseModel):
    scenario_description: str
    severity: Severity
    precedent_link: Optional[str] = None


# ── Negotiator Output ──────────────────────────────────────────────────────

class Rewrite(BaseModel):
    original_text: str
    proposed_text: str
    rationale: str
    fallback_text: str
    walk_away_threshold: str


# ── Chief Counsel Output ──────────────────────────────────────────────────

class ExecutionPlan(BaseModel):
    agents_to_run: List[str]
    parallel_groups: List[List[str]] = Field(default_factory=list)
    reasoning: str


class RoutingDecision(BaseModel):
    clauses_for_adversary: List[str]  # clause IDs
    reasoning: str


class Conflict(BaseModel):
    clause_id: str
    agent_a: str
    agent_b: str
    verdict_a: str
    verdict_b: str
    reconciliation: str


class Synthesis(BaseModel):
    summary: str
    key_risks: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)


class NegotiationDecision(BaseModel):
    decision: NegotiationDecision
    reasoning: str
    escalation_details: Optional[Dict[str, Any]] = None


# ── Negotiation State ─────────────────────────────────────────────────────

class NegotiationParameters(BaseModel):
    must_haves: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    walk_away_thresholds: Dict[str, Any] = Field(default_factory=dict)
    authority_level: str = "balanced"  # conservative | balanced | aggressive
    counterparty_email: str = ""


class NegotiationRound(BaseModel):
    round_number: int
    inbound_email: Dict[str, Any] = Field(default_factory=dict)
    re_analysis: Dict[str, Any] = Field(default_factory=dict)
    outbound_response: Optional[Dict[str, Any]] = None
    decision: str = ""  # auto_respond | escalate | close
    escalation_details: Optional[Dict[str, Any]] = None


# ── Main State Object ──────────────────────────────────────────────────────

class BlindspotState(BaseModel):
    # Inputs
    contract_text: str = ""
    source_format: str = "pdf"
    user_role: str = ""
    deal_context: DealContext = Field(default_factory=DealContext)
    counterparty_info: CounterpartyInfo = Field(default_factory=CounterpartyInfo)

    # Initial Review
    scout_output: Optional[ScoutOutput] = None
    investigator_profile: Optional[CounterpartyProfile] = None
    jurist_verdicts: Dict[str, LegalVerdict] = Field(default_factory=dict)
    benchmark_scores: Dict[str, BenchmarkResult] = Field(default_factory=dict)
    exploits: Dict[str, List[ExploitScenario]] = Field(default_factory=dict)
    rewrites: Dict[str, Rewrite] = Field(default_factory=dict)
    redlined_docx_path: Optional[str] = None
    negotiation_email_draft: Optional[str] = None

    # Chief Counsel
    plan: Optional[ExecutionPlan] = None
    routing_decision: Optional[RoutingDecision] = None
    inter_agent_conflicts: List[Conflict] = Field(default_factory=list)
    final_synthesis: Optional[Synthesis] = None
    negotiation_decisions: List[NegotiationDecision] = Field(default_factory=list)

    # Negotiation
    negotiation_active: bool = False
    negotiation_params: Optional[NegotiationParameters] = None
    rounds: List[NegotiationRound] = Field(default_factory=list)
    current_status: str = ""
    final_contract_state: Optional[str] = None

    # Meta
    created_at: datetime = Field(default_factory=datetime.utcnow)
    analyzer_version: str = "2.0"
    processing_ms: int = 0
    warnings: List[str] = Field(default_factory=list)
