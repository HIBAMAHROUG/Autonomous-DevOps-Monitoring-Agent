import requests

# Adresse de Prometheus
PROMETHEUS_URL = "http://localhost:9090/api/v1/query"

# Requête PromQL
query = "up"

try:
    response = requests.get(PROMETHEUS_URL, params={"query": query})

    if response.status_code == 200:
        print("Connexion réussie à Prometheus !")
        print(response.json())
    else:
        print("Erreur :", response.status_code)

except Exception as e:
    print("Impossible de se connecter à Prometheus.")
    print(e)