import time
from collector.metrics import get_cpu


def collect():

    print("Collecte des métriques CPU...")

    cpu = get_cpu()

    print(cpu)


while True:

    collect()

    time.sleep(30)