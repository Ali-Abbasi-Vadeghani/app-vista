
QUESTIONS = [
    {
        "name": "Score trend by application",
        "description": "Overall Play Store score per crawl observation.",
        "dashboard": "primary",
        "sql": """SELECT name, category, crawl_timestamp, overall_score
FROM vw_app_score_trend
ORDER BY crawl_timestamp, name;""",
    },
    {
        "name": "Review score trend by application",
        "description": "Individual review scores over time.",
        "dashboard": "primary",
        "sql": """SELECT name, category, review_at, review_score
FROM vw_review_score_trend
ORDER BY review_at, name;""",
    },
    {
        "name": "Installs trend",
        "description": "Minimum installs reported by Play Store per crawl observation.",
        "dashboard": "primary",
        "sql": """SELECT name, category, crawl_timestamp, min_installs
FROM vw_install_trend
ORDER BY crawl_timestamp, name;""",
    },
    {
        "name": "Messaging apps network stability",
        "description": "Network stability indicators for messaging applications.",
        "dashboard": "primary",
        "sql": """SELECT name, scenario, avg_handshake_rtt_ms, retransmissions,
zero_window_events, tcp_reset_drops, avg_overhead_ratio, avg_network_risk_index
FROM vw_messaging_network
ORDER BY avg_network_risk_index NULLS LAST;""",
    },
    {
        "name": "Latest app business snapshot",
        "description": "Latest product, review and network indicators in one table.",
        "dashboard": "primary",
        "sql": """SELECT *
FROM vw_app_business_snapshot
ORDER BY latest_score DESC NULLS LAST;""",
    },
    {
        "name": "Apps with rating-review divergence",
        "description": "Find apps where Play Store aggregate score differs from stored review scores (all-time and last 30 days).",
        "dashboard": "primary",
        "sql": """SELECT name, category,
       latest_score,
       all_time_review_score,
       recent_review_score,
       ROUND((latest_score - all_time_review_score)::numeric, 2) AS gap_vs_all_time,
       ROUND((latest_score - recent_review_score)::numeric, 2) AS gap_vs_recent
FROM vw_app_business_snapshot
WHERE latest_score IS NOT NULL
  AND (all_time_review_score IS NOT NULL OR recent_review_score IS NOT NULL)
ORDER BY GREATEST(
    ABS(COALESCE(latest_score - all_time_review_score, 0)),
    ABS(COALESCE(latest_score - recent_review_score, 0))
) DESC;""",
    },
    {
        "name": "Most engaged reviews",
        "description": "Reviews receiving the most thumbs-up.",
        "dashboard": "secondary",
        "sql": """SELECT a.name, a.category, r.review_at, r.score,
       r.thumbs_up_count, r.content
FROM app_reviews r
JOIN applications a ON a.id = r.application_id
ORDER BY r.thumbs_up_count DESC NULLS LAST
LIMIT 100;""",
    },
    {
        "name": "Network overhead by scenario",
        "description": "Compare transferred bytes, payload and overhead by network scenario.",
        "dashboard": "secondary",
        "sql": """SELECT name, category, scenario,
       AVG(total_transferred_bytes) AS avg_transferred_bytes,
       AVG(total_payload_bytes) AS avg_payload_bytes,
       AVG(overhead_ratio) AS avg_overhead_ratio
FROM vw_network_quality
GROUP BY name, category, scenario
ORDER BY avg_overhead_ratio DESC NULLS LAST;""",
    },
    {
        "name": "Apps with rising or falling installs",
        "description": "Compare each app's first and latest observed minimum installs.",
        "dashboard": "primary",
        "sql": """WITH ranked AS (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY application_id
           ORDER BY crawl_timestamp, min_installs
         ) AS rn_first,
         ROW_NUMBER() OVER (
           PARTITION BY application_id
           ORDER BY crawl_timestamp DESC, min_installs DESC
         ) AS rn_last
  FROM vw_install_trend
),
firsts AS (
  SELECT application_id, name, category, min_installs AS first_installs
  FROM ranked WHERE rn_first = 1
),
lasts AS (
  SELECT application_id, min_installs AS latest_installs
  FROM ranked WHERE rn_last = 1
)
SELECT f.name, f.category, f.first_installs, l.latest_installs,
       (l.latest_installs - f.first_installs) AS install_change,
       CASE WHEN f.first_installs > 0
            THEN ROUND(100.0 * (l.latest_installs - f.first_installs) / f.first_installs, 2)
            ELSE NULL END AS install_change_pct
FROM firsts f JOIN lasts l USING (application_id)
ORDER BY install_change_pct DESC NULLS LAST;""",
    },
]