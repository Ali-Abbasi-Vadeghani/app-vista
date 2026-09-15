import re

import pytest

from app.questions import QUESTIONS


def test_questions_is_non_empty():
    assert len(QUESTIONS) > 0


def test_every_question_has_required_fields():
    for q in QUESTIONS:
        assert "name" in q
        assert "sql" in q
        assert "description" in q
        assert q["name"]
        assert q["sql"].strip()


def test_every_question_has_valid_dashboard_scope():
    for q in QUESTIONS:
        scope = q.get("dashboard", "primary")
        assert scope in {"primary", "secondary"}


def test_question_names_are_unique():
    names = [q["name"] for q in QUESTIONS]
    assert len(names) == len(set(names))


def test_primary_and_secondary_partitions():
    primary = [q for q in QUESTIONS if q.get("dashboard") == "primary"]
    secondary = [q for q in QUESTIONS if q.get("dashboard") == "secondary"]
    assert len(primary) + len(secondary) == len(QUESTIONS)
    assert len(primary) >= 1


def test_primary_questions_include_required_analyses():
    names = {
        q["name"] for q in QUESTIONS if q.get("dashboard") == "primary"
    }
    assert "Score trend by application" in names
    assert "Review score trend by application" in names
    assert "Installs trend" in names
    assert "Messaging apps network stability" in names


def test_secondary_questions_are_off_dashboard():
    secondary = {
        q["name"] for q in QUESTIONS if q.get("dashboard") == "secondary"
    }
    assert "Most engaged reviews" in secondary
    assert "Network overhead by scenario" in secondary


KNOWN_SOURCES = {
    "vw_app_score_trend",
    "vw_review_score_trend",
    "vw_install_trend",
    "vw_messaging_network",
    "vw_app_business_snapshot",
    "vw_network_quality",
    "vw_latest_app_stats",
    "vw_app_catalog",
    "applications",
    "app_reviews",
    "app_stats",
    "network_measurements",
}

SQL_KEYWORDS = {"select", "where", "group", "order", "limit", "on", "as"}


def _extract_references(sql: str) -> set[str]:
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        re.IGNORECASE,
    )
    refs = set()
    for match in pattern.finditer(sql):
        token = match.group(1).lower()
        if token in SQL_KEYWORDS:
            continue
        refs.add(token)
    return refs


def test_questions_reference_known_views():
    cte_names = {"ranked", "firsts", "lasts"}

    for q in QUESTIONS:
        refs = _extract_references(q["sql"]) - cte_names
        unknown = refs - KNOWN_SOURCES
        assert not unknown, (
            f"Unknown source(s) {unknown} in question '{q['name']}'"
        )


def test_no_legacy_network_risk_score_reference():
    for q in QUESTIONS:
        assert "network_risk_score" not in q["sql"], q["name"]


