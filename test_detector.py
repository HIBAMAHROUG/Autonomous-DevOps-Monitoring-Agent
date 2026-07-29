from detector.detector import check_metrics


metrics = {
    "cpu_usage": 95,
    "memory_usage": 60
}


result = check_metrics(metrics)

print(result)