import pathlib

path = pathlib.Path("api/dashboard.py")
text = path.read_text(encoding="utf-8")

old = (
    '    return jsonify({\n'
    '        "recent": decision_log.list_recent(limit=limit),\n'
    '        "self_healing_ratio": stats.get("auto_resolution_rate", 0.0),\n'
    '        "total_incidents": stats.get("total_incidents", 0),\n'
    '        "avg_mttr_seconds": stats.get("avg_mttr_seconds", 0),\n'
    '    })'
)
new = (
    '    return jsonify({\n'
    '        "recent": decision_log.list_recent(limit=limit),\n'
    '        "self_healing_ratio": stats.get("auto_resolution_rate") or 0.0,\n'
    '        "total_incidents": stats.get("total_incidents", 0),\n'
    '        "avg_mttr_seconds": stats.get("mttr_seconds_avg") or 0,\n'
    '    })'
)

if old not in text:
    raise SystemExit("ANCRAGE INTROUVABLE -- arret sans modification.")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("dashboard.py corrige (cle mttr_seconds_avg).")
