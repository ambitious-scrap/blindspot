"""Blindspot — Orchestration Graph."""

import asyncio
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

    def _run_agent(self, name: str, state: BlindspotState):
        """Run one agent against shared state and return its mutation."""
        self.agents[name].set_state(state)
        return self.agents[name].run()

    def _apply_result(self, state: BlindspotState, result):
        """Apply state mutation dict to shared state."""
        for key, value in result.items():
            setattr(state, key, value)

    async def arun_with_events(self, initial_state: BlindspotState):
        """Execute with SSE event emission."""
        state = initial_state

        # Scout
        yield {"event": "scout_start", "data": {}}
        result = self._run_agent("scout", state)
        self._apply_result(state, result)
        clauses_data = _jsonable(state.scout_output.clauses) if state.scout_output else []
        yield {"event": "scout_complete", "data": {"clauses": clauses_data}}

        # Planner
        await asyncio.sleep(1)
        yield {"event": "chief_counsel_start", "data": {"mode": "planner"}}
        self.agents["chief_counsel"].set_state(state)
        plan = self.agents["chief_counsel"].run_planner()
        state.plan = plan
        yield {"event": "chief_counsel_planned", "data": {"plan": _jsonable(plan)}}

        # Investigator, Jurist, Benchmarker
        sequential_agents = ["investigator", "jurist", "benchmarker"]
        for name in sequential_agents:
            yield {"event": f"{name}_start", "data": {}}
            await asyncio.sleep(1)
            result = await asyncio.to_thread(self._run_agent, name, state)
            self._apply_result(state, result)
            
            if name == "investigator":
                yield {
                    "event": "investigator_complete",
                    "data": {"investigator_profile": _jsonable(result.get("investigator_profile"))},
                }
            elif name == "jurist":
                yield {
                    "event": "jurist_complete",
                    "data": {"jurist_verdicts": _jsonable(result.get("jurist_verdicts", {}))},
                }
            elif name == "benchmarker":
                yield {
                    "event": "benchmarker_complete",
                    "data": {"benchmark_scores": _jsonable(result.get("benchmark_scores", {}))},
                }
        # Router
        self.agents["chief_counsel"].set_state(state)
        routing = self.agents["chief_counsel"].run_router()
        state.routing_decision = routing
        yield {"event": "chief_counsel_routed", "data": {"routing_decision": _jsonable(routing)}}

        # Adversary (conditional)
        if routing and routing.clauses_for_adversary:
            await asyncio.sleep(1)
            yield {"event": "adversary_start", "data": {}}
            result = self._run_agent("adversary", state)
            self._apply_result(state, result)
            yield {
                "event": "adversary_complete",
                "data": {"exploits": _jsonable(result.get("exploits", {}))},
            }

        # Negotiator
        await asyncio.sleep(1)
        yield {"event": "negotiator_start", "data": {}}
        result = self._run_agent("negotiator", state)
        self._apply_result(state, result)
        yield {
            "event": "negotiator_complete",
            "data": {
                "rewrites": _jsonable(result.get("rewrites", {})),
                "redlined_docx_path": result.get("redlined_docx_path"),
                "negotiation_email_draft": result.get("negotiation_email_draft"),
            },
        }

        # Reconciler
        self.agents["chief_counsel"].set_state(state)
        reconciliation = self.agents["chief_counsel"].run_reconciler()
        self._apply_result(state, reconciliation)
        yield {"event": "chief_counsel_synthesis", "data": _jsonable(reconciliation.get("final_synthesis", {}))}
        yield {
            "event": "chief_counsel_complete",
            "data": {
                "mode": "reconciler",
                "final_synthesis": _jsonable(reconciliation.get("final_synthesis", {})),
                "inter_agent_conflicts": _jsonable(reconciliation.get("inter_agent_conflicts", [])),
            },
        }
