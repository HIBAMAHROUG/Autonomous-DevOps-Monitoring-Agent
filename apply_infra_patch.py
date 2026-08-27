import pathlib

path = pathlib.Path("api/dashboard.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "from flask import Blueprint, jsonify, render_template, request",
        "import requests\n"
        "from flask import Blueprint, jsonify, render_template, request"
    ),
    (
        'dashboard_api = Blueprint("dashboard_api", __name__)',
        'dashboard_api = Blueprint("dashboard_api", __name__)\n'
        '\n'
        'PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")\n'
        '\n'
        'INFRA_QUERIES = {\n'
        '    "cpu_percent": (\n'
        '        \'100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)\'\n'
        '    ),\n'
        '    "memory_percent": (\n'
        '        "(1 - (node_memory_MemAvailable_bytes / "\n'
        '        "node_memory_MemTotal_bytes)) * 100"\n'
        '    ),\n'
        '}\n'
        '\n'
        '\n'
        'def _query_prometheus(expr: str) -> float | None:\n'
        '    try:\n'
        '        resp = requests.get(\n'
        '            f"{PROMETHEUS_URL}/api/v1/query",\n'
        '            params={"query": expr},\n'
        '            timeout=5,\n'
        '        )\n'
        '        resp.raise_for_status()\n'
        '        result = resp.json()["data"]["result"]\n'
        '        if not result:\n'
        '            return None\n'
        '        return float(result[0]["value"][1])\n'
        '    except Exception:\n'
        '        return None'
    ),
    (
        '@dashboard_api.route("/api/dashboard/decisions", methods=["GET"])',
        '@dashboard_api.route("/api/dashboard/infra", methods=["GET"])\n'
        'def infra():\n'
        '    if not _check_api_key():\n'
        '        return jsonify({"error": "Unauthorized"}), 401\n'
        '\n'
        '    return jsonify({\n'
        '        key: _query_prometheus(expr)\n'
        '        for key, expr in INFRA_QUERIES.items()\n'
        '    })\n'
        '\n'
        '\n'
        '@dashboard_api.route("/api/dashboard/decisions", methods=["GET"])'
    ),
]

for i, (old, new) in enumerate(replacements):
    if old not in text:
        raise SystemExit(f"ANCRAGE {i} INTROUVABLE -- arret sans modification.\n{old[:150]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("dashboard.py patche avec succes pour infra (2/2 ancrages appliques).")
