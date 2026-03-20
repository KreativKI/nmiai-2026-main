#!/usr/bin/env python3
"""
NM i AI 2026 — NLP Endpoint Health Checker (shared/tools/check_nlp_endpoint.py)

Tests the Tripletex AI agent endpoint with a sample prompt.
Reports: status, latency, response format compliance.

Usage:
    python3 shared/tools/check_nlp_endpoint.py
    python3 shared/tools/check_nlp_endpoint.py --url https://your-endpoint.run.app/solve
    python3 shared/tools/check_nlp_endpoint.py --json
"""

import argparse
import json
import sys
import time

try:
    import httpx
except ImportError:
    import urllib.request
    import urllib.error
    httpx = None

DEFAULT_URL = "https://tripletex-agent-795548831221.europe-west4.run.app/solve"

SAMPLE_PAYLOADS = [
    {
        "name": "health_check",
        "body": {"prompt": "health check", "task_type": "ping"},
    },
    {
        "name": "basic_create",
        "body": {
            "prompt": "Opprett en kunde med navn Test AS",
            "files": [],
            "tripletex_credentials": {
                "base_url": "https://tx-proxy.ainm.no/v2",
                "session_token": "test-health-check-only",
            },
        },
    },
]


def check_endpoint(url: str) -> dict:
    """Run health checks against the NLP endpoint."""
    result = {
        "url": url,
        "checks": [],
        "overall": "pass",
    }

    for payload in SAMPLE_PAYLOADS:
        check = {"name": payload["name"], "status": "fail", "latency_ms": None, "details": ""}
        body = json.dumps(payload["body"]).encode("utf-8")

        start = time.time()
        try:
            if httpx:
                resp = httpx.post(url, content=body, headers={"Content-Type": "application/json"}, timeout=15)
                status_code = resp.status_code
                resp_text = resp.text
            else:
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                resp = urllib.request.urlopen(req, timeout=15)
                status_code = resp.status
                resp_text = resp.read().decode()
        except Exception as e:
            check["status"] = "fail"
            check["details"] = str(e)
            check["latency_ms"] = round((time.time() - start) * 1000)
            result["overall"] = "fail"
            result["checks"].append(check)
            continue

        latency = round((time.time() - start) * 1000)
        check["latency_ms"] = latency

        if status_code in (200, 422):
            check["status"] = "pass"
            check["details"] = f"HTTP {status_code}, {latency}ms"
            try:
                data = json.loads(resp_text)
                if "status" in data:
                    check["details"] += f", status={data['status']}"
            except (json.JSONDecodeError, ValueError):
                check["details"] += ", non-JSON response"
        else:
            check["status"] = "fail"
            check["details"] = f"HTTP {status_code}, {latency}ms"
            result["overall"] = "fail"

        result["checks"].append(check)

    return result


def main():
    parser = argparse.ArgumentParser(description="Check NLP endpoint health")
    parser.add_argument("--url", default=DEFAULT_URL, help="Endpoint URL")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = check_endpoint(args.url)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "UP" if result["overall"] == "pass" else "DOWN"
        print(f"\nNLP Endpoint: {status}")
        print(f"URL: {result['url']}")
        for c in result["checks"]:
            icon = "PASS" if c["status"] == "pass" else "FAIL"
            print(f"  [{icon}] {c['name']}: {c['details']}")
        print()

    sys.exit(0 if result["overall"] == "pass" else 1)


if __name__ == "__main__":
    main()
