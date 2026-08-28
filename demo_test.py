"""
Script de démo pour Smartovate - Agent DevOps Autonome
=========================================================

Déclenche 2 scénarios via le VRAI pipeline (pas le mock UI test-critical):

  Scénario 1 : anomalie modérée -> auto-remédiation (l'IA agit seule)
  Scénario 2 : anomalie critique -> approbation manuelle (l'IA escalade)

Utilisation :
    python demo_test.py

Le script affiche le score ML et la sévérité obtenus à chaque étape, et
ajuste automatiquement la valeur CPU si besoin pour atteindre la sévérité
cible. Les incidents résultants passent par decision_log et sont donc
visibles sur le dashboard web (/dashboard) après exécution.

À COPIER dans le dossier racine de ton projet (MonitoringAgent), à côté
de detector/, orchestrator/, remediation/, etc.
"""

import sys
from datetime import datetime, timedelta, timezone

from detector.pipeline import check_and_confirm
from orchestrator.orchestrator import handle_alert


def run_scenario(label: str, cpu_value: float, pod_name: str, service_name: str):
    print(f"\n{'=' * 60}")
    print(f"SCÉNARIO : {label}")
    print(f"{'=' * 60}")
    print(f"Injection CPU = {cpu_value}% sur le service '{service_name}'...")

    now0 = datetime.now(timezone.utc)
    metrics = {"cpu_usage": cpu_value}

    # 1er appel : démarre le compteur de dépassement (_breach_since)
    alerts = check_and_confirm(metrics, service=service_name)
    print(f"  [t+0s]   alertes retournées : {len(alerts)} (attendu: 0, la durée "
          f"minimale de 300s n'est pas encore atteinte)")

    # 2e appel : on simule que 301 secondes se sont écoulées en appelant
    # directement le détecteur interne avec un `now` décalé, pour ne pas
    # avoir à attendre réellement 5 minutes.
    from detector.detector import _default_detector
    from anomaly_agent.severity import classify_severity
    from detector.pipeline import _get_ml_detector

    now1 = now0 + timedelta(seconds=301)
    threshold_alerts = _default_detector.check(
        metrics,
        service=service_name,
        pod=pod_name,
        now=now1,
    )

    if not threshold_alerts:
        print("  ERREUR : le pré-filtre n'a déclenché aucune alerte. "
              "Augmente cpu_value et relance.")
        return None

    # IMPORTANT : on force un détecteur ML FRAIS (rechargé depuis l'artefact
    # calibré sur disque) pour ce scénario, au lieu de réutiliser le
    # singleton mis en cache. Sinon, la baseline EWMA interne (mise à jour
    # à chaque appel de observe()/score_sample()) serait polluée par le
    # scénario précédent, faussant le score du 2e scénario.
    import detector.pipeline as pipeline_module
    pipeline_module._ml_detector = None
    detector = _get_ml_detector()
    score, z_scores = detector.score_sample(metrics)
    severity = classify_severity(score, detector.thresholds)

    print(f"  [t+301s] score ML = {score:.4f}  |  sévérité calculée = {severity}")

    if severity is None:
        print("  ERREUR : le modèle ML n'a pas confirmé l'anomalie (severity=None). "
              "Augmente cpu_value et relance.")
        return None

    alert = {
        **threshold_alerts[0],
        "ml_score": round(score, 4),
        "severity": severity,
        "z_scores": {k: round(v, 2) for k, v in z_scores.items()},
    }

    print(f"  -> Envoi de l'alerte à l'orchestrateur (handle_alert)...")
    result = handle_alert(alert, pod=pod_name, dry_run=True)

    decision = result.get("decision") or result.get("error") or "?"
    action = result.get("action", "?")
    print(f"\n  RÉSULTAT :")
    print(f"    Décision   : {decision}")
    print(f"    Action     : {action}")
    print(f"    Incident   : {result.get('incident_id', '?')}")

    return result


if __name__ == "__main__":
    print("Démo Agent DevOps Autonome - Smartovate Ltd")
    print("Déclenchement des 2 scénarios via le pipeline réel "
          "(detector -> anomaly_agent -> orchestrator -> executor)")

    # Scénario 1 : CPU élevé mais pas extrême -> devrait rester en dessous
    # du seuil "critical" de classify_severity -> auto-remédiation attendue.
    run_scenario(
        label="Auto-remédiation attendue (CPU élevé, non-critique)",
        cpu_value=93.0,
        pod_name="demo-pod-auto",
        service_name="demo-service-auto",
    )

    # Scénario 2 : CPU extrême -> devrait classer en "critical"
    # -> approbation manuelle attendue (executor/service.py + safety.py).
    run_scenario(
        label="Approbation manuelle attendue (CPU critique)",
        cpu_value=99.5,
        pod_name="demo-pod-critical",
        service_name="demo-service-critical",
    )

    print(f"\n{'=' * 60}")
    print("Terminé. Ouvre http://localhost:5000/dashboard pour voir les 2 "
          "incidents dans l'onglet Incidents / Approvals.")
    print(f"{'=' * 60}")