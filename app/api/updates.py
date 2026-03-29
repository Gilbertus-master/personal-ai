import json
import os
import structlog
from pathlib import Path
from packaging.version import Version
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/updates", tags=["updates"])
log = structlog.get_logger()

RELEASES_DIR = Path(__file__).parent / "releases"

GILBERTUS_API_KEY = os.getenv("GILBERTUS_API_KEY", "")


class PublishRequest(BaseModel):
    version: str
    notes: str
    pub_date: str
    platforms: dict


def _load_release(app_name: str) -> dict | None:
    """Load release JSON for given app. Returns None if file missing."""
    path = RELEASES_DIR / f"{app_name}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error("release_file_read_error", app_name=app_name, error=str(e))
        return None


@router.get("/{app_name}/{target}/{arch}/{current_version}")
async def check_update(app_name: str, target: str, arch: str, current_version: str):
    """
    Tauri updater endpoint.
    Returns update JSON if newer version available, 204 otherwise.
    """
    release = _load_release(app_name)
    if release is None:
        return Response(status_code=204)

    try:
        current = Version(current_version)
        latest = Version(release["version"])
    except Exception:
        log.warning("version_parse_error", app_name=app_name, current=current_version)
        return Response(status_code=204)

    if current >= latest:
        return Response(status_code=204)

    # Build Tauri-compatible platform key
    platform_key = f"{target}-{arch}"

    # Build response with platform-specific info if available
    platforms = release.get("platforms", {})
    response_platforms = {}
    if platform_key in platforms:
        response_platforms[platform_key] = platforms[platform_key]

    log.info(
        "update_available",
        app_name=app_name,
        current=str(current),
        latest=str(latest),
        target=target,
        arch=arch,
    )

    return {
        "version": release["version"],
        "notes": release.get("notes", ""),
        "pub_date": release.get("pub_date", ""),
        "platforms": response_platforms,
    }


@router.get("/{app_name}/latest")
async def get_latest(app_name: str):
    """Return latest version info for given app."""
    release = _load_release(app_name)
    if release is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Not found", "detail": f"No release info for {app_name}"},
        )
    return {
        "version": release["version"],
        "notes": release.get("notes", ""),
        "pub_date": release.get("pub_date", ""),
    }


@router.post("/{app_name}/publish")
async def publish_release(app_name: str, req: PublishRequest, request: Request):
    """
    Publish a new release. Requires API key auth (handled by global middleware).
    """
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)

    release_data = {
        "version": req.version,
        "notes": req.notes,
        "pub_date": req.pub_date,
        "platforms": req.platforms,
    }

    path = RELEASES_DIR / f"{app_name}.json"
    with open(path, "w") as f:
        json.dump(release_data, f, indent=2, ensure_ascii=False)

    log.info(
        "release_published",
        app_name=app_name,
        version=req.version,
        platforms=list(req.platforms.keys()),
    )

    return {"status": "published", "app_name": app_name, "version": req.version}
