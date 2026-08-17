"""
Explainability des alertes — critère d'acceptation ML.

Le score IsolationForest n'est pas interprétable seul ; on s'appuie donc
sur les z-scores par métrique (déjà calculés pour le modèle) pour dire
QUELLE(S) métrique(s) ont déclenché l'alerte et de COMBIEN elles dévient
 de leur baseline habituelle.
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class MetricContribution:
    metric: str
    value: float
    z_score: float
    baseline_mean: float
    baseline_std: float

    @property
    def deviation_pct(self) -> float:
        if self.baseline_mean == 0:
            return 0.0
        return (self.value - self.baseline_mean) / abs(self.baseline_mean) * 100


def explain(sample: Dict[str, float], z_scores: Dict[str, float], feature_store, top_k: int = 3) -> dict:
    contributions: List[MetricContribution] = []
    for metric, z in z_scores.items():
        baseline = feature_store.baselines[metric]
        contributions.append(MetricContribution(
            metric=metric,
            value=sample.get(metric, float("nan")),
            z_score=z,
            baseline_mean=baseline.ewma_mean or 0.0,
            baseline_std=baseline.std,
        ))

    contributions.sort(key=lambda c: abs(c.z_score), reverse=True)
    top = contributions[:top_k]

    narrative_parts = []
    for c in top:
        direction = "au-dessus" if c.z_score > 0 else "en-dessous"
        narrative_parts.append(
            f"{c.metric} = {c.value:.1f} ({direction} de sa moyenne habituelle "
            f"{c.baseline_mean:.1f} ± {c.baseline_std:.1f}, z-score={c.z_score:+.1f}, "
            f"écart={c.deviation_pct:+.0f}%)"
        )

    return {
        "top_contributors": [c.__dict__ for c in top],
        "narrative": "Anomalie détectée principalement sur : " + " ; ".join(narrative_parts),
    }
