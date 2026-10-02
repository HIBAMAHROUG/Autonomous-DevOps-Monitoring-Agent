from remediation.safety import SafetyConfig, SafetyPolicy


def test_max_actions_per_hour_blocks_after_limit():
    policy = SafetyPolicy(SafetyConfig(max_actions_per_hour=1))

    assert policy.check("a1", {}) == (True, "Safety checks passed")
    allowed, reason = policy.check("a2", {})

    assert allowed is False
    assert "Maximum actions per hour exceeded" in reason


def test_max_pod_actions_blocks_loop_for_one_pod():
    policy = SafetyPolicy(
        SafetyConfig(max_pod_actions=1, pod_action_window_minutes=15)
    )

    assert policy.check("a1", {"pod_id": "pod-a"})[0] is True
    allowed, reason = policy.check("a2", {"pod_id": "pod-a"})

    assert allowed is False
    assert "Pod action limit exceeded for pod-a" in reason


def test_circuit_breaker_opens_after_consecutive_failures():
    policy = SafetyPolicy(SafetyConfig(circuit_breaker_failures=2))

    policy.record_result(False)
    policy.record_result(False)
    allowed, reason = policy.check("a1", {})

    assert allowed is False
    assert reason == "Circuit breaker is open"


def test_kill_switch_blocks_all_actions():
    policy = SafetyPolicy()
    policy.activate_kill_switch()

    allowed, reason = policy.check("a1", {})

    assert allowed is False
    assert reason == "Kill switch is active"