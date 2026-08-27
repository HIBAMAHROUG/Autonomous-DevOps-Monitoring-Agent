import pathlib

path = pathlib.Path("orchestrator/orchestrator.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        'from remediation.notifications import notify_escalation',
        'from remediation.notifications import notify_escalation\n'
        'from monitoring import agent_metrics\n'
        'from remediation.decision_log import decision_log'
    ),
    (
        '            reason=f"Log collection failed, cannot diagnose: {exc}",\n'
        '        )',
        '            reason=f"Log collection failed, cannot diagnose: {exc}",\n'
        '        )\n'
        '        agent_metrics.record_decision("ESCALATE", None)\n'
        '        agent_metrics.record_incident_outcome(\n'
        '            "escalated",\n'
        '            (datetime.now(timezone.utc) - detected_at).total_seconds(),\n'
        '        )\n'
        '        decision_log.add(\n'
        '            mode="ESCALATE",\n'
        '            confidence=None,\n'
        '            incident_id=incident_id,\n'
        '            reason=f"Log collection failed: {exc}",\n'
        '        )'
    ),
    (
        '            reason=(\n'
        '                f"Root cause confidence too low "\n'
        '                f"({diagnosis.confidence:.2f} < 0.80): "\n'
        '                f"{diagnosis.category or \'unknown category\'}"\n'
        '            ),\n'
        '        )',
        '            reason=(\n'
        '                f"Root cause confidence too low "\n'
        '                f"({diagnosis.confidence:.2f} < 0.80): "\n'
        '                f"{diagnosis.category or \'unknown category\'}"\n'
        '            ),\n'
        '        )\n'
        '        agent_metrics.record_decision("ESCALATE", diagnosis.confidence)\n'
        '        agent_metrics.record_incident_outcome(\n'
        '            "escalated",\n'
        '            (datetime.now(timezone.utc) - detected_at).total_seconds(),\n'
        '        )\n'
        '        decision_log.add(\n'
        '            mode="ESCALATE",\n'
        '            confidence=diagnosis.confidence,\n'
        '            incident_id=incident_id,\n'
        '            reason=f"Low root cause confidence: {diagnosis.category}",\n'
        '        )'
    ),
    (
        '        decision.reason,\n'
        '    )\n'
        '\n'
        '    if decision.decision_mode == DecisionMode.ESCALATE:',
        '        decision.reason,\n'
        '    )\n'
        '\n'
        '    log_entry = decision_log.add(\n'
        '        mode=decision.decision_mode.value,\n'
        '        confidence=decision.confidence,\n'
        '        incident_id=incident_id,\n'
        '        action_type=decision.chosen_action_id,\n'
        '        reason=decision.reason,\n'
        '    )\n'
        '    agent_metrics.record_decision(\n'
        '        decision.decision_mode.value, decision.confidence\n'
        '    )\n'
        '\n'
        '    if decision.decision_mode == DecisionMode.ESCALATE:'
    ),
    (
        '            reason=f"Decision engine escalated: {decision.reason}",\n'
        '        )',
        '            reason=f"Decision engine escalated: {decision.reason}",\n'
        '        )\n'
        '        agent_metrics.record_incident_outcome(\n'
        '            "escalated",\n'
        '            (datetime.now(timezone.utc) - detected_at).total_seconds(),\n'
        '        )\n'
        '        decision_log.update_outcome(log_entry.id, "escalated")'
    ),
    (
        '        mttr.record_outcome(incident_id, outcome)\n'
        '\n'
        '        return {\n'
        '            "incident_id": incident_id,\n'
        '            "outcome": outcome,\n'
        '            "decision": decision,\n'
        '            "execution_result": result,\n'
        '            "verification": verification,\n'
        '        }',
        '        mttr.record_outcome(incident_id, outcome)\n'
        '        agent_metrics.record_incident_outcome(\n'
        '            outcome,\n'
        '            (datetime.now(timezone.utc) - detected_at).total_seconds(),\n'
        '        )\n'
        '        agent_metrics.record_remediation_action(\n'
        '            decision.chosen_action_id, result.success\n'
        '        )\n'
        '        decision_log.update_outcome(log_entry.id, outcome)\n'
        '\n'
        '        return {\n'
        '            "incident_id": incident_id,\n'
        '            "outcome": outcome,\n'
        '            "decision": decision,\n'
        '            "execution_result": result,\n'
        '            "verification": verification,\n'
        '        }'
    ),
    (
        '    if outcome != "pending":\n'
        '        mttr.record_outcome(incident_id, outcome)\n'
        '\n'
        '    return {\n'
        '        "incident_id": incident_id,\n'
        '        "outcome": outcome,\n'
        '        "decision": decision,\n'
        '        "execution_result": result,\n'
        '    }',
        '    if outcome != "pending":\n'
        '        mttr.record_outcome(incident_id, outcome)\n'
        '        agent_metrics.record_incident_outcome(\n'
        '            outcome,\n'
        '            (datetime.now(timezone.utc) - detected_at).total_seconds(),\n'
        '        )\n'
        '        agent_metrics.record_remediation_action(\n'
        '            decision.chosen_action_id, result.success\n'
        '        )\n'
        '        decision_log.update_outcome(log_entry.id, outcome)\n'
        '\n'
        '    return {\n'
        '        "incident_id": incident_id,\n'
        '        "outcome": outcome,\n'
        '        "decision": decision,\n'
        '        "execution_result": result,\n'
        '    }'
    ),
]

for i, (old, new) in enumerate(replacements):
    if old not in text:
        raise SystemExit(f"ANCRAGE {i} INTROUVABLE -- arret sans modification.\n{old[:150]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("orchestrator.py patche avec succes (7/7 ancrages appliques).")
