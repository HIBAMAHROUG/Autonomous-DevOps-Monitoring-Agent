# Autonomous DevOps Monitoring Agent

Agent DevOps autonome : surveillance d'infrastructure, détection d'anomalies,
diagnostic et remédiation automatique, avec garde-fous de sécurité (dry-run,
rate limiting, circuit breaker, approbation humaine).

Voir `docs/final/architecture.md` pour le schéma d'architecture détaillé.

## ⚠️ Deux moteurs de détection coexistent

Ce dépôt contient actuellement **deux implémentations distinctes** de la
détection d'anomalies :

- **`detector/`** — détection à seuils simples, statiques, historiquement le
  premier module écrit. Sert de garde-fou "fast path" à faible latence.
- **`anomaly_agent/`** — agent de détection par modèle ML (scoring,
  explication, classification de sévérité par quantiles), exposé via sa
  propre API FastAPI (`anomaly_agent/api.py`). C'est le moteur destiné à la
  production.

**Statut actuel** : `anomaly_agent/` est le moteur de référence à faire
évoluer. `detector/` reste utilisé par `collector/collector.py` comme
pré-filtre rapide indépendant. Voir la section "Architecture" ci-dessous et
`docs/final/architecture.md` pour le détail des responsabilités de chacun.
Ne pas dupliquer de nouvelle logique de seuils dans `detector/` sans
vérifier si elle doit plutôt vivre dans `anomaly_agent/`.

## Structure du projet

```
collector/       Collecte des métriques (CPU/RAM/réseau/disque) depuis Prometheus
detector/        Détection à seuils (fast path), voir avertissement ci-dessus
anomaly_agent/   Agent de détection ML (moteur de référence) + API FastAPI
diagonisis/      Agrégation des logs contextuels (Loki) pour le diagnostic
remediation/     Catalogue de remédiations, scoring, décision, garde-fous (safety)
executor/        Exécution des actions (kubectl, docker, cleanup...) avec dry-run
storage/         Persistance des métriques et de l'historique des remédiations
api/              API Flask d'ingestion/consultation des métriques
monitoring/       Values Helm pour la stack Prometheus/Loki/Grafana
terraform/        Provisioning infra (ne pas committer terraform.tfstate ni .terraform/)
docs/             Documentation d'architecture
```

## Prérequis

- Python 3.11+
- Un cluster Kubernetes accessible via `kubectl` (K3s/Minikube en environnement de test)
- Prometheus, Loki, InfluxDB accessibles (voir `docker-compose.yml` / `monitoring/` pour un déploiement local)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner les vraies valeurs (jamais commiter .env)
```

## Variables d'environnement

| Variable | Description |
|---|---|
| `INFLUX_URL` | URL de l'instance InfluxDB pour le stockage des métriques |
| `INFLUX_ORG` | Organisation InfluxDB |
| `INFLUX_TOKEN` | Token d'authentification InfluxDB (secret) |
| `API_KEY` | Clé d'authentification pour l'API metrics (`api/routes.py`) |
| `PROMETHEUS_URL` | URL de l'API Prometheus (défaut : `http://localhost:9090/api/v1/query`) |
| `PROMETHEUS_TOKEN` | Token optionnel si Prometheus est protégé |
| `AGENT_OFFLINE_WEBHOOK_URL` | Webhook secondaire déclenché si l'agent perd la connexion à l'API Kubernetes pendant plus de 5 minutes |

## Lancer les tests

```bash
python -m pytest -v
```

## Déploiement

```bash
docker build -t autonomous-devops-agent .
docker compose up
```

Pour la stack de monitoring sur Kubernetes, voir les values Helm dans `monitoring/`, `loki/` et `alloy/`.

## Sécurité / garde-fous

Toute action de remédiation passe par `remediation/safety.py` (`SafetyPolicy`) avant exécution :

- limite d'actions par heure et par pod (anti-boucle, cf. Bug 1 du cahier des charges)
- circuit breaker après échecs consécutifs
- kill switch manuel
- approbation humaine obligatoire pour les actions critiques (`failover`, `rollback`)
- mode `dry_run` par défaut sur tous les exécuteurs (`executor/`)

## Licence

À définir.