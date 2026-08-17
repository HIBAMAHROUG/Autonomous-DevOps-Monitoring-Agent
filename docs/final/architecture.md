\# Architecture du MonitoringAgent



\## 1. Vue générale



Le MonitoringAgent est une plateforme de détection et de remédiation automatique des incidents d'infrastructure.



```text

┌─────────────────────────────────────────────────────────┐

│                    Infrastructure                       │

│              Kubernetes / Docker / Services             │

└──────────────────────────┬──────────────────────────────┘

&#x20;                          │

&#x20;                   Metrics + Logs

&#x20;                          │

&#x20;             ┌────────────▼────────────┐

&#x20;             │    Monitoring Layer     │

&#x20;             │                         │

&#x20;             │ Prometheus │ Loki │     │

&#x20;             │           Grafana       │

&#x20;             └────────────┬────────────┘

&#x20;                          │

&#x20;                     Metrics API

&#x20;                          │

&#x20;             ┌────────────▼────────────┐

&#x20;             │    Monitoring Agent     │

&#x20;             │                         │

&#x20;             │ Collector               │

&#x20;             │     ↓                   │

&#x20;             │ Detector                │

&#x20;             │     ↓                   │

&#x20;             │ Diagnosis               │

&#x20;             │     ↓                   │

&#x20;             │ Decision Engine         │

&#x20;             └────────────┬────────────┘

&#x20;                          │

&#x20;                    Remediation

&#x20;                          │

&#x20;             ┌────────────▼────────────┐

&#x20;             │      Safety Layer       │

&#x20;             │                         │

&#x20;             │ • Rate Limit            │

&#x20;             │ • Blast Radius          │

&#x20;             │ • Human Approval        │

&#x20;             │ • Circuit Breaker       │

&#x20;             │ • Kill Switch           │

&#x20;             └────────────┬────────────┘

&#x20;                          │

&#x20;                ┌─────────▼─────────┐

&#x20;                │ ExecutionService  │

&#x20;                └─────────┬─────────┘

&#x20;                          │

&#x20;      ┌──────────┬─────────┼─────────┬──────────┐

&#x20;      ↓          ↓         ↓         ↓          ↓

&#x20;   Restart    Scaling   Cleanup   Failover   Rollback

&#x20;      │          │         │         │          │

&#x20;      └──────────┴─────────┴─────────┴──────────┘

&#x20;                          │

&#x20;             ┌────────────▼────────────┐

&#x20;             │ Kubernetes / Docker     │

&#x20;             └─────────────────────────┘

```



\## 2. Composants principaux



\### Monitoring



\* \*\*Prometheus\*\* : collecte et stockage des métriques.

\* \*\*Grafana\*\* : visualisation et dashboards.

\* \*\*Loki\*\* : centralisation des logs.



\### MonitoringAgent



Le système est organisé en plusieurs composants :



```text

collector/

detector/

diagonisis/

remediation/

executor/

storage/

api/

```



\### Collector



Le Collector récupère les métriques d'infrastructure à intervalles réguliers.



Exemples :



\* CPU

\* mémoire

\* réseau

\* autres métriques Prometheus



\### Detector



Le Detector analyse les métriques afin d'identifier les anomalies.



\### Diagnosis



Le module de diagnostic identifie le type de problème et recherche l'action corrective appropriée.



\### Decision Engine



Le moteur de décision choisit le mode d'exécution :



\* `AUTO\_EXECUTE`

\* `SUGGEST\_TO\_HUMAN`

\* `ESCALATE`



\### Safety Layer



Avant toute action réelle, les règles de sécurité sont vérifiées.



Les protections comprennent :



\* nombre maximal d'actions par heure ;

\* limitation du blast radius ;

\* approbation humaine pour les actions critiques ;

\* circuit breaker ;

\* audit trail ;

\* kill switch.



\### ExecutionService



`ExecutionService` centralise l'exécution des actions de remédiation.



Les executors disponibles sont :



\* `DockerExecutor`

\* `ScalingExecutor`

\* `CleanupExecutor`

\* `FailoverExecutor`

\* `RollbackExecutor`



\## 3. Flux de traitement



```text

Métrique

&#x20;  ↓

Prometheus

&#x20;  ↓

Collector

&#x20;  ↓

Detector

&#x20;  ↓

Diagnosis

&#x20;  ↓

Decision Engine

&#x20;  ↓

Safety Policy

&#x20;  ↓

ExecutionService

&#x20;  ↓

Action corrective

&#x20;  ↓

Kubernetes / Docker

&#x20;  ↓

Résultat

&#x20;  ↓

Audit / Historique

```



\## 4. Sécurité



Le système utilise une approche \*\*fail-safe\*\*.



Une action peut être bloquée lorsque :



\* le nombre maximal d'actions est atteint ;

\* le nombre de replicas demandé dépasse le blast radius autorisé ;

\* une approbation humaine est nécessaire ;

\* le circuit breaker est activé ;

\* le kill switch est actif.



Exemple :



```text

Action demandée

&#x20;     ↓

Safety Policy

&#x20;     ↓

&#x20;  Autorisée ? ── Non ──→ BLOCKED

&#x20;     │

&#x20;    Oui

&#x20;     ↓

ExecutionService

&#x20;     ↓

Exécution réelle

```



\## 5. Modes d'exécution



\### Dry-run



Le mode `dry\_run=True` simule l'action sans modifier l'infrastructure.



Il permet de vérifier :



\* la commande générée ;

\* les paramètres ;

\* les règles de sécurité ;

\* le résultat attendu.



\### Real execution



Avec `dry\_run=False`, l'action est réellement exécutée si elle respecte toutes les règles de sécurité.



\## 6. Infrastructure de test



L'environnement de démonstration utilise :



\* Windows 11 ;

\* Docker Desktop ;

\* Minikube ;

\* Kubernetes ;

\* Prometheus ;

\* Grafana ;

\* Loki.



Les tests de remédiation utilisent notamment le deployment :



```text

remediation-test

```



\## 7. Exemple de flux réel



Lorsqu'un problème nécessite une augmentation du nombre de replicas :



```text

Anomalie détectée

&#x20;      ↓

Décision : SCALE

&#x20;      ↓

Safety Policy

&#x20;      ↓

Vérification du blast radius

&#x20;      ↓

ExecutionService

&#x20;      ↓

kubectl scale deployment

&#x20;      ↓

Kubernetes

&#x20;      ↓

Nouveau nombre de replicas

```



\## 8. Résilience



L'architecture permet de séparer :



\* détection ;

\* décision ;

\* sécurité ;

\* exécution ;

\* stockage ;

\* observabilité.



Cette séparation facilite les tests, le remplacement d'un composant et l'évolution du système.



\## 9. Structure du projet



```text

MonitoringAgent/

│

├── collector/

├── detector/

├── diagonisis/

├── remediation/

│   ├── decision.py

│   ├── models.py

│   ├── safety.py

│   └── catalog.py

│

├── executor/

│   ├── service.py

│   ├── scaling\_executor.py

│   ├── docker\_executor.py

│   ├── cleanup\_executor.py

│   ├── failover\_executor.py

│   └── rollback\_executor.py

│

├── monitoring/

├── loki/

├── storage/

├── api/

├── terraform/

└── docs/

&#x20;   └── final/

```



\## 10. Conclusion



Le MonitoringAgent fournit une architecture complète de \*\*monitoring, détection, décision et remédiation automatique\*\*.



L'intégration d'une couche de sécurité avant l'exécution permet de limiter les risques liés à l'automatisation et de conserver un contrôle opérationnel sur les actions critiques.



