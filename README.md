# Autonomous DevOps Agent — End-to-End Pipeline Fix

## What this fixes

The corrected bundle connects:

Prometheus -> Collector -> threshold detector -> ML confirmation -> Incident
-> Loki diagnosis -> decision engine -> SafetyPolicy -> Kubernetes remediation
-> Prometheus verification -> MTTR/dashboard.

It also:
- runs the collector as a dedicated Docker service;
- fixes the Prometheus API URL;
- fixes the `namespace/pod` -> `pod + namespace` mismatch;
- implements Kubernetes pod restart (the previous executor was only a stub);
- persists audit and approval data in SQLite so API + collector share state;
- prevents repeated incidents every 30 seconds for the same sustained breach;
- adds CPU and high-memory problems to the remediation knowledge base;
- keeps Loki as the diagnostic source, with a metric fallback when Loki has no
  matching ERROR/WARN pattern.

## 1. Copy the files

Replace only the files contained in this ZIP. Do NOT overwrite your existing
dashboard/template files.

Keep your existing `kube-docker-config.yaml` for now, but see the security note.

## 2. Set a real target pod

For a deterministic demo, set this in docker-compose:

    TARGET_POD: "YOUR-POD-NAME"

and:

    K8S_NAMESPACE: "default"

If TARGET_POD is omitted, the collector first tries the highest-CPU pod and then
falls back to the first Running pod.

## 3. Start

PowerShell:

    docker compose down
    docker compose build --no-cache
    docker compose up -d

Then:

    docker compose ps
    docker logs -f monitoring-collector

## 4. Expected collector logs

You should see:

    Target pod: ...
    Confirmed incidents: 1
    INCIDENT DETECTED
    INCIDENT START
    Loki ...
    DECISION
    AUTO_EXECUTE
    REMEDIATION END
    outcome=resolved

For a critical incident you should instead see:

    SUGGEST_TO_HUMAN
    Human approval required for critical action

and the request should appear in:

    GET /api/approvals/pending

## 5. Demo thresholds

The supplied demo thresholds are intentionally low:

    CPU > 70% for 60s
    MEMORY > 70% for 60s

After the demo, restore production values such as:

    CPU > 90% for 300s
    MEMORY > 85% for 300s

## 6. Test Kubernetes access from the container

    docker exec monitoring-collector kubectl --kubeconfig /app/kube-config/config get pods -A

Then test Loki:

    docker exec monitoring-api python -c "import requests; print(requests.get('http://loki:3100/ready').text)"

Test Prometheus:

    docker exec monitoring-collector python -c "import requests; print(requests.get('http://prometheus:9090/-/ready').text)"

## 7. Loki / Alloy

The supplied Alloy configuration sends Kubernetes logs to the Docker Compose
Loki at:

    http://host.docker.internal:3100/loki/api/v1/push

This assumes Minikube is running with Docker Desktop and can resolve
`host.docker.internal`.

If your Minikube environment cannot resolve it, use a reachable host IP or
NodePort instead and update `alloy/alloy-values.yaml`.

## 8. IMPORTANT security note

Your public GitHub repository currently contains `kube-docker-config.yaml` with
embedded client certificate/private-key material. Treat that credential as
exposed. Do not keep it in a public repository.

Generate a fresh kubeconfig/credential, remove the old key from the public repo,
and use a secret or local ignored file.

## 9. Why the old pipeline did not heal

The repository had several independent blockers:
- collector called `check_metrics()` instead of `check_and_confirm()`;
- compose did not start a collector process;
- Prometheus URL in compose was missing `/api/v1/query`;
- `PROMETHEUS_REQUIRE_AUTH` defaulted to true without a token in compose;
- `get_highest_cpu_pod()` returns `namespace/pod`, while Loki expected only pod;
- Kubernetes pod remediation executor returned "non implemente";
- `dry_run` defaulted to true;
- audit/approval state was in process memory, so API and collector could not
  reliably share approval state;
- the remediation knowledge base did not contain CPU/high-memory signatures;
- sustained threshold alerts could be emitted repeatedly.

This bundle addresses those blockers without redesigning your dashboard.
