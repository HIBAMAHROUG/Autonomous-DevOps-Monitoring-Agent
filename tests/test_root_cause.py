from diagonisis.root_cause import (
    ROOT_CAUSE_CONFIDENCE_THRESHOLD,
    diagnose,
)


def test_diagnose_matches_oom_pattern_with_high_confidence():
    logs = [
        {"timestamp": "2", "message": "Container killed: OOMKilled"},
        {"timestamp": "1", "message": "ERROR previous unrelated log"},
    ]

    diagnosis = diagnose(logs)

    assert diagnosis.category == "OutOfMemory"
    assert diagnosis.confidence == 0.95
    assert diagnosis.requires_human is False


def test_diagnose_matches_network_timeout():
    logs = [{"timestamp": "1", "message": "upstream connection timed out"}]

    diagnosis = diagnose(logs)

    assert diagnosis.category == "NetworkTimeout"
    assert diagnosis.confidence == 0.90


def test_diagnose_most_recent_log_wins():
    # get_pod_logs interroge Loki avec direction="backward" : le log le
    # plus récent (premier de la liste) doit être celui qui déclenche le
    # diagnostic si plusieurs patterns différents matchent.
    logs = [
        {"timestamp": "2", "message": "no space left on device"},
        {"timestamp": "1", "message": "OOMKilled"},
    ]

    diagnosis = diagnose(logs)

    assert diagnosis.category == "DiskFull"


def test_diagnose_no_match_returns_zero_confidence_and_requires_human():
    logs = [{"timestamp": "1", "message": "WARN: retrying request"}]

    diagnosis = diagnose(logs)

    assert diagnosis.category is None
    assert diagnosis.confidence == 0.0
    assert diagnosis.requires_human is True


def test_diagnose_empty_logs_requires_human():
    diagnosis = diagnose([])

    assert diagnosis.category is None
    assert diagnosis.requires_human is True


def test_confidence_threshold_is_80_percent():
    assert ROOT_CAUSE_CONFIDENCE_THRESHOLD == 0.80