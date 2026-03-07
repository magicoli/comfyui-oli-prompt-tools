"""
Run a ComfyUI workflow from the terminal and print string outputs.

Expects a workflow in **API format** (export via Save > Save (API format) in
ComfyUI with Dev Mode enabled) — not the default LiteGraph workflow format.

Usage:
    python tmp/run_workflow.py tmp/my-workflow-api.json [--url https://localhost:18188]

Polls the history endpoint until the prompt completes, then prints every
STRING output value found in the results.
"""

import argparse
import json
import ssl
import time
import urllib.request
import urllib.error
from pathlib import Path


def _ctx():
    """SSL context that skips cert verification (self-signed on dev server)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def api(base_url, path, data=None):
    """GET or POST to the ComfyUI API; return parsed JSON."""
    url = base_url.rstrip("/") + path
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_ctx(), timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:2000]}") from None


def run(workflow_path, base_url):
    workflow = json.loads(Path(workflow_path).read_text())

    # Queue the prompt
    resp = api(base_url, "/prompt", {"prompt": workflow})
    prompt_id = resp["prompt_id"]
    print(f"Queued  prompt_id={prompt_id}")

    # Poll history until done
    for attempt in range(120):  # up to 60 s
        time.sleep(0.5)
        hist = api(base_url, f"/history/{prompt_id}")
        if prompt_id not in hist:
            continue
        entry = hist[prompt_id]
        status = entry.get("status", {})
        if not status.get("completed"):
            msgs = status.get("messages", [])
            if msgs:
                print(f"  [{attempt}] {msgs[-1]}")
            continue

        # Completed — collect outputs
        outputs = entry.get("outputs", {})
        found = False
        for node_id, node_out in outputs.items():
            for key, vals in node_out.items():
                for v in (vals if isinstance(vals, list) else [vals]):
                    if isinstance(v, str):
                        print(f"  node {node_id} · {key}: {v!r}")
                        found = True
        if not found:
            print("  (no string outputs found in results)")
        return

    print("Timed out waiting for completion.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow", help="Path to workflow JSON")
    ap.add_argument("--url", default="https://localhost:18188", help="ComfyUI base URL")
    args = ap.parse_args()
    run(args.workflow, args.url)
