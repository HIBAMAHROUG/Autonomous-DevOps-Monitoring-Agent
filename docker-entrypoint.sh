#!/bin/sh
set -e

SA_DIR=/var/run/secrets/kubernetes.io/serviceaccount

if [ -n "$KUBERNETES_SERVICE_HOST" ] && [ -f "$SA_DIR/token" ]; then
    kubectl config set-cluster in-cluster \
        --server="https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT}" \
        --certificate-authority="$SA_DIR/ca.crt" >/dev/null

    kubectl config set-credentials in-cluster-sa \
        --token="$(cat "$SA_DIR/token")" >/dev/null

    kubectl config set-context in-cluster \
        --cluster=in-cluster \
        --user=in-cluster-sa \
        --namespace="$(cat "$SA_DIR/namespace" 2>/dev/null || echo default)" \
        >/dev/null

    kubectl config use-context in-cluster >/dev/null
fi

exec "$@"