-- metabase/analytics.sql

-- AppVista analytical layer.
-- These are read-only views consumed by Metabase.
-- No crawler/storage service depends on these views.

CREATE OR REPLACE VIEW vw_app_catalog AS
SELECT
    a.id AS application_id,
    a.name,
    a.package_name,
    a.category,
    a.is_active,
    a.created_at,
    a.updated_at
FROM applications a;

CREATE OR REPLACE VIEW vw_latest_app_stats AS
SELECT DISTINCT ON (s.application_id)
    s.application_id,
    s.package_name,
    s.crawl_timestamp,
    s.min_installs,
    s.score,
    s.ratings,
    s.reviews,
    s.updated,
    s.version,
    s.ad_supported
FROM app_stats s
ORDER BY s.application_id, s.crawl_timestamp DESC, s.id DESC;

CREATE OR REPLACE VIEW vw_app_score_trend AS
SELECT
    a.id AS application_id,
    a.name,
    a.package_name,
    a.category,
    s.crawl_timestamp,
    s.score AS overall_score,
    s.ratings,
    s.reviews AS review_count,
    s.min_installs
FROM applications a
JOIN app_stats s ON s.application_id = a.id
WHERE s.score IS NOT NULL;

CREATE OR REPLACE VIEW vw_review_score_trend AS
SELECT
    a.id AS application_id,
    a.name,
    a.package_name,
    a.category,
    r.review_at,
    r.score AS review_score,
    r.thumbs_up_count
FROM applications a
JOIN app_reviews r ON r.application_id = a.id
WHERE r.review_at IS NOT NULL;

CREATE OR REPLACE VIEW vw_install_trend AS
SELECT
    a.id AS application_id,
    a.name,
    a.package_name,
    a.category,
    s.crawl_timestamp,
    s.min_installs
FROM applications a
JOIN app_stats s ON s.application_id = a.id
WHERE s.min_installs IS NOT NULL;

CREATE OR REPLACE VIEW vw_network_quality AS
SELECT
    a.id AS application_id,
    a.name,
    a.package_name,
    a.category,
    n.scenario,
    n.captured_at,
    n.handshake_rtt_ms,
    n.retransmission_count,
    n.zero_window_event_count,
    n.tcp_reset_drops,
    n.total_transferred_bytes,
    n.total_payload_bytes,
    n.overhead_ratio,
    n.packet_count,
    n.tcp_packet_count,
    n.tcp_flow_count,
    (
        COALESCE(n.handshake_rtt_ms, 0)
        + COALESCE(n.retransmission_count, 0) * 10.0
        + COALESCE(n.zero_window_event_count, 0) * 25.0
        + COALESCE(n.tcp_reset_drops, 0) * 25.0
    ) AS network_risk_index
FROM applications a
JOIN network_measurements n ON n.application_id = a.id;

CREATE OR REPLACE VIEW vw_messaging_network AS
SELECT
    n.application_id,
    a.name,
    a.package_name,
    a.category,
    n.scenario,
    AVG(n.handshake_rtt_ms)::double precision AS avg_handshake_rtt_ms,
    SUM(n.retransmission_count)::bigint AS retransmissions,
    SUM(n.zero_window_event_count)::bigint AS zero_window_events,
    SUM(n.tcp_reset_drops)::bigint AS tcp_reset_drops,
    AVG(n.overhead_ratio)::double precision AS avg_overhead_ratio,
    AVG(n.total_transferred_bytes)::double precision AS avg_transferred_bytes,
    AVG(n.total_payload_bytes)::double precision AS avg_payload_bytes,
    AVG(n.network_risk_index)::double precision AS avg_network_risk_index
FROM vw_network_quality n
JOIN applications a ON a.id = n.application_id
WHERE lower(a.category) IN (
    'پیام‌رسان', 'پیامرسان', 'messenger', 'messaging', 'chat', 'social'
)
GROUP BY n.application_id, a.name, a.package_name, a.category, n.scenario;

CREATE OR REPLACE VIEW vw_app_business_snapshot AS
SELECT
    a.id AS application_id,
    a.name,
    a.package_name,
    a.category,
    l.min_installs,
    l.score AS latest_score,
    l.ratings,
    l.reviews,
    l.crawl_timestamp,
    COALESCE(review_all.review_score, NULL) AS all_time_review_score,
    COALESCE(review_all.review_count, 0) AS all_time_review_count,
    COALESCE(review_recent.review_score, NULL) AS recent_review_score,
    COALESCE(review_recent.review_count, 0) AS recent_review_count,
    COALESCE(net.avg_rtt_ms, NULL) AS avg_rtt_ms,
    COALESCE(net.avg_overhead_ratio, NULL) AS avg_overhead_ratio,
    COALESCE(net.avg_network_risk, NULL) AS avg_network_risk
FROM applications a
LEFT JOIN vw_latest_app_stats l ON l.application_id = a.id
LEFT JOIN (
    SELECT application_id,
           AVG(score)::double precision AS review_score,
           COUNT(*)::bigint AS review_count
    FROM app_reviews
    WHERE score IS NOT NULL
    GROUP BY application_id
) review_all ON review_all.application_id = a.id
LEFT JOIN (
    SELECT application_id,
           AVG(score)::double precision AS review_score,
           COUNT(*)::bigint AS review_count
    FROM app_reviews
    WHERE score IS NOT NULL
      AND review_at IS NOT NULL
      AND review_at >= timezone('UTC', NOW()) - INTERVAL '30 days'
    GROUP BY application_id
) review_recent ON review_recent.application_id = a.id
LEFT JOIN (
    SELECT application_id,
           AVG(handshake_rtt_ms)::double precision AS avg_rtt_ms,
           AVG(overhead_ratio)::double precision AS avg_overhead_ratio,
           AVG(network_risk_index)::double precision AS avg_network_risk
    FROM vw_network_quality
    GROUP BY application_id
) net ON net.application_id = a.id;