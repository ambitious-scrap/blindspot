"""Blindspot — Updated API with Gemini + Real SSE Streaming"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Dict, Any
from pathlib import Path

from src.state.schema import BlindspotState, DealContext, CounterpartyInfo
from src.orchestration.graph import BlindspotGraph
from src.retrieval.retriever import get_retriever
from src.config import settings

# In-memory store for negotiation state (for demo purposes)
ACTIVE_ANALYSES: Dict[str, BlindspotState] = {}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler("/tmp/backend.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(file_handler)

app = FastAPI(title="Blindspot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "Blindspot", "status": "running", "models": {
        "jurist": settings.gemini_pro_model,
        "adversary": settings.gemini_flash_model,
    }, "live_llm_enabled": settings.llm_enabled}


@app.on_event("startup")
async def startup():
    """Initialize corpus retrieval before first request."""
    await asyncio.to_thread(get_retriever)


@app.post("/api/v1/analyze")
async def analyze_contract(
    file: UploadFile = File(...),
    metadata: str = Form("{}")
):
    """Analyze uploaded contract. Returns SSE stream of agent events."""

    # Parse metadata
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        meta = {}

    # Read file content
    content = await file.read()
    source_format = file.filename.split(".")[-1].lower() if file.filename else "txt"

    logger.info("Processing file: %s, format: %s, size: %s bytes", file.filename, source_format, len(content))

    # Extract text based on format
    contract_text = ""
    if source_format == "pdf":
        try:
            from pypdf import PdfReader
            from io import BytesIO
            reader = PdfReader(BytesIO(content))
            contract_text = ""
            for page in reader.pages:
                contract_text += page.extract_text() or ""
            logger.info("PDF parsed: %s chars extracted", len(contract_text))
        except Exception as e:
            logger.error("PDF parsing failed: %s", e)
            raise HTTPException(400, f"PDF parsing failed: {e}")
    elif source_format == "docx":
        try:
            from docx import Document as DocxDocument
            from io import BytesIO
            doc = DocxDocument(BytesIO(content))
            contract_text = "\n".join([p.text for p in doc.paragraphs])
            logger.info("DOCX parsed: %s chars extracted", len(contract_text))
        except Exception as e:
            logger.error("DOCX parsing failed: %s", e)
            raise HTTPException(400, f"DOCX parsing failed: {e}")
    else:
        contract_text = content.decode("utf-8", errors="ignore")
        logger.info("Text file loaded: %s chars", len(contract_text))

    # Initialize state
    state = BlindspotState(
        contract_text=contract_text,
        source_format=source_format,
        user_role=meta.get("role", "freelancer"),
        deal_context=DealContext(**meta.get("deal_context", {})),
        counterparty_info=CounterpartyInfo(**meta.get("counterparty_info", {})),
    )

    # Create orchestration graph
    graph = BlindspotGraph()

    async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
        """Stream events from LangGraph execution."""
        started = time.perf_counter()
        
        # Yield the document text immediately so frontend can render it
        yield {
            "event": "document_parsed",
            "data": json.dumps({"text": contract_text})
        }
        
        try:
            async for event in graph.arun_with_events(state):
                if isinstance(event, dict):
                    event_type = event.get("event", "update")
                    event_data = event.get("data", {})
                    yield {
                        "event": event_type,
                        "data": json.dumps(event_data)
                    }

            # Final event
            state.processing_ms = int((time.perf_counter() - started) * 1000)
            analysis_id = "an_" + str(uuid.uuid4())[:8]
            ACTIVE_ANALYSES[analysis_id] = state
            
            yield {
                "event": "final_report",
                "data": json.dumps({
                    "status": "complete",
                    "analysis_id": analysis_id,
                    "processing_ms": state.processing_ms,
                    "redlined_docx_path": state.redlined_docx_path,
                })
            }

        except Exception as e:
            logger.exception("Analysis failed")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())


@app.post("/api/v1/negotiate/start")
async def start_negotiation(body: Dict[str, Any]):
    """Start negotiation mode with user parameters."""
    analysis_id = body.get("analysis_id", "demo")
    return {
        "negotiation_id": analysis_id,
        "initial_outbound_email_id": "email_001",
        "status": "awaiting_counterparty"
    }


@app.post("/api/v1/negotiate/{negotiation_id}/inbound")
async def inbound_email(negotiation_id: str, body: Dict[str, Any]):
    """Inject inbound email for negotiation round."""
    return {
        "round_number": 1,
        "decision": "auto_respond",
        "status": "responding"
    }


@app.get("/api/v1/negotiate/{negotiation_id}/stream")
async def negotiate_stream(negotiation_id: str):
    """SSE stream for negotiation updates."""

    async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
        state = ACTIVE_ANALYSES.get(negotiation_id)
        
        outbound_msg = "Initial counter-proposal sent based on agent rewrites."
        inbound_reply = "Counterparty replied. They rejected the kill fee but agreed to 30-day notice."
        decision_reasoning = "Within walk-away thresholds. Dropping kill fee but holding on notice period."
        compromise_msg = "Compromise drafted and sent automatically."
        
        if state and "negotiator" in state.agent_states:
            rewrites = state.agent_states["negotiator"].get("rewrites", {})
            if rewrites:
                issues = list(rewrites.keys())
                outbound_msg = f"Initial counter-proposal sent incorporating rewrites for: {', '.join(issues[:2])}."
                if len(issues) > 0:
                    inbound_reply = f"Counterparty replied. They pushed back on the proposed rewrite for {issues[0]} but agreed to the other terms."
                    decision_reasoning = f"Evaluating counter-proposal on {issues[0]}. Our walk-away thresholds allow a compromise here."
                    compromise_msg = f"Compromise drafted for {issues[0]} and sent automatically."

        # Initial state: Outbound email sent
        yield {
            "event": "outbound_sent",
            "data": json.dumps({"round": 1, "message": outbound_msg})
        }
        await asyncio.sleep(4)
        
        # Round 2: Counterparty replies
        yield {
            "event": "inbound_received",
            "data": json.dumps({"round": 2, "message": inbound_reply})
        }
        await asyncio.sleep(2)
        
        # Agents evaluate
        yield {
            "event": "decision",
            "data": json.dumps({"round": 2, "decision": "auto_respond", "reasoning": decision_reasoning})
        }
        await asyncio.sleep(2)
        
        # Auto-response sent
        yield {
            "event": "outbound_sent",
            "data": json.dumps({"round": 2, "message": compromise_msg})
        }
        await asyncio.sleep(4)
        
        # Round 3: Counterparty agrees
        yield {
            "event": "inbound_received",
            "data": json.dumps({"round": 3, "message": "Counterparty agrees to all terms. Ready for signature."})
        }
        await asyncio.sleep(2)
        
        # Final decision
        yield {
            "event": "decision",
            "data": json.dumps({"round": 3, "decision": "close", "reasoning": "All terms acceptable."})
        }

    return EventSourceResponse(event_generator())


@app.post("/api/v1/negotiate/{negotiation_id}/respond_to_escalation")
async def respond_escalation(negotiation_id: str, body: Dict[str, Any]):
    """User responds to escalation."""
    return {"status": "resumed", "decision": body.get("user_decision", "counter")}


@app.get("/api/v1/download/{redline_id}")
async def download_redline(redline_id: str):
    """Download redlined .docx file."""
    path = Path(settings.redline_output_path)
    if redline_id not in {"latest", path.name, path.stem}:
        raise HTTPException(404, "Unknown redline artifact")
    if not path.exists():
        raise HTTPException(404, "Redline artifact not generated yet")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/v1/logs")
async def get_logs(lines: int = 50):
    """Return recent backend logs (development only)."""
    try:
        with open('/tmp/backend.log', 'r') as f:
            log_lines = f.readlines()
            return {"logs": log_lines[-lines:]}
    except OSError as e:
        return {"logs": [f"Could not read logs: {e}"]}


if __name__ == "__main__":
    import uvicorn
    from src.config import settings
    uvicorn.run("src.api.main:app", host=settings.api_host, port=settings.api_port, reload=True)
