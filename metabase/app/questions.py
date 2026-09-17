# metabase/app/questions.py

QUESTIONS = [
    {
        "name": "Score trend by application",
        "description": "Overall Play Store score per crawl observation.",
        "dashboard": "primary",
        "display": "line",
        "visualization_settings": {
            "graph.dimensions": ["crawl_timestamp", "name"],
            "graph.metrics": ["overall_score"],
            "graph.y_axis.auto_range": False,
            "graph.y_axis.min": 3.5,
            "graph.y_axis.max": 5,
            "graph.show_trendline": False,
            "graph.show_values": False,
        },
        "sql": """SELECT name, category, crawl_timestamp, overall_score
FROM vw_app_score_trend
ORDER BY crawl_timestamp, name;""",
    },
    {
        "name": "Review score trend by application",
        "description": "Weekly average review score for the last 365 days, only weeks with at least 10 reviews.",
        "dashboard": "primary",
        "display": "line",
        "visualization_settings": {
            "graph.dimensions": ["review_week", "name"],
            "graph.metrics": ["avg_score"],
        },
        "sql": """SELECT
    name,
    date_trunc('week', review_at) AS review_week,
    AVG(review_score) AS avg_score,
    COUNT(*) AS review_count
FROM vw_review_score_trend
WHERE review_at >= NOW() - INTERVAL '365 days'
GROUP BY name, date_trunc('week', review_at)
HAVING COUNT(*) >= 10
ORDER BY review_week, name;""",
    },
    {
        "name": "Installs trend",
        "description": "Maximum reported minimum installs per application, on a log scale bar chart.",
        "dashboard": "primary",
        "display": "bar",
        "visualization_settings": {
            "graph.dimensions": ["name"],
            "graph.metrics": ["min_installs"],
            "graph.y_axis.scale": "log",
            "graph.y_axis.auto_range": False,
            "graph.y_axis.min": 1000,
            "graph.y_axis.max": 10000000,
        },
        "sql": """SELECT
    name,
    MAX(min_installs) AS min_installs
FROM vw_install_trend
GROUP BY name
ORDER BY min_installs DESC;""",
    },
    {
        "name": "Messaging apps network stability",
        "description": "Network stability indicators for messaging applications.",
        "dashboard": "primary",
        "display": "table",
        "visualization_settings": {},
        "sql": """SELECT name, scenario, avg_handshake_rtt_ms, retransmissions,
zero_window_events, tcp_reset_drops, avg_overhead_ratio, avg_network_risk_index
FROM vw_messaging_network
ORDER BY avg_network_risk_index NULLS LAST;""",
    },
    {
        "name": "Latest app business snapshot",
        "description": "Latest product, review and network indicators in one table.",
        "dashboard": "primary",
        "display": "table",
        "visualization_settings": {
            "table.columns": [
                {"name": "application_id", "enabled": False},
                {"name": "name", "enabled": True},
                {"name": "package_name", "enabled": True},
                {"name": "category", "enabled": True},
                {"name": "min_installs", "enabled": True},
                {"name": "latest_score", "enabled": True},
                {"name": "ratings", "enabled": True},
                {"name": "reviews", "enabled": True},
                {"name": "crawl_timestamp", "enabled": True},
                {"name": "all_time_review_score", "enabled": True},
                {"name": "all_time_review_count", "enabled": True},
                {"name": "recent_review_score", "enabled": True},
                {"name": "recent_review_count", "enabled": True},
                {"name": "avg_rtt_ms", "enabled": False},
                {"name": "avg_overhead_ratio", "enabled": False},
                {"name": "avg_network_risk", "enabled": False},
            ],
            "table.pivot_column": "avg_rtt_ms",
            "table.cell_column": "min_installs",
            "table.column_formatting": [
                {
                    "id": 0,
                    "type": "range",
                    "operator": "=",
                    "columns": ["latest_score"],
                    "colors": ["#ED6E6E", "#FFFFFF", "#84BB4C"],
                    "min_type": "custom",
                    "min_value": 2.9,
                    "max_type": None,
                    "max_value": 100,
                    "highlight_row": False,
                }
            ],
        },
        "sql": """SELECT *
FROM vw_app_business_snapshot
ORDER BY latest_score DESC NULLS LAST;""",
    },
    {
        "name": "Messaging apps — Combo comparison",
        "description": "Compare RTT, zero-window events, TCP resets and overhead for messaging apps across upload and download scenarios.",
        "dashboard": "primary",
        "display": "combo",
        "visualization_settings": {
            "graph.dimensions": ["name"],
            "graph.metrics": ["zero_window", "rst", "rtt_ms", "overhead_x1000"],
        },
        "sql": """SELECT name, scenario,
       avg_handshake_rtt_ms AS rtt_ms,
       zero_window_events AS zero_window,
       tcp_reset_drops AS rst,
       avg_overhead_ratio * 1000 AS overhead_x1000
FROM vw_messaging_network
ORDER BY avg_network_risk_index DESC NULLS LAST;""",
    },
    {
        "name": "Apps with rating review divergence",
        "description": "Compare Play Store aggregate score with the last 30 days review score and label the divergence.",
        "dashboard": "primary",
        "display": "bar",
        "visualization_settings": {
            "table.pivot_column": "status",
            "table.cell_column": "latest_score",
            "graph.dimensions": ["name", "status"],
            "graph.metrics": ["gap"],
            "graph.series_order_dimension": None,
            "graph.series_order": None,
            "column_settings": {
                "[\"name\",\"gap\"]": {"show_mini_bar": True}
            },
            "series_settings": {
                "Play Store overrates": {"color": "#51528D"},
                "In sync": {"color": "#88BF4D"},
                "Reviews more positive": {"color": "#E75454"},
            },
        },
        "sql": """SELECT
    name,
    category,
    latest_score,
    all_time_review_score,
    recent_review_score,
    ROUND((latest_score - recent_review_score)::numeric, 2) AS gap,
    CASE
        WHEN latest_score - recent_review_score > 0.3 THEN 'Play Store overrates'
        WHEN latest_score - recent_review_score < -0.3 THEN 'Reviews more positive'
        ELSE 'In sync'
    END AS status
FROM vw_app_business_snapshot
WHERE latest_score IS NOT NULL
  AND recent_review_score IS NOT NULL
ORDER BY ABS(latest_score - recent_review_score) DESC;""",
    },
    {
        "name": "Popularity vs quality matrix",
        "description": "Scatter plot of apps by install count (popularity) and latest score (quality), with bubble size showing review count.",
        "dashboard": "primary",
        "display": "scatter",
        "visualization_settings": {
            "graph.dimensions": ["min_installs", "category"],
            "graph.metrics": ["latest_score"],
            "scatter.bubble": "reviews",
            "graph.x_axis.scale": "histogram",
            "graph.series_order_dimension": None,
            "graph.series_order": None,
        },
        "sql": """SELECT
    name,
    category,
    min_installs,
    latest_score,
    reviews,
    CASE
        WHEN min_installs >= 1000000000 THEN 'High Popularity'
        WHEN min_installs >= 10000000  THEN 'Medium Popularity'
        ELSE 'Low Popularity'
    END AS popularity_band,
    CASE
        WHEN latest_score >= 4.5 THEN 'High Quality'
        WHEN latest_score >= 3.5 THEN 'Medium Quality'
        WHEN latest_score IS NOT NULL THEN 'Low Quality'
        ELSE 'Unknown'
    END AS quality_band,
    CASE
        WHEN min_installs >= 1000000000 AND latest_score < 3.5 THEN TRUE
        ELSE FALSE
    END AS is_mismatch
FROM vw_app_business_snapshot
WHERE min_installs IS NOT NULL
  AND latest_score IS NOT NULL
ORDER BY min_installs DESC;""",
    },
    {
        "name": "Average score of last 100 reviews",
        "description": "Average score of the most recent 100 reviews for each application; apps with fewer than 100 reviews use all stored reviews.",
        "dashboard": "primary",
        "display": "bar",
        "visualization_settings": {
            "graph.dimensions": ["name"],
            "graph.metrics": ["avg_last_100_score"],
            "graph.y_axis.auto_range": False,
            "graph.y_axis.min": 1,
            "graph.y_axis.max": 5,
        },
        "sql": """WITH ranked_reviews AS (
    SELECT
        name,
        review_score,
        ROW_NUMBER() OVER (
            PARTITION BY name
            ORDER BY review_at DESC NULLS LAST
        ) AS rn
    FROM vw_review_score_trend
    WHERE review_score IS NOT NULL
)
SELECT
    name,
    ROUND(AVG(review_score)::numeric, 2) AS avg_last_100_score,
    COUNT(*) AS reviews_used
FROM ranked_reviews
WHERE rn <= 100
GROUP BY name
ORDER BY avg_last_100_score DESC NULLS LAST;""",
    },
    {
        "name": "Review volume per application (3-hour buckets)",
        "description": "Number of reviews written by users in 3-hour buckets over time, filtered by application.",
        "dashboard": "primary",
        "display": "line",
        "visualization_settings": {
            "graph.dimensions": ["review_bucket", "name"],
            "graph.metrics": ["review_count"],
        },
        "sql": """SELECT
    name,
    date_trunc('hour', review_at) +
        INTERVAL '3 hour' * FLOOR(EXTRACT(HOUR FROM review_at)::int / 3) AS review_bucket,
    COUNT(*) AS review_count
FROM vw_review_score_trend
WHERE review_at IS NOT NULL
  AND {{app_filter}}
GROUP BY name, review_bucket
ORDER BY review_bucket;""",
    },
]