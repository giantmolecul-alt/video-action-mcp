import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from starlette.routing import Mount

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings


APP_NAME = "Video Action MCP"
APP_VERSION = "0.1.0"

MCP_PATH_SECRET = os.getenv("MCP_PATH_SECRET", "")

if not MCP_PATH_SECRET:
    raise RuntimeError("MCP_PATH_SECRET is required")


mcp = MCPServer(
    APP_NAME,
    version=APP_VERSION,
    instructions=(
        "Controlled tools for the Video Action Agent. "
        "Never claim an external action occurred unless a tool returns success."
    ),
)


DECISIONS: list[dict[str, Any]] = []


@mcp.tool()
def analyze_video_event(
    timestamp: str,
    observation: str,
    interpretation: str,
    confidence: float,
) -> dict[str, Any]:
    """Record a visual event identified from a video. No external action."""
    confidence = max(0.0, min(1.0, float(confidence)))

    return {
        "success": True,
        "type": "video_event",
        "timestamp": timestamp,
        "observation": observation,
        "interpretation": interpretation,
        "confidence": confidence,
    }


@mcp.tool()
def save_decision(
    action: str,
    reason: str,
    confidence: float,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Save a proposed action. This does not execute it."""

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


@mcp.tool()
def get_decisions() -> dict[str, Any]:
    """Return decisions saved during this server lifetime."""

    return {
        "success": True,
        "count": len(DECISIONS),
        "decisions": DECISIONS[-50:],
    }


@mcp.tool()
def validate_action(
    action: str,
    authorized: bool,
    confidence: float,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Validate a proposed action without executing it."""

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


# Build the MCP application first.
mcp_app = mcp.streamable_http_app(
    stateless_http=True,
    json_response=True,
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


# IMPORTANT:
# Because mcp_app is mounted inside FastAPI, the parent application
# must run the MCP session manager.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
)


# MCP endpoint:
# /mcp/<MCP_PATH_SECRET>
app.router.routes.append(
    Mount(
        f"/mcp/{MCP_PATH_SECRET}",
        app=mcp_app,
    )
)


@app.get("/")
async def root():
    # Do NOT expose the secret here.
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "online",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }
