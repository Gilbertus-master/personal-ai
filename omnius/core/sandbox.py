"""Omnius Sandbox Manager — Docker container lifecycle for plugin development.

Creates isolated containers with Plugin SDK, no network access,
limited resources, and no secrets. Plugins are developed inside
the sandbox and extracted as tar archives.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import docker
import docker.errors
import structlog

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

SANDBOX_IMAGE = "omnius-sandbox:latest"
SANDBOX_NETWORK = "sandbox-net"
DOCKERFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "sandbox", "Dockerfile.sandbox")
BUILD_CONTEXT = os.path.join(os.path.dirname(__file__), "..")
MAX_SANDBOX_MINUTES = 30


class SandboxManager:
    """Manages Docker sandbox containers for plugin development."""

    def __init__(self):
        self.client = docker.from_env()
        log.info("sandbox_manager_init")

    def _ensure_image(self) -> None:
        """Build sandbox image if it doesn't exist."""
        try:
            self.client.images.get(SANDBOX_IMAGE)
            log.debug("sandbox_image_exists", image=SANDBOX_IMAGE)
        except docker.errors.ImageNotFound:
            log.info("sandbox_image_building", image=SANDBOX_IMAGE)
            self.client.images.build(
                path=os.path.abspath(BUILD_CONTEXT),
                dockerfile="sandbox/Dockerfile.sandbox",
                tag=SANDBOX_IMAGE,
                rm=True,
            )
            log.info("sandbox_image_built", image=SANDBOX_IMAGE)

    def _ensure_network(self) -> None:
        """Create dedicated sandbox network if it doesn't exist.

        This network is internal-only (no internet access) and only
        connects sandbox containers to the proxy service.
        """
        try:
            self.client.networks.get(SANDBOX_NETWORK)
        except docker.errors.NotFound:
            self.client.networks.create(
                SANDBOX_NETWORK,
                driver="bridge",
                internal=True,  # No internet access
                labels={"omnius.role": "sandbox"},
            )
            log.info("sandbox_network_created", network=SANDBOX_NETWORK)

    def create_sandbox(
        self,
        session_id: str,
        plugin_name: str,
        proxy_port: int = 8099,
    ) -> dict:
        """Create and start a sandboxed container for plugin development.

        Args:
            session_id: Unique session identifier.
            plugin_name: Name of the plugin being developed.
            proxy_port: Port of the sandbox proxy (default 8099).

        Returns:
            Dict with session_id, container_id, status, started_at.
        """
        container_name = f"omnius-sandbox-{session_id}"

        try:
            self._ensure_image()
            self._ensure_network()

            # Render CLAUDE.md template
            template_path = os.path.join(
                os.path.dirname(__file__), "..", "sandbox", "CLAUDE.md.template"
            )
            with open(template_path) as f:
                claude_md = f.read().replace("{{ plugin_name }}", plugin_name)

            container = self.client.containers.create(
                image=SANDBOX_IMAGE,
                name=container_name,
                hostname="sandbox",
                # Network: internal sandbox-net only (no internet)
                network=SANDBOX_NETWORK,
                # Security: drop all capabilities
                cap_drop=["ALL"],
                # Read-only root filesystem
                read_only=True,
                # Writable tmpfs for /tmp and /workspace
                tmpfs={
                    "/tmp": "size=100M",
                    "/workspace": "size=200M",
                },
                # Resource limits
                mem_limit="512m",
                cpu_period=100000,
                cpu_quota=100000,  # 1 CPU
                pids_limit=100,
                # Security options
                security_opt=["no-new-privileges:true"],
                # Environment (NO secrets)
                environment={
                    "PLUGIN_NAME": plugin_name,
                    "SANDBOX_SESSION_ID": session_id,
                    "SANDBOX_PROXY_URL": f"http://sandbox-proxy:{proxy_port}",
                },
                # Keep container running
                stdin_open=True,
                tty=True,
                # Labels for identification
                labels={
                    "omnius.role": "sandbox",
                    "omnius.session_id": session_id,
                    "omnius.plugin_name": plugin_name,
                },
            )

            container.start()

            # Write CLAUDE.md into the container workspace
            import tarfile
            import io

            tar_buf = io.BytesIO()
            with tarfile.open(fileobj=tar_buf, mode="w") as tar:
                data = claude_md.encode("utf-8")
                info = tarfile.TarInfo(name="CLAUDE.md")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            tar_buf.seek(0)
            container.put_archive("/workspace", tar_buf)

            started_at = datetime.now(timezone.utc)

            # Record in DB
            try:
                with get_pg_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO omnius_sandbox_sessions
                                (id, plugin_name, container_id, status, started_at)
                            VALUES (%s, %s, %s, 'running', %s)
                            ON CONFLICT (id) DO UPDATE
                            SET container_id = EXCLUDED.container_id,
                                status = 'running',
                                started_at = EXCLUDED.started_at
                        """, (session_id, plugin_name, container.id, started_at))
                    conn.commit()
            except Exception as db_err:
                log.error("sandbox_db_record_failed", error=str(db_err),
                          session_id=session_id)

            log.info("sandbox_created", session_id=session_id,
                     container_id=container.short_id, plugin_name=plugin_name)

            return {
                "session_id": session_id,
                "container_id": container.id,
                "status": "running",
                "started_at": started_at.isoformat(),
            }

        except Exception as e:
            log.error("sandbox_create_failed", error=str(e),
                      session_id=session_id)
            # Clean up on failure
            try:
                c = self.client.containers.get(container_name)
                c.stop(timeout=5)
                c.remove(force=True)
            except Exception:
                pass
            raise

    async def exec_in_sandbox(
        self, session_id: str, command: str
    ) -> AsyncGenerator[str, None]:
        """Execute a command inside the sandbox container.

        Args:
            session_id: Session identifier.
            command: Shell command to execute.

        Yields:
            Stdout chunks as strings.
        """
        container_name = f"omnius-sandbox-{session_id}"
        try:
            container = self.client.containers.get(container_name)
            exec_result = container.exec_run(
                cmd=["bash", "-c", command],
                stream=True,
                demux=True,
                user="sandbox",
                workdir="/workspace",
            )
            for stdout_chunk, stderr_chunk in exec_result.output:
                if stdout_chunk:
                    yield stdout_chunk.decode("utf-8", errors="replace")
                if stderr_chunk:
                    yield stderr_chunk.decode("utf-8", errors="replace")

            log.debug("sandbox_exec", session_id=session_id,
                      command=command[:100])
        except docker.errors.NotFound:
            log.error("sandbox_not_found", session_id=session_id)
            yield f"Error: sandbox {session_id} not found\n"
        except Exception as e:
            log.error("sandbox_exec_failed", error=str(e),
                      session_id=session_id)
            yield f"Error: {e}\n"

    def destroy_sandbox(self, session_id: str) -> dict:
        """Stop and remove a sandbox container.

        Args:
            session_id: Session identifier.

        Returns:
            Dict with session_id and status.
        """
        container_name = f"omnius-sandbox-{session_id}"
        try:
            container = self.client.containers.get(container_name)
            container.stop(timeout=10)
            container.remove(force=True)
            log.info("sandbox_destroyed", session_id=session_id)
        except docker.errors.NotFound:
            log.warning("sandbox_already_gone", session_id=session_id)
        except Exception as e:
            log.error("sandbox_destroy_failed", error=str(e),
                      session_id=session_id)

        # Update DB
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE omnius_sandbox_sessions
                        SET status = 'destroyed', completed_at = NOW()
                        WHERE id = %s
                    """, (session_id,))
                conn.commit()
        except Exception as db_err:
            log.error("sandbox_db_update_failed", error=str(db_err),
                      session_id=session_id)

        return {"session_id": session_id, "status": "destroyed"}

    def collect_output(self, session_id: str) -> bytes:
        """Extract plugin output from the sandbox as a tar.gz archive.

        Args:
            session_id: Session identifier.

        Returns:
            Tar archive bytes from /workspace/output/.
        """
        container_name = f"omnius-sandbox-{session_id}"
        try:
            container = self.client.containers.get(container_name)
            # Ensure output directory exists
            container.exec_run(
                cmd=["mkdir", "-p", "/workspace/output"],
                user="sandbox",
            )
            archive_data, _ = container.get_archive("/workspace/output/")
            log.info("sandbox_output_collected", session_id=session_id)
            return archive_data.read() if hasattr(archive_data, "read") else archive_data
        except docker.errors.NotFound:
            log.error("sandbox_not_found", session_id=session_id)
            return b""
        except Exception as e:
            log.error("sandbox_collect_failed", error=str(e),
                      session_id=session_id)
            return b""

    def get_sandbox_status(self, session_id: str) -> dict:
        """Get current status of a sandbox container.

        Args:
            session_id: Session identifier.

        Returns:
            Dict with session info and container status.
        """
        container_name = f"omnius-sandbox-{session_id}"
        try:
            container = self.client.containers.get(container_name)
            attrs = container.attrs
            started_at_str = attrs.get("State", {}).get("StartedAt", "")
            uptime = 0.0
            if started_at_str and container.status == "running":
                # Parse Docker ISO timestamp
                started = datetime.fromisoformat(
                    started_at_str.replace("Z", "+00:00")
                )
                uptime = (datetime.now(timezone.utc) - started).total_seconds()

            return {
                "session_id": session_id,
                "container_id": container.id,
                "status": container.status,
                "uptime_seconds": round(uptime, 1),
            }
        except docker.errors.NotFound:
            return {
                "session_id": session_id,
                "container_id": None,
                "status": "not_found",
                "uptime_seconds": 0,
            }
        except Exception as e:
            log.error("sandbox_status_failed", error=str(e),
                      session_id=session_id)
            return {
                "session_id": session_id,
                "container_id": None,
                "status": "error",
                "uptime_seconds": 0,
            }

    def list_sandboxes(self) -> list[dict]:
        """List all active sandbox containers.

        Returns:
            List of dicts with container info.
        """
        try:
            containers = self.client.containers.list(
                filters={"label": "omnius.role=sandbox"},
                all=True,
            )
            result = []
            for c in containers:
                result.append({
                    "session_id": c.labels.get("omnius.session_id", "unknown"),
                    "plugin_name": c.labels.get("omnius.plugin_name", "unknown"),
                    "container_id": c.id,
                    "status": c.status,
                    "name": c.name,
                })
            return result
        except Exception as e:
            log.error("sandbox_list_failed", error=str(e))
            return []

    def _cleanup_expired(self) -> int:
        """Stop and remove sandbox containers running beyond the timeout.

        Returns:
            Number of containers cleaned up.
        """
        cleaned = 0
        try:
            containers = self.client.containers.list(
                filters={"label": "omnius.role=sandbox", "status": "running"},
            )
            now = datetime.now(timezone.utc)
            for container in containers:
                started_at_str = container.attrs.get("State", {}).get("StartedAt", "")
                if not started_at_str:
                    continue
                started = datetime.fromisoformat(
                    started_at_str.replace("Z", "+00:00")
                )
                runtime_minutes = (now - started).total_seconds() / 60.0

                if runtime_minutes > MAX_SANDBOX_MINUTES:
                    session_id = container.labels.get("omnius.session_id", "unknown")
                    log.warning("sandbox_timeout", session_id=session_id,
                                runtime_minutes=round(runtime_minutes, 1))
                    try:
                        container.stop(timeout=10)
                        container.remove(force=True)
                        cleaned += 1

                        # Update DB
                        with get_pg_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    UPDATE omnius_sandbox_sessions
                                    SET status = 'timeout', completed_at = NOW()
                                    WHERE id = %s AND status = 'running'
                                """, (session_id,))
                            conn.commit()
                    except Exception as e:
                        log.error("sandbox_cleanup_container_failed",
                                  error=str(e), session_id=session_id)
        except Exception as e:
            log.error("sandbox_cleanup_failed", error=str(e))

        if cleaned:
            log.info("sandbox_cleanup_done", cleaned=cleaned)
        return cleaned
