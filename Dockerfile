FROM python:3.11-slim

WORKDIR /app

# kubectl est requis par les exécuteurs de remédiation (scaling, rollback,
# failover, k8s_pod_restart) qui l'invoquent en sous-processus.
# docker.io fournit le CLI `docker`, requis par DockerExecutor
# (docker_executor.py appelle `docker restart <container>` en subprocess).
# Le client parle au démon Docker de l'hôte via le socket monté dans
# docker-compose.yml (/var/run/docker.sock) — pas de dockerd lancé ici.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates docker.io \
    && KUBECTL_VERSION=$(curl -Ls https://dl.k8s.io/release/stable.txt) \
    && curl -Lo /usr/local/bin/kubectl \
       "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Corrige les fins de ligne CRLF qu'un checkout Windows/Git peut avoir
# introduites dans docker-entrypoint.sh : avec un \r final, le noyau
# Linux cherche l'interpréteur "/bin/sh\r" (inexistant) et échoue avec
# "exec ...: no such file or directory" au démarrage du conteneur.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-u", "app.py"]