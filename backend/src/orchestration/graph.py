"""Blindspot v2.0 — Orchestration Graph."""

from pydantic import BaseModel
from src.state.schema import BlindspotState
from src.agents.scout import ScoutAgent
from src.agents.investigator import InvestigatorAgent
from src.agents.jurist import JuristAgent
from src.agents.benchmarker import BenchmarkerAgent
from src.agents.adversary import AdversaryAgent
from src.agents.negotiator import NegotiatorAgent
from src.agents.chief_counsel import ChiefCounselAgent


def _jsonable(obj):
    """Recursively coerce Pydantic models / containers to JSON-safe primitives."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


class BlindspotGraph:
    """Orchestration for initial contract review."""

    def __init__(self):
        self.agents = {
            "scout": ScoutAgent(),
            "investigator": InvestigatorAgent(),
            "jurist": JuristAgent(),
            "benchmarker": BenchmarkerAgent(),
            "adversary": AdversaryAgent(),
            "negotiator": NegotiatorAgent(),
            "chief_counsel": ChiefCounselAgent(),
        }

    def run(self, initial_state: BlindspotState) -> BlindspotState:
        """Execute agents sequentially."""
        state = initial_state

        # Scout
        self.agents["scout"].set_state(state)
        result = self.agents["scout"].run()
        for k, v in result.items():
            setattr(state, k, v)

        # Chief Counsel Planner
        self.agents["chief_counsel"].set_state(state)
        plan = self.agents["chief_counsel"].run_planner()
        state.plan = plan

        # Investigator, Jurist, Benchmarker (parallel simulation)
        for name in ["investigator", "jurist", "benchmarker"]:
            self.agents[name].set_state(state)
            result = self.agents[name].run()
            for k, v in result.items():
                setattr(state, k, v)

        # Chief Counsel Router
        self.agents["chief_counsel"].set_state(state)
        routing = self.agents["chief_counsel"].run_router()
        state.routing_decision = routing

        # Adversary (conditional)
        if routing and routing.clauses_for_adversary:
            self.agents["adversary"].set_state(state)
            result = self.agents["adversary"].run()
            for k, v in result.items():
                setattr(state, k, v)

        # Negotiator
        self.agents["negotiator"].set_state(state)
        result = self.agents["negotiator"].run()
        for k, v in result.items():
            setattr(state, k, v)

        # Chief Counsel Reconciler
        self.agents["chief_counsel"].set_state(state)
        reconciliation = self.agents["chief_counsel"].run_reconciler()
        for k, v in reconciliation.items():
            setattr(state, k, v)

        return state

    async def arun_with_events(self, initial_state: BlindspotState):
        """Execute with SSE event emission."""
        state = initial_state

        # Scout
        yield {"event": "scout_start", "data": ""}
        self.agents["scout"].set_state(state)
        result = self.agents["scout"].run()
        for k, v in result.items():
            setattr(state, k, v)
        clauses_data = _jsonable(state.scout_output.clauses) if state.scout_output else []
        yield {"event": "scout_complete", "data": {"clauses": clauses_data}}

        # Planner
        self.agents["chief_counsel"].set_state(state)
        plan = self.agents["chief_counsel"].run_planner()
        state.plan = plan

        # Investigator
        yield {"event": "investigator_start", "data": ""}
        self.agents["investigator"].set_state(state)
        result = self.agents["investigator"].run()
        for k, v in result.items():
            setattr(state, k, v)
        yield {"event": "investigator_complete", "data": _jsonable(result.get("investigator_profile", {}))}

        # Jurist
        yield {"event": "jurist_start", "data": ""}
        self.agents["jurist"].set_state(state)
        result = self.agents["jurist"].run()
        for k, v in result.items():
            setattr(state, k, v)
        yield {"event": "jurist_complete", "data": {"verdicts": len(result.get("jurist_verdicts", {}))}}

        # Benchmarker
        yield {"event": "benchmarker_start", "data": ""}
        self.agents["benchmarker"].set_state(state)
        result = self.agents["benchmarker"].run()
        for k, v in result.items():
            setattr(state, k, v)
        yield {"event": "benchmarker_complete", "data": {"scores": len(result.get("benchmark_scores", {}))}}

        # Router
        self.agents["chief_counsel"].set_state(state)
        routing = self.agents["chief_counsel"].run_router()
        state.routing_decision = routing

        # Adversary (conditional)
        if routing and routing.clauses_for_adversary:
            yield {"event": "adversary_start", "data": ""}
            self.agents["adversary"].set_state(state)
            result = self.agents["adversary"].run()
            for k, v in result.items():
                setattr(state, k, v)
            yield {"event": "adversary_complete", "data": _jsonable(result.get("exploits", {}))}

        # Negotiator
        yield {"event": "negotiator_start", "data": ""}
        self.agents["negotiator"].set_state(state)
        result = self.agents["negotiator"].run()
        for k, v in result.items():
            setattr(state, k, v)
        yield {"event": "negotiator_complete", "data": {"rewrites": len(result.get("rewrites", {}))}}

        # Reconciler
        self.agents["chief_counsel"].set_state(state)
        reconciliation = self.agents["chief_counsel"].run_reconciler()
        for k, v in reconciliation.items():
            setattr(state, k, v)
        yield {"event": "chief_counsel_synthesis", "data": _jsonable(reconciliation.get("final_synthesis", {}))}

        yield {"event": "final_report", "data": {"status": "complete"}}
