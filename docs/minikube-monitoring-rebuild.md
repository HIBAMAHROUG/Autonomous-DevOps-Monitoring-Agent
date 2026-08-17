# Remise a zero complete de Minikube et du stack monitoring

This guide assumes Windows 11, Docker Desktop, Minikube, Helm, kube-prometheus-stack, Loki, Promtail, and Grafana.

The goal is to start from a clean state with a simple setup compatible with Minikube:

- 6 Go RAM and 4 CPU for Minikube.
- Prometheus via kube-prometheus-stack.
- Loki for centralized logs.
- Promtail to ship pod logs to Loki.
- Grafana pre-configured with Prometheus and Loki.
- Alerts for CPU, memory, network, and disk.

## 1. Nettoyage complet

Close Docker Desktop before running the cleanup commands. If a file is locked, restart the machine first; file locks are almost always caused by a running process.

```powershell
docker system prune -af --volumes
```

Removes unused containers, images, networks, build cache, and volumes. This is the fastest way to clean Docker Desktop for a fresh Minikube rebuild.

```powershell
docker builder prune -af
```

Removes any remaining BuildKit cache that can keep old layers around.

```powershell
minikube delete --all --purge
```

Deletes every Minikube profile and its cached state. The `--purge` flag removes the local Minikube configuration as well.

```powershell
Stop-Service ssh-agent -ErrorAction SilentlyContinue
```

Stops the Windows SSH agent if it is holding a Minikube key file open.

```powershell
Remove-Item -Recurse -Force $env:USERPROFILE\.minikube
```

Deletes leftover Minikube files that sometimes survive `minikube delete`.

```powershell
Remove-Item -Recurse -Force $env:USERPROFILE\.kube\cache -ErrorAction SilentlyContinue
```

Clears cached Kubernetes discovery and stale client data.

If `id_rsa.pub` or another SSH file is still locked, reboot once after stopping Docker Desktop and retry the deletion. Persistent locks usually disappear after a full process restart.

## 2. Recreate Minikube

```powershell
minikube start --driver=docker --cpus=4 --memory=6144 --kubernetes-version=v1.35.0 --disk-size=30g
```

Starts a fresh Minikube cluster on Docker Desktop with 4 CPUs, 6 GiB of RAM, and a 30 GiB disk. The Docker driver is the simplest option for a local Windows setup.

```powershell
kubectl config use-context minikube
```

Makes sure all following Kubernetes commands target the new cluster.

## 3. Install the namespace and charts

```powershell
kubectl apply -f monitoring/namespace.yaml
```

Creates the `monitoring` namespace that will host Prometheus, Loki, Promtail, and Grafana.

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
```

Adds the official Helm repository that contains kube-prometheus-stack.

```powershell
helm repo add grafana https://grafana.github.io/helm-charts
```

Adds the Grafana Helm repository for Loki and Promtail.

```powershell
helm repo update
```

Refreshes chart metadata before installation.

```powershell
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack -n monitoring -f monitoring/kube-prometheus-stack-values.yaml
```

Installs or upgrades Prometheus, Alertmanager, Grafana, node-exporter, kube-state-metrics, and the default Kubernetes rules.

```powershell
helm upgrade --install loki grafana/loki -n monitoring -f loki/loki-values.yaml
```

Installs Loki in single-binary mode with filesystem storage so it stays simple and stable on Minikube.

```powershell
helm upgrade --install promtail grafana/promtail -n monitoring -f monitoring/promtail-values.yaml
```

Installs Promtail as a DaemonSet so each node can ship its pod logs to Loki.

```powershell
kubectl apply -f monitoring/prometheus-rules.yaml
```

Installs custom alert rules for CPU, memory, network, and disk usage.

## 4. Verification

```powershell
kubectl get pods -n monitoring
```

Checks that Prometheus, Alertmanager, Grafana, Loki, and Promtail all reached the Running state.

```powershell
kubectl get servicemonitor,prometheusrule -n monitoring
```

Confirms that the operator is seeing the scrape resources and that the alert rules were created.

```powershell
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
```

Forwards Grafana to localhost so you can log in and test the dashboards and data sources. If your Helm release name differs, use the Grafana service name shown by `kubectl get svc -n monitoring`.

```powershell
kubectl port-forward -n monitoring svc/loki 3100:3100
```

Forwards Loki locally so you can test readiness and ingestion.

Then verify Loki directly:

```powershell
Invoke-WebRequest http://localhost:3100/ready
```

Returns HTTP 200 when Loki is healthy. If it still returns 503, Loki is not ready and Promtail/Grafana will fail too.

## 5. Validate Grafana and logs

In Grafana, open Connections, Data sources, and confirm both Prometheus and Loki are present.

In Explore, select Loki and run a simple query like:

`{namespace="monitoring"}`

Then check that you can see log streams from Promtail and other pods. If the query returns nothing, inspect Promtail logs:

```powershell
kubectl logs -n monitoring -l app.kubernetes.io/name=promtail
```

If Grafana cannot reach Loki, verify the Loki service name and that the Loki pod is Running before debugging Grafana.

## 6. Acceptance checklist

- Terraform exists in the repository and the monitoring stack is managed by Kubernetes manifests and Helm values.
- Prometheus is installed through kube-prometheus-stack.
- CPU metrics come from node-exporter and kubelet/cAdvisor.
- Memory metrics come from node-exporter and kubelet/cAdvisor.
- Network metrics come from node-exporter.
- Disk metrics come from node-exporter.
- Alerts are installed through `monitoring/prometheus-rules.yaml`.
- Logs are centralized through Loki.
- Promtail ships pod logs to Loki.
- Grafana is configured with a Loki datasource.
- You can verify logs in Grafana Explore.

## 7. The files to use

- `monitoring/namespace.yaml`
- `monitoring/kube-prometheus-stack-values.yaml`
- `loki/loki-values.yaml`
- `monitoring/promtail-values.yaml`
- `monitoring/prometheus-rules.yaml`

## 8. Why this setup is simple

This layout avoids extra complexity like ingress, external object storage, or multi-replica Loki components. It is the smallest configuration that still gives you Prometheus, Grafana, Loki, Promtail, and alerts on a local Minikube cluster.