"""API d'accès aux alertes de l'agent (complète l'API métriques de la story
pipeline). Démarre aussi la boucle temps réel en tâche de fond.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException

from .agent import AnomalyAgent
from .alerting import dispatcher
from .model import AnomalyDetector

_agent: AnomalyAgent = None
_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent, _task
    detector = AnomalyDetector.load()
    _agent = AnomalyAgent(detector)
    _task = asyncio.create_task(_agent.run_forever())
    yield
    _agent.stop()
    if _task:
        _task.cancel()


app = FastAPI(title="Anomaly Detection Agent API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/alerts")
def list_alerts(limit: int = 50):
    return [asdict(a) for a in dispatcher.latest(limit=limit)]


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str):
    alert = dispatcher.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return asdict(alert)


@app.get("/thresholds")
def get_thresholds():
    return _agent.detector.thresholds.to_dict()
