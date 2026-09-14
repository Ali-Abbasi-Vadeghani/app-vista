from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppStats(Base):
    __tablename__ = "app_stats"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    application_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    package_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    crawl_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    min_installs: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    ratings: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    reviews: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    updated: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    ad_supported: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AppReview(Base):
    __tablename__ = "app_reviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    application_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    package_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    review_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    thumbs_up_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    crawl_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "package_name",
            "review_id",
            name="uq_app_reviews_package_review",
        ),
    )


class NetworkMeasurement(Base):
    __tablename__ = "network_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scenario: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    pcap_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    pcap_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    packet_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tcp_packet_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tcp_flow_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    handshake_rtt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    retransmission_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    zero_window_event_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tcp_reset_drops: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    total_transferred_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_payload_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    overhead_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "scenario",
            "pcap_sha256",
            name="uq_network_measurement_capture",
        ),
    )    