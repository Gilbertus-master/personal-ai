#!/usr/bin/env python3
"""Claude CLI stub for sandbox environments.

Mimics the Claude CLI interface, forwarding requests to the sandbox proxy
which injects the real API key and forwards to Anthropic.

Uses only stdlib — no external dependencies allowed in sandbox.
"""
import json
import os
import sys
import urllib.error
import urllib.request

PROXY_URL = os.getenv("SANDBOX_PROXY_URL", "http://sandbox-proxy:8099")
SESSION_ID = os.getenv("SANDBOX_SESSION_ID", "unknown")


def send_message(prompt: str) -> None:
    """Send a message to the proxy and stream the response to stdout."""
    url = f"{PROXY_URL}/v1/messages"
    payload = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "metadata": {"session_id": SESSION_ID},
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Sandbox-Session": SESSION_ID,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            try:
                data = json.loads(body)
                # Extract text from Anthropic response format
                if "content" in data and isinstance(data["content"], list):
                    for block in data["content"]:
                        if block.get("type") == "text":
                            print(block["text"])
                else:
                    print(body)
            except json.JSONDecodeError:
                print(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Error ({e.code}): {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        print("Proxy not reachable. Check SANDBOX_PROXY_URL.", file=sys.stderr)
        sys.exit(1)
    except TimeoutError:
        print("Request timed out after 120s.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = sys.argv[1:]

    # claude -p "prompt" mode
    if "-p" in args:
        idx = args.index("-p")
        if idx + 1 < len(args):
            prompt = args[idx + 1]
            send_message(prompt)
        else:
            print("Error: -p requires a prompt argument.", file=sys.stderr)
            sys.exit(1)
        return

    # Interactive mode: read lines from stdin
    if not sys.stdin.isatty():
        # Piped input — read all and send
        prompt = sys.stdin.read().strip()
        if prompt:
            send_message(prompt)
        return

    # Interactive TTY mode
    print("Claude Sandbox (type 'exit' to quit)")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().lower() in ("exit", "quit"):
            break
        if line.strip():
            send_message(line.strip())


if __name__ == "__main__":
    main()
