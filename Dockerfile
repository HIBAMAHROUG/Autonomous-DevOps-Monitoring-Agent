FROM python:3.11-slim

WORKDIR /app

# kubectl est requis par les exécuteurs de remédiation (scaling, rollback,
# failover, k8s_pod_restart) qui l'invoquent en sous-processus.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && KUBECTL_VERSION=$(curl -Ls https://dl.k8s.io/release/stable.txt) \
    && curl -Lo /usr/local/bin/kubectl \
       "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-u", "app.py"]