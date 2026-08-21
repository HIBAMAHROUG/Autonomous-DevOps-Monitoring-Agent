# Autonomous DevOps Monitoring Agent

Agent DevOps autonome : surveillance d'infrastructure, détection d'anomalies, diagnostic et remédiation automatique, avec garde-fous de sécurité.

## Pipeline de détection à deux étages

Le pipeline combine deux systèmes :

1. Étage 1 — pré-filtre : détection rapide avec seuils, durée, tendance et fenêtres de maintenance.
2. Étage 2 — confirmation ML : Isolation Forest, analyse multivariée des quatre métriques et classification de sévérité.

Le pipeline unifié se trouve dans detector/pipeline.py et est utilisé par collector/collector.py.

## Structure du projet

 collector/ Collecte CPU, RAM, réseau et disque depuis Prometheus
 detector/ Détection à seuils
 anomaly_agent/ Détection ML et API FastAPI
 diagnosis/ Agrégation des logs Loki
 remediation/ Décision, catalogue et garde-fous
 executor/ Exécution des actions
 storage/ Persistance des métriques et de l'audit
 api/ API Flask
 monitoring/ Configuration Prometheus, Loki et Grafana
 terraform/ Infrastructure as Code
 docs/ Documentation

## Prérequis

- Python 3.11+
- Kubernetes accessible via kubectl
- Prometheus
- Loki
- InfluxDB
- Docker

## Installation sous Windows PowerShell

 python -m venv .venv
 .venv\Scripts\Activate.ps1
 pip install -r requirements.txt
 Copy-Item .env.example .env

Ne jamais committer le fichier .env.

## Variables d'environnement

| Variable | Description |
|---|---|
| INFLUX_URL | URL InfluxDB |
| INFLUX_ORG | Organisation InfluxDB |
| INFLUX_TOKEN | Token InfluxDB |
| API_KEY | Clé API |
| PROMETHEUS_URL | URL Prometheus |
| PROMETHEUS_TOKEN | Token Prometheus optionnel |
| SLACK_WEBHOOK_URL | Webhook Slack |
| AGENT_OFFLINE_WEBHOOK_URL | Webhook secondaire pour l'alerte "Agent Offline" (Bug 3 : perte de connexion Kubernetes > 5 min). Retombe sur SLACK_WEBHOOK_URL si absent. |
| SMTP_HOST | Serveur SMTP |
| SMTP_PORT | Port SMTP |
| SMTP_USER | Utilisateur SMTP |
| SMTP_PASSWORD | Mot de passe SMTP |
| APPROVAL_EMAIL_TO | Destinataire des approbations |
| APPROVAL_EMAIL_FROM | Expéditeur des approbations |
| AUDIT_BACKEND | sqlite ou postgres |
| REMEDIATION_DB_HOST | Hôte PostgreSQL |
| REMEDIATION_DB_PORT | Port PostgreSQL |
| REMEDIATION_DB_NAME | Nom de la base PostgreSQL |
| REMEDIATION_DB_USER | Utilisateur PostgreSQL |
| REMEDIATION_DB_PASSWORD | Mot de passe PostgreSQL |

## Persistance de l'audit

Le système utilise storage/audit_store.py comme point d'entrée unique.

Deux backends sont disponibles :

- SQLite : backend par défaut pour les tests et le staging.
- PostgreSQL : backend recommandé pour la production multi-instances.

### SQLite

Variable :

 AUDIT_BACKEND=sqlite

Base locale :

 data/audit.sqlite3

### PostgreSQL

Variable :

 AUDIT_BACKEND=postgres

Configurer ensuite les variables REMEDIATION_DB_*.

Le schéma PostgreSQL est :

 storage/schema_audit.sql

Le backend PostgreSQL est :

 storage/audit_store_postgres.py

Le dispatcher est :

 storage/audit_store.py

## Tests

Exécuter tous les tests :

 python -m pytest -v

Collecter uniquement les tests :

 python -m pytest --collect-only -q

Tester la persistance :

 python -m pytest test_persistence.py -v

Tester le backend PostgreSQL :

 python -m pytest test_audit_postgres.py -v

## Sécurité

Les actions passent par SafetyPolicy avant exécution.

- limite d'actions par heure
- limite d'actions par pod
- protection anti-boucle
- circuit breaker
- kill switch
- limitation du blast radius
- approbation humaine pour les actions critiques
- dry-run par défaut
- retry avec backoff exponentiel sur les erreurs de connexion kubectl,
  et alerte "Agent Offline" après 5 minutes de panne (executor/kubectl_client.py)

## Déploiement

 docker build -t autonomous-devops-agent .
 docker compose up

## Licence

À définir.