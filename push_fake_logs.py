"""
Pousse de faux logs dans Loki, avec les bons labels (namespace/pod) et un
message qui matche un pattern connu de diagonisis/patterns.yaml (ex:
"OutOfMemory" -> confiance 0.95), pour que diagnose() ne renvoie pas
requires_human=True à cause d'un diagnostic non concluant.

À lancer AVANT demo_test.py / simulate-real-incident, une fois par pod
que tu vas utiliser dans tes scénarios.

Utilisation :
    python push_fake_logs.py demo-pod-auto
    python push_fake_logs.py demo-pod-critical

Nécessite que le port 3100 de Loki soit exposé sur ta machine hôte
(c'est le cas dans le docker-compose.yml fourni : "3100:3100").
"""

import sys
import time
import requests

LOKI_PUSH_URL = "http://localhost:3100/loki/api/v1/push"


def push_log(pod: str, namespace: str = "default", message: str = None):
    message = message or (
        f"ERROR: OutOfMemory: container {pod} killed, OOMKilled "
        f"(memory usage exceeded limit)"
    )

    now_ns = str(int(time.time() * 1_000_000_000))

    payload = {
        "streams": [
            {
                "stream": {
                    "namespace": namespace,
                    "pod": pod,
                },
                "values": [
                    [now_ns, message]
                ],
            }
        ]
    }

    response = requests.post(LOKI_PUSH_URL, json=payload, timeout=5)

    if response.status_code == 204:
        print(f"OK : log poussé pour pod={pod} namespace={namespace}")
        print(f"     message = {message!r}")
    else:
        print(f"ERREUR {response.status_code} : {response.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python push_fake_logs.py <pod_name> [namespace]")
        sys.exit(1)

    pod_name = sys.argv[1]
    ns = sys.argv[2] if len(sys.argv) > 2 else "default"

    push_log(pod_name, ns)