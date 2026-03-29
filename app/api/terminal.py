"""
Terminal WebSocket — PTY-backed interactive terminal via xterm.js.

Architecture:
  Client → WebSocket → PTY (bash/claude) → bidirectional byte stream

Security:
  - Requires valid GILBERTUS_API_KEY via query param or first message
  - Admin-only (role_level >= 99 implied by API key match)
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import termios
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException
from starlette.websockets import WebSocketState
import structlog

router = APIRouter(prefix="/terminal", tags=["terminal"])
log = structlog.get_logger()

GILBERTUS_API_KEY = os.getenv("GILBERTUS_API_KEY", "")
WORKING_DIR = "/home/sebastian/personal-ai"

# In-memory session tracking
_active_sessions: dict[str, dict[str, Any]] = {}


def _verify_api_key(provided: str) -> bool:
    """Check API key against env. In dev mode (no key set), allow all."""
    if not GILBERTUS_API_KEY:
        return True
    return provided == GILBERTUS_API_KEY


@router.get("/sessions")
async def list_sessions(request: Request):
    """List active terminal sessions (audit endpoint)."""
    provided = (
        request.headers.get("X-API-Key")
        or request.headers.get("Authorization", "").removeprefix("Bearer ")
        or request.query_params.get("api_key", "")
    )
    if not _verify_api_key(provided):
        raise HTTPException(status_code=401, detail="Unauthorized")

    sessions = []
    for sid, info in _active_sessions.items():
        sessions.append({
            "session_id": sid,
            "started_at": info.get("started_at"),
            "pid": info.get("pid"),
            "cmd": info.get("cmd"),
            "status": "active",
        })
    return {"sessions": sessions}


@router.websocket("/ws")
async def terminal_ws(websocket: WebSocket):
    """Bidirectional PTY WebSocket stream."""
    # --- Auth via query param ---
    api_key = websocket.query_params.get("api_key", "")
    cmd = websocket.query_params.get("cmd", "bash")

    await websocket.accept()

    # If no api_key in query param, expect it as first message
    if not api_key:
        try:
            first_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            try:
                parsed = json.loads(first_msg)
                api_key = parsed.get("api_key", "")
            except (json.JSONDecodeError, AttributeError):
                api_key = first_msg.strip()
        except asyncio.TimeoutError:
            await websocket.close(code=4003, reason="Auth timeout")
            return

    if not _verify_api_key(api_key):
        log.warning("terminal_auth_failed", reason="invalid_api_key")
        await websocket.close(code=4003, reason="Invalid API key")
        return

    session_id = str(uuid.uuid4())
    master_fd = None
    child_pid = None

    try:
        # Spawn PTY
        master_fd, slave_fd = pty.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        # Determine shell command
        if cmd == "claude":
            shell_cmd = ["claude"]
        else:
            shell_cmd = ["/bin/bash", "--login"]

        child_pid = os.fork()

        if child_pid == 0:
            # Child process
            os.close(master_fd)
            os.setsid()

            # Set slave as controlling terminal
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)

            if slave_fd > 2:
                os.close(slave_fd)

            os.chdir(WORKING_DIR)
            os.execvpe(shell_cmd[0], shell_cmd, env)

        # Parent process
        os.close(slave_fd)

        _active_sessions[session_id] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "pid": child_pid,
            "cmd": cmd,
            "master_fd": master_fd,
        }

        log.info("terminal_session_started", session_id=session_id, pid=child_pid, cmd=cmd)

        # Set master_fd to non-blocking
        import fcntl as _fcntl
        flags = _fcntl.fcntl(master_fd, _fcntl.F_GETFL)
        _fcntl.fcntl(master_fd, _fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Read loop: master_fd → WebSocket
        async def read_pty():
            loop = asyncio.get_event_loop()
            while True:
                try:
                    data = await loop.run_in_executor(None, _blocking_read, master_fd)
                    if data:
                        await websocket.send_bytes(data)
                    else:
                        # EOF — process exited
                        break
                except OSError:
                    break
                except Exception:
                    break

        # Write loop: WebSocket → master_fd
        async def write_pty():
            while True:
                try:
                    msg = await websocket.receive()
                except WebSocketDisconnect:
                    break

                if msg.get("type") == "websocket.disconnect":
                    break

                if "text" in msg:
                    text = msg["text"]
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict) and parsed.get("type") == "resize":
                            cols = parsed.get("cols", 80)
                            rows = parsed.get("rows", 24)
                            _set_winsize(master_fd, rows, cols)
                            continue
                    except (json.JSONDecodeError, ValueError):
                        pass
                    os.write(master_fd, text.encode("utf-8"))

                elif "bytes" in msg and msg["bytes"]:
                    os.write(master_fd, msg["bytes"])

        # Run both loops concurrently
        read_task = asyncio.create_task(read_pty())
        write_task = asyncio.create_task(write_pty())

        done, pending = await asyncio.wait(
            [read_task, write_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    except WebSocketDisconnect:
        log.info("terminal_ws_disconnected", session_id=session_id)
    except Exception as exc:
        log.error("terminal_error", session_id=session_id, error=str(exc))
    finally:
        # Cleanup
        _active_sessions.pop(session_id, None)

        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass

        if child_pid and child_pid > 0:
            try:
                os.kill(child_pid, signal.SIGTERM)
                # Give it a moment, then force kill
                await asyncio.sleep(0.5)
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    os.waitpid(child_pid, os.WNOHANG)
                except ChildProcessError:
                    pass
            except OSError:
                pass

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass

        log.info("terminal_session_ended", session_id=session_id)


def _blocking_read(fd: int, bufsize: int = 4096) -> bytes | None:
    """Blocking read from PTY master fd. Returns None on EOF."""
    import select as _select
    try:
        rlist, _, _ = _select.select([fd], [], [], 0.1)
        if rlist:
            return os.read(fd, bufsize)
        return b""
    except OSError:
        return None


def _set_winsize(fd: int, rows: int, cols: int):
    """Set terminal window size via ioctl."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
