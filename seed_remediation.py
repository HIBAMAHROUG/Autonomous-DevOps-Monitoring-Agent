import json

from remediation.db_connector import get_dict_cursor


def seed():
    # =========================================================
    # LOAD JSON
    # =========================================================
    with open("storage/known_problems.json", encoding="utf-8") as f:
        problems = json.load(f)

    with open("storage/actions_catalog.json", encoding="utf-8") as f:
        actions = json.load(f)

    print("JSON loaded")
    print(f"Actions found  : {len(actions)}")
    print(f"Problems found : {len(problems)}")

    # =========================================================
    # POSTGRES
    # =========================================================
    with get_dict_cursor() as cur:

        # =====================================================
        # ACTIONS
        # =====================================================
        for action in actions:

            cur.execute(
                """
                INSERT INTO actions (
                    action_id,
                    name,
                    type,
                    executor,
                    params_schema,
                    risk_level,
                    reversible,
                    avg_resolution_time_s,
                    success_rate_historical
                )
                VALUES (
                    %(action_id)s,
                    %(name)s,
                    %(type)s,
                    %(executor)s,
                    %(params_schema)s::jsonb,
                    %(risk_level)s,
                    %(reversible)s,
                    %(avg_resolution_time_s)s,
                    %(success_rate_historical)s
                )
                ON CONFLICT (action_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    executor = EXCLUDED.executor,
                    params_schema = EXCLUDED.params_schema,
                    risk_level = EXCLUDED.risk_level,
                    reversible = EXCLUDED.reversible,
                    avg_resolution_time_s =
                        EXCLUDED.avg_resolution_time_s,
                    success_rate_historical =
                        EXCLUDED.success_rate_historical,
                    updated_at = now()
                """,
                {
                    "action_id": action["action_id"],
                    "name": action["name"],
                    "type": action["type"],
                    "executor": action["executor"],
                    "params_schema": json.dumps(
                        action.get("params_schema", {})
                    ),
                    "risk_level": action["risk_level"],
                    "reversible": action["reversible"],
                    "avg_resolution_time_s": action.get(
                        "avg_resolution_time_s", 0
                    ),
                    "success_rate_historical": action.get(
                        "success_rate_historical", 0.5
                    ),
                },
            )

        # =====================================================
        # PROBLEMS
        # =====================================================
        for problem in problems:

            cur.execute(
                """
                INSERT INTO problems (
                    problem_id,
                    title,
                    category,
                    metric,
                    condition,
                    affected_component,
                    duration_s,
                    known_causes,
                    severity_default,
                    tags
                )
                VALUES (
                    %(problem_id)s,
                    %(title)s,
                    %(category)s,
                    %(metric)s,
                    %(condition)s,
                    %(affected_component)s,
                    %(duration_s)s,
                    %(known_causes)s::jsonb,
                    %(severity_default)s,
                    %(tags)s::jsonb
                )
                ON CONFLICT (problem_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    category = EXCLUDED.category,
                    metric = EXCLUDED.metric,
                    condition = EXCLUDED.condition,
                    affected_component =
                        EXCLUDED.affected_component,
                    duration_s = EXCLUDED.duration_s,
                    known_causes = EXCLUDED.known_causes,
                    severity_default =
                        EXCLUDED.severity_default,
                    tags = EXCLUDED.tags,
                    last_updated = now()
                """,
                {
                    "problem_id": problem["problem_id"],
                    "title": problem["title"],
                    "category": problem["category"],
                    "metric": problem["metric"],
                    "condition": problem["condition"],
                    "affected_component": problem["affected_component"],
                    "duration_s": problem.get("duration_s", 0),
                    "known_causes": json.dumps(
                        problem.get("known_causes", [])
                    ),
                    "severity_default": problem["severity_default"],
                    "tags": json.dumps(
                        problem.get("tags", [])
                    ),
                },
            )

            # =================================================
            # PROBLEM -> ACTIONS
            # =================================================
            cur.execute(
                """
                DELETE FROM problem_actions
                WHERE problem_id = %s
                """,
                (problem["problem_id"],),
            )

            for action_id in problem.get(
                "corrective_actions", []
            ):
                cur.execute(
                    """
                    INSERT INTO problem_actions (
                        problem_id,
                        action_id
                    )
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        problem["problem_id"],
                        action_id,
                    ),
                )

    # =========================================================
    # SUCCESS
    # =========================================================
    print()
    print("=== REMEDIATION SEED ===")
    print(f"Actions  : {len(actions)}")
    print(f"Problems : {len(problems)}")
    print("Relations: loaded")
    print("RESULT   : PASS")


if __name__ == "__main__":
    seed()