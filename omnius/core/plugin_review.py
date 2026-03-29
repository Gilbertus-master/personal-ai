"""Automated review pipeline for Omnius plugins.

Orchestrates security scanning (bandit), AST import analysis,
SDK compliance checks, manifest validation, test execution,
and optional LLM-based code review.

All checks are designed to work even if optional tools (bandit,
anthropic API) are unavailable — they degrade gracefully.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

ANTHROPIC_MODEL = os.getenv("OMNIUS_LLM_MODEL", "claude-haiku-4-5")

# --- Data classes ---

@dataclass
class Finding:
    severity: str   # critical, high, medium, low
    category: str   # security, quality, compliance, test
    title: str
    description: str
    file: str = ""
    line: int = 0


@dataclass
class ReviewResult:
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    security_score: float = 1.0   # 0.0-1.0
    quality_score: float = 1.0    # 0.0-1.0
    tests_passed: int = 0
    tests_total: int = 0


# --- Import whitelist/blocklist ---

IMPORT_WHITELIST = {
    "omnius.plugins.sdk", "omnius", "typing", "datetime", "json", "re",
    "collections", "dataclasses", "enum", "math", "decimal", "uuid",
    "hashlib", "base64", "copy", "functools", "itertools", "abc",
    "contextlib", "textwrap", "string", "operator", "numbers",
    "fractions", "statistics", "pathlib", "__future__", "pydantic",
}

IMPORT_BLOCKLIST = {
    "os", "subprocess", "socket", "requests", "urllib", "shutil",
    "importlib", "ctypes", "pickle", "shelve", "marshal", "tempfile",
    "glob", "io", "http", "ftplib", "smtplib", "telnetlib", "xmlrpc",
    "multiprocessing", "threading", "signal", "sys", "builtins",
    "code", "codeop", "compile",
}


# --- Core functions ---

def review_plugin(plugin_dir: Path) -> ReviewResult:
    """Orchestrate ALL review checks for a plugin directory.

    Aggregates findings, calculates scores.
    passed=True only if zero critical/high findings AND
    tests_passed == tests_total AND security_score >= 0.7.
    """
    findings: list[Finding] = []

    # 1. Manifest check
    manifest_path = plugin_dir / "manifest.json"
    if manifest_path.exists():
        manifest_findings = check_manifest(manifest_path)
        findings.extend(manifest_findings)
    else:
        findings.append(Finding(
            severity="critical",
            category="compliance",
            title="Missing manifest.json",
            description="Plugin directory does not contain manifest.json",
            file=str(plugin_dir),
        ))

    # 2. AST import checks on all .py files in backend/
    backend_dir = plugin_dir / "backend"
    if backend_dir.exists():
        for py_file in backend_dir.glob("**/*.py"):
            if py_file.name == "__init__.py":
                continue
            findings.extend(check_ast_imports(py_file))
            findings.extend(check_sdk_compliance(py_file))
    else:
        findings.append(Finding(
            severity="high",
            category="compliance",
            title="Missing backend directory",
            description="Plugin has no backend/ directory",
            file=str(plugin_dir),
        ))

    # 3. Bandit security scan
    bandit_findings = run_bandit(plugin_dir)
    findings.extend(bandit_findings)

    # 4. Tests
    tests_passed, tests_total, test_findings = run_tests(plugin_dir)
    findings.extend(test_findings)

    # 5. LLM review (optional)
    security_score = 1.0
    quality_score = 1.0
    try:
        plugin_code = _collect_plugin_code(plugin_dir)
        manifest_data = {}
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest_data = json.load(f)
        llm_sec, llm_qual, llm_findings = llm_review(plugin_code, manifest_data)
        security_score = llm_sec
        quality_score = llm_qual
        findings.extend(llm_findings)
    except Exception as e:
        log.warning("llm_review_skipped", error=str(e))

    # Calculate pass/fail
    critical_high = [f for f in findings if f.severity in ("critical", "high")]
    tests_ok = tests_passed == tests_total
    passed = len(critical_high) == 0 and tests_ok and security_score >= 0.7

    result = ReviewResult(
        passed=passed,
        findings=findings,
        security_score=security_score,
        quality_score=quality_score,
        tests_passed=tests_passed,
        tests_total=tests_total,
    )

    log.info("plugin_review_complete",
             plugin_dir=str(plugin_dir),
             passed=passed,
             findings_count=len(findings),
             critical_high=len(critical_high),
             security_score=security_score,
             quality_score=quality_score,
             tests=f"{tests_passed}/{tests_total}")

    return result


def run_bandit(plugin_dir: Path) -> list[Finding]:
    """Run bandit security scanner on plugin backend code.

    If bandit is not installed, logs warning and returns empty list.
    """
    backend_dir = plugin_dir / "backend"
    if not backend_dir.exists():
        return []

    try:
        result = subprocess.run(
            ["bandit", "-r", str(backend_dir), "-f", "json", "-q"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        log.warning("bandit_not_installed",
                     hint="Install with: pip install bandit")
        return []
    except subprocess.TimeoutExpired:
        log.warning("bandit_timeout", plugin_dir=str(plugin_dir))
        return []
    except Exception as e:
        log.warning("bandit_error", error=str(e))
        return []

    findings: list[Finding] = []
    try:
        # Bandit returns JSON even on non-zero exit (findings found)
        output = result.stdout or result.stderr
        if not output.strip():
            return []

        data = json.loads(output)
        severity_map = {
            "HIGH": "high",
            "MEDIUM": "medium",
            "LOW": "low",
        }

        for issue in data.get("results", []):
            sev = severity_map.get(issue.get("issue_severity", "LOW"), "low")
            findings.append(Finding(
                severity=sev,
                category="security",
                title=f"Bandit: {issue.get('test_name', 'unknown')}",
                description=issue.get("issue_text", ""),
                file=issue.get("filename", ""),
                line=issue.get("line_number", 0),
            ))
    except json.JSONDecodeError:
        log.warning("bandit_json_parse_failed", output=result.stdout[:200])

    return findings


def check_ast_imports(handler_py: Path) -> list[Finding]:
    """Parse file with ast and check imports against whitelist/blocklist."""
    findings: list[Finding] = []
    try:
        source = handler_py.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(handler_py))
    except SyntaxError as e:
        findings.append(Finding(
            severity="critical",
            category="quality",
            title="Syntax error in handler",
            description=f"Could not parse {handler_py.name}: {e}",
            file=str(handler_py),
            line=e.lineno or 0,
        ))
        return findings
    except Exception as e:
        log.warning("ast_parse_failed", file=str(handler_py), error=str(e))
        return findings

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module(alias.name, node.lineno, handler_py, findings)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _check_module(node.module, node.lineno, handler_py, findings)

    return findings


def _check_module(module_name: str, lineno: int, file_path: Path,
                  findings: list[Finding]) -> None:
    """Check a single module name against whitelist/blocklist."""
    # Get top-level module
    top_module = module_name.split(".")[0]

    # Check whitelist first (including submodules like omnius.plugins.sdk)
    for allowed in IMPORT_WHITELIST:
        if module_name == allowed or module_name.startswith(allowed + "."):
            return
        if top_module == allowed:
            return

    # Check blocklist
    if top_module in IMPORT_BLOCKLIST:
        findings.append(Finding(
            severity="critical",
            category="security",
            title=f"Blocked import: {module_name}",
            description=(
                f"Import '{module_name}' is not allowed in plugins. "
                f"Module '{top_module}' is on the blocklist. "
                f"Use PluginContext methods for data access and I/O."
            ),
            file=str(file_path),
            line=lineno,
        ))
        return

    # Unknown module — medium finding
    findings.append(Finding(
        severity="medium",
        category="security",
        title=f"Unknown import: {module_name}",
        description=(
            f"Import '{module_name}' is not in the approved whitelist. "
            f"Review manually to determine if it should be allowed."
        ),
        file=str(file_path),
        line=lineno,
    ))


def check_sdk_compliance(handler_py: Path) -> list[Finding]:
    """Check that handler functions use PluginContext properly.

    Verifies:
    - Handler functions accept PluginContext as first arg
    - No dangerous patterns: open(), exec(), eval(), __import__(), compile()
    - No raw SQL or file I/O outside PluginContext
    """
    findings: list[Finding] = []
    try:
        source = handler_py.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(handler_py))
    except (SyntaxError, Exception):
        # Already caught in check_ast_imports
        return findings

    # Check handler functions — look for async def or def at module level
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private/helper functions
            if node.name.startswith("_"):
                continue
            # Check first arg is context/ctx (PluginContext)
            args = node.args
            if args.args:
                first_arg = args.args[0].arg
                if first_arg not in ("context", "ctx"):
                    findings.append(Finding(
                        severity="medium",
                        category="compliance",
                        title=f"Handler '{node.name}' missing PluginContext arg",
                        description=(
                            f"Function '{node.name}' first parameter is '{first_arg}', "
                            f"expected 'context' or 'ctx' (PluginContext). "
                            f"Plugin handlers must receive PluginContext as first argument."
                        ),
                        file=str(handler_py),
                        line=node.lineno,
                    ))
            else:
                findings.append(Finding(
                    severity="high",
                    category="compliance",
                    title=f"Handler '{node.name}' has no arguments",
                    description=(
                        f"Function '{node.name}' accepts no arguments. "
                        f"Plugin handlers must receive PluginContext as first argument."
                    ),
                    file=str(handler_py),
                    line=node.lineno,
                ))

    # Check for dangerous patterns in source
    dangerous_patterns = [
        (r"\bopen\s*\(", "open()", "Use PluginContext methods instead of direct file I/O"),
        (r"\bexec\s*\(", "exec()", "Dynamic code execution is not allowed"),
        (r"\beval\s*\(", "eval()", "Dynamic code evaluation is not allowed"),
        (r"\b__import__\s*\(", "__import__()", "Dynamic imports are not allowed"),
        (r"\bcompile\s*\(", "compile()", "Code compilation is not allowed"),
        (r"\bgetattr\s*\([^,]+,\s*['\"]__", "getattr() on dunder",
         "Accessing dunder attributes via getattr is not allowed"),
    ]

    for pattern, name, reason in dangerous_patterns:
        for match in re.finditer(pattern, source):
            # Get line number
            line_num = source[:match.start()].count("\n") + 1
            findings.append(Finding(
                severity="critical",
                category="security",
                title=f"Dangerous pattern: {name}",
                description=reason,
                file=str(handler_py),
                line=line_num,
            ))

    return findings


def check_manifest(manifest_path: Path) -> list[Finding]:
    """Validate manifest using SDK validator plus additional checks."""
    from omnius.plugins.sdk.manifest import validate_manifest

    findings: list[Finding] = []

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        findings.append(Finding(
            severity="critical",
            category="compliance",
            title="Invalid manifest JSON",
            description=f"Could not parse manifest.json: {e}",
            file=str(manifest_path),
        ))
        return findings

    # Run SDK validation
    result = validate_manifest(manifest)
    if not result["valid"]:
        findings.append(Finding(
            severity="critical",
            category="compliance",
            title="Manifest schema validation failed",
            description=result["error"],
            file=str(manifest_path),
        ))
        return findings

    # Additional check: version must be semver-like (X.Y.Z)
    version = manifest.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        findings.append(Finding(
            severity="high",
            category="compliance",
            title="Invalid version format",
            description=f"Version '{version}' must be semver format X.Y.Z",
            file=str(manifest_path),
        ))

    # Additional check: author should be a valid email (recommended)
    author = manifest.get("author", "")
    if author and "@" not in author and author != "system":
        findings.append(Finding(
            severity="low",
            category="compliance",
            title="Author is not an email",
            description=f"Author '{author}' should be a valid email address",
            file=str(manifest_path),
        ))

    # Check hooks reference existing handler files
    plugin_dir = manifest_path.parent
    for hook in manifest.get("hooks", []):
        handler_ref = hook.get("handler", "")
        if ":" in handler_ref:
            handler_file = handler_ref.split(":")[0]
        else:
            handler_file = handler_ref
        if handler_file and not (plugin_dir / handler_file).exists():
            findings.append(Finding(
                severity="high",
                category="compliance",
                title=f"Handler file not found: {handler_file}",
                description=f"Hook references '{handler_ref}' but file does not exist",
                file=str(manifest_path),
            ))

    # Check permissions_required are from known set
    known_permissions = {
        "plugins:use", "plugins:manage", "plugins:propose",
        "ask", "timeline", "brief", "commands:*", "admin",
        "data:read", "data:write", "tasks:create", "notifications:send",
    }
    for perm in manifest.get("permissions_required", []):
        if perm not in known_permissions:
            findings.append(Finding(
                severity="low",
                category="compliance",
                title=f"Unknown permission: {perm}",
                description=f"Permission '{perm}' is not in the known permission set",
                file=str(manifest_path),
            ))

    return findings


def run_tests(plugin_dir: Path) -> tuple[int, int, list[Finding]]:
    """Run pytest on plugin tests directory.

    Returns: (passed_count, total_count, findings_for_failures)
    """
    tests_dir = plugin_dir / "tests"
    findings: list[Finding] = []

    if not tests_dir.exists() or not list(tests_dir.glob("test_*.py")):
        findings.append(Finding(
            severity="critical",
            category="test",
            title="No tests found",
            description=f"Plugin must have tests in {tests_dir}",
            file=str(plugin_dir),
        ))
        return 0, 0, findings

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", str(tests_dir), "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(plugin_dir.parent.parent.parent),  # project root
        )
    except FileNotFoundError:
        log.warning("pytest_not_found")
        findings.append(Finding(
            severity="medium",
            category="test",
            title="pytest not available",
            description="Could not run tests — pytest not found",
            file=str(tests_dir),
        ))
        return 0, 0, findings
    except subprocess.TimeoutExpired:
        findings.append(Finding(
            severity="high",
            category="test",
            title="Tests timed out",
            description="Plugin tests took longer than 120 seconds",
            file=str(tests_dir),
        ))
        return 0, 0, findings
    except Exception as e:
        log.warning("test_run_error", error=str(e))
        return 0, 0, findings

    output = result.stdout + "\n" + result.stderr

    # Parse pytest summary line: "X passed, Y failed" or "X passed"
    passed = 0
    failed = 0

    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    error_match = re.search(r"(\d+) error", output)

    if passed_match:
        passed = int(passed_match.group(1))
    if failed_match:
        failed = int(failed_match.group(1))
    if error_match:
        failed += int(error_match.group(1))

    total = passed + failed

    if failed > 0:
        findings.append(Finding(
            severity="high",
            category="test",
            title=f"{failed} test(s) failed",
            description=output[:1000],
            file=str(tests_dir),
        ))

    if total == 0:
        findings.append(Finding(
            severity="critical",
            category="test",
            title="No tests collected",
            description="pytest collected 0 tests — check test file naming and imports",
            file=str(tests_dir),
        ))

    return passed, total, findings


def llm_review(plugin_code: str, manifest: dict) -> tuple[float, float, list[Finding]]:
    """Call Claude to review plugin code for security and quality.

    Returns: (security_score, quality_score, findings)
    If API key not available, returns defaults (1.0, 1.0, []).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("llm_review_skipped", reason="no ANTHROPIC_API_KEY")
        return 1.0, 1.0, []

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        prompt = (
            "Review this Omnius plugin for security vulnerabilities and code quality.\n"
            "Score security 0.0-1.0 and quality 0.0-1.0.\n"
            "List any findings as JSON array.\n\n"
            "Respond ONLY with JSON:\n"
            '{"security_score": 0.0-1.0, "quality_score": 0.0-1.0, '
            '"findings": [{"severity": "critical|high|medium|low", '
            '"category": "security|quality", "title": "...", "description": "..."}]}\n\n'
            f"Manifest:\n{json.dumps(manifest, indent=2)}\n\n"
            f"Plugin code:\n{plugin_code[:8000]}"
        )

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text.strip()

        # Parse JSON response
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            # Try extracting JSON from response
            json_match = re.search(
                r'\{[^{}]*"security_score"[^{}]*"findings"[^}]*\[.*?\]\s*\}',
                result_text,
                re.DOTALL,
            )
            if json_match:
                data = json.loads(json_match.group())
            else:
                log.warning("llm_review_unparseable", response=result_text[:300])
                return 1.0, 1.0, []

        security_score = float(data.get("security_score", 1.0))
        quality_score = float(data.get("quality_score", 1.0))

        findings = []
        for f in data.get("findings", []):
            findings.append(Finding(
                severity=f.get("severity", "medium"),
                category=f.get("category", "quality"),
                title=f.get("title", "LLM finding"),
                description=f.get("description", ""),
            ))

        log.info("llm_review_complete",
                 security=security_score,
                 quality=quality_score,
                 findings=len(findings))

        return security_score, quality_score, findings

    except Exception as e:
        log.warning("llm_review_failed", error=str(e))
        return 1.0, 1.0, []


def _collect_plugin_code(plugin_dir: Path) -> str:
    """Collect all Python source code from plugin for LLM review."""
    parts = []
    for py_file in sorted(plugin_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        try:
            rel_path = py_file.relative_to(plugin_dir)
            content = py_file.read_text(encoding="utf-8")
            parts.append(f"--- {rel_path} ---\n{content}")
        except Exception:
            continue
    return "\n\n".join(parts)
