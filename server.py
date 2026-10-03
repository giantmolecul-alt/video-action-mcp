import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from starlette.routing import Mount

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings


# ============================================================
# CONFIGURATION
# ============================================================

APP_NAME = "Video Action MCP"
APP_VERSION = "0.1.0"

MCP_PATH_SECRET = os.getenv("MCP_PATH_SECRET", "").strip()

if not MCP_PATH_SECRET:
    raise RuntimeError("MCP_PATH_SECRET is required")


# ============================================================
# MCP SERVER
# ============================================================

mcp = MCPServer(
    APP_NAME,
    version=APP_VERSION,
    instructions=(
        "Controlled tools for the Video Action Agent. "
        "Analyze video observations and prepare proposed actions. "
        "Never claim an external action occurred unless a tool "
        "explicitly returns success."
    ),
)


# ============================================================
# IN-MEMORY DECISION STORAGE
# ============================================================

DECISIONS: list[dict[str, Any]] = []


# ============================================================
# TOOL 1 — ANALYZE VIDEO EVENT
# ============================================================

@mcp.tool()
def analyze_video_event(
    timestamp: str,
    observation: str,
    interpretation: str,
    confidence: float,
) -> dict[str, Any]:
    """
    Record a visual event identified from a video.

    This tool does NOT execute any external action.
    """

    confidence = max(0.0, min(1.0, float(confidence)))

    return {
        "success": True,
        "type": "video_event",
        "timestamp": timestamp,
        "observation": observation,
        "interpretation": interpretation,
        "confidence": confidence,
    }


# ============================================================
# TOOL 2 — SAVE DECISION
# ============================================================

@mcp.tool()
def save_decision(
    action: str,
    reason: str,
    confidence: float,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    """
    Save a proposed action.

    This does NOT execute the action.
    """

    confidence = max(0.0, min(1.0, float(confidence)))

    record = {
        "id": len(DECISIONS) + 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "reason": reason,
        "confidence": confidence,
        "evidence": evidence or [],
        "status": "PROPOSED_ONLY",
    }

    DECISIONS.append(record)

    return {
        "success": True,
        "decision": record,
    }


# ============================================================
# TOOL 3 — GET SAVED DECISIONS
# ============================================================

@mcp.tool()
def get_decisions() -> dict[str, Any]:
    """
    Return decisions saved during this server lifetime.
    """

    return {
        "success": True,
        "count": len(DECISIONS),
        "decisions": DECISIONS[-50:],
    }


# ============================================================
# TOOL 4 — VALIDATE ACTION
# ============================================================

@mcp.tool()
def validate_action(
    action: str,
    authorized: bool,
    confidence: float,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    """
    Validate a proposed action without executing it.

    An action is considered validated only when:
    - explicit authorization is true
    - confidence is at least 0.80
    - evidence is supplied
    """

    confidence = max(0.0, min(1.0, float(confidence)))

    approved = (
        bool(authorized)
        and confidence >= 0.80
        and bool(evidence)
    )

    return {
        "success": True,
        "action": action,
        "validated": approved,
        "status": (
            "READY_FOR_SEPARATE_EXECUTION"
            if approved
            else "REJECTED"
        ),
        "reason": (
            "Authorization, confidence and evidence requirements satisfied."
            if approved
            else
            "Requires explicit authorization, confidence >= 0.80, "
            "and evidence."
        ),
    }


# ============================================================
# MCP STREAMABLE HTTP APPLICATION
# ============================================================

mcp_app = mcp.streamable_http_app(
    # IMPORTANT:
    # Because the MCP application is mounted at:
    # /mcp/<SECRET>
    #
    # "/" makes that mount itself the MCP endpoint.
    #
    # Therefore Claude connects to:
    #
    # https://video-action-mcp.onrender.com/mcp/<SECRET>/
    #
    streamable_http_path="/",

    json_response=True,

    stateless_http=True,

    transport_security=TransportSecuritySettings(
        allowed_hosts=[
            "video-action-mcp.onrender.com",
            "video-action-mcp.onrender.com:*",
        ],
        allowed_origins=[
            "https://video-action-mcp.onrender.com",
        ],
    ),
)


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Start the MCP session manager.

    This is required because the MCP application is mounted
    inside the parent FastAPI application.
    """

    async with mcp.session_manager.run():
        yield


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
)


# ============================================================
# MCP ROUTE
# ============================================================

app.router.routes.append(
    Mount(
        f"/mcp/{MCP_PATH_SECRET}",
        app=mcp_app,
    )
)


# ============================================================
# HEALTH / STATUS ROUTES
# ============================================================

@app.get("/")
async def root():
    """
    Public service status.

    IMPORTANT:
    The MCP secret is intentionally NOT returned here.
    """

    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "online",
    }


@app.get("/health")
async def health():
    """
    Simple health check.
    """

    return {
        "status": "ok"
    }
