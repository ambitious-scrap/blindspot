# Blindspot — Architecture Decisions

## Framework Choices

### Backend: FastAPI + Python
- **Reason**: FastAPI provides native async support and SSE via sse-starlette. Pydantic v2 for state modeling with minimal boilerplate.

### State Management: Pydantic Models
- **Reason**: Shared mutable state object using Pydantic v2 for validation, serialization, and type safety across all agents.

### Vector Database: ChromaDB
- **Reason**: Lightweight, embeddable vector store that requires no external infrastructure. Supports cosine similarity search with metadata filtering.

### Agent Orchestration: LangGraph-style State Graph
- **Reason**: Enables parallel execution (Jurist + Benchmarker), conditional edges (Adversary only if risky clauses), and state joining.

## Key Design Decisions

1. **Shared Mutable State**: All agents read/write to a single BlindspotState object. This enables transparency (UI shows all agent outputs) and reconciliation (Chief Counsel compares all verdicts).

2. **Streaming SSE**: Events emitted at each agent completion. No blocking spinners >2s.

3. **Grounded Reasoning**: Jurist agent constrained to cite only corpus entries. Citation validation at output time.

4. **Demo Cache Layer**: Hard-coded cached responses for demo contract enable reliable demo even if LLM API fails.
