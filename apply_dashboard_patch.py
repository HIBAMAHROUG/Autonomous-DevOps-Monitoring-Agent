import pathlib

path = pathlib.Path("api/dashboard.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        'from executor.service import execution_service\n'
        'from remediation.approvals import approval_store',
        'from executor.service import execution_service\n'
        'from remediation.approvals import approval_store\n'
        'from remediation.decision_log import decision_log\n'
        'import remediation.mttr as mttr'
    ),
    (
        '@dashboard_api.route("/api/dashboard/history", methods=["GET"])\n'
        'def history():',
        '@dashboard_api.route("/api/dashboard/decisions", methods=["GET"])\n'
        'def decisions():\n'
        '    if not _check_api_key():\n'
        '        return jsonify({"error": "Unauthorized"}), 401\n'
        '\n'
        '    limit = request.args.get("limit", 50, type=int)\n'
        '    stats = mttr.get_stats()\n'
        '\n'
        '    return jsonify({\n'
        '        "recent": decision_log.list_recent(limit=limit),\n'
        '        "self_healing_ratio": stats.get("auto_resolution_rate", 0.0),\n'
        '        "total_incidents": stats.get("total_incidents", 0),\n'
        '        "avg_mttr_seconds": stats.get("avg_mttr_seconds", 0),\n'
        '    })\n'
        '\n'
        '\n'
        '@dashboard_api.route("/api/dashboard/history", methods=["GET"])\n'
        'def history():'
    ),
]

for i, (old, new) in enumerate(replacements):
    if old not in text:
        raise SystemExit(f"ANCRAGE {i} INTROUVABLE -- arret sans modification.\n{old[:150]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("dashboard.py patche avec succes (2/2 ancrages appliques).")
