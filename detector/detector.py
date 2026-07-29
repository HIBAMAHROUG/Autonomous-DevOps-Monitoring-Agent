import yaml
import json
import os


# Charger les règles
with open("detector/rules.yaml", "r") as file:
    rules = yaml.safe_load(file)



def check_metrics(metrics):

    alerts = []


    # Vérification CPU
    if metrics["cpu_usage"] > rules["cpu"]["threshold"]:

        alerts.append({
            "service": "monitoring-agent",
            "metric": "CPU",
            "value": metrics["cpu_usage"],
            "severity": "CRITICAL"
        })


    # Vérification RAM
    if metrics["memory_usage"] > rules["memory"]["threshold"]:

        alerts.append({
            "service": "monitoring-agent",
            "metric": "MEMORY",
            "value": metrics["memory_usage"],
            "severity": "CRITICAL"
        })


    # Sauvegarde des alertes

    if alerts:

        os.makedirs(
            "events",
            exist_ok=True
        )

        with open(
            "events/alerts.json",
            "w"
        ) as file:

            json.dump(
                alerts,
                file,
                indent=4
            )


    return alerts