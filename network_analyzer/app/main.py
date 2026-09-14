
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from .analyzer import analyze_pcap
from .api_client import get_application_id
from .logging_config import setup_logging
from .redis_client import publish_network_measurement


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
setup_logging(level=getattr(logging, LOG_LEVEL, logging.INFO))

logger = logging.getLogger("network-analyzer")


ALLOWED_SCENARIOS = {"upload", "download"}
ALLOWED_EXTENSIONS = {".pcap", ".pcapng"}

_allowed_packages_raw = os.getenv("ALLOWED_PACKAGES", "").strip()
ALLOWED_PACKAGES = {
    item.strip()
    for item in _allowed_packages_raw.split(",")
    if item.strip()
}

MAX_PCAP_BYTES = int(
    os.getenv("MAX_PCAP_BYTES", str(500 * 1024 * 1024))
)


class MetricsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    application_id: int
    package_name: str
    scenario: str
    pcap_filename: str
    pcap_sha256: str
    captured_at: str | None

    packet_count: int
    tcp_packet_count: int
    tcp_flow_count: int

    handshake_rtt_ms: float | None
    retransmission_count: int
    zero_window_event_count: int
    tcp_reset_drops: int

    total_transferred_bytes: int
    total_payload_bytes: int
    overhead_ratio: float | None


class AnalyzeResponse(BaseModel):
    status: str
    message_id: str
    metrics: MetricsResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Network analyzer starting: allowed_packages=%s max_pcap_bytes=%s",
        ALLOWED_PACKAGES or "(all)",
        MAX_PCAP_BYTES,
    )
    yield
    logger.info("Network analyzer shutting down")


app = FastAPI(
    title="AppVista Network Traffic Analyzer",
    version="3.0.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {
        "service": "network-analyzer",
        "status": "ok",
        "version": app.version,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(...),
    package_name: str = Form(...),
    scenario: str = Form(...),
):
    package_name = package_name.strip()
    scenario = scenario.strip().lower()

    logger.info(
        "Received analyze request package=%s scenario=%s filename=%s",
        package_name,
        scenario,
        file.filename,
    )

    if ALLOWED_PACKAGES and package_name not in ALLOWED_PACKAGES:
        logger.warning("Rejected disallowed package=%s", package_name)
        raise HTTPException(
            status_code=400,
            detail=f"Package is not allowed: {package_name}",
        )

    if scenario not in ALLOWED_SCENARIOS:
        logger.warning("Rejected invalid scenario=%s", scenario)
        raise HTTPException(
            status_code=400,
            detail="scenario must be either 'upload' or 'download'",
        )

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        logger.warning("Rejected invalid extension=%s", suffix)
        raise HTTPException(
            status_code=400,
            detail="Only .pcap and .pcapng files are supported",
        )

    try:
        application_id = get_application_id(package_name)
    except Exception as exc:
        logger.exception("Failed to fetch applications from the API")
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach the API service: {exc}",
        ) from exc

    if application_id is None:
        logger.warning(
            "Active application not found package=%s", package_name
        )
        raise HTTPException(
            status_code=404,
            detail=f"Active application not found for package: {package_name}",
        )

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            prefix="appvista-network-",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            total_size = 0

            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_PCAP_BYTES:
                    logger.warning(
                        "Upload exceeds max size package=%s size=%s",
                        package_name,
                        total_size,
                    )
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"PCAP exceeds maximum allowed size "
                            f"({MAX_PCAP_BYTES} bytes)"
                        ),
                    )

                temp_file.write(chunk)

        logger.info(
            "Saved uploaded pcap to temp path=%s size=%s",
            temp_path,
            total_size,
        )

        metrics = analyze_pcap(
            path=temp_path,
            application_id=application_id,
            package_name=package_name,
            scenario=scenario,
            pcap_filename=file.filename or temp_path.name,
        )

        try:
            message_id = publish_network_measurement(metrics)
        except Exception as exc:
            logger.exception("Failed to publish network measurement to Redis")
            raise HTTPException(
                status_code=503,
                detail=f"Could not publish to Redis: {exc}",
            ) from exc

        response_metrics = MetricsResponse(
            **{
                **metrics,
                "captured_at": (
                    metrics["captured_at"].isoformat()
                    if metrics["captured_at"] is not None
                    else None
                ),
            }
        )

        logger.info(
            "Analyze request completed package=%s scenario=%s message_id=%s",
            package_name,
            scenario,
            message_id,
        )

        return AnalyzeResponse(
            status="success",
            message_id=message_id,
            metrics=response_metrics,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("PCAP analysis failed package=%s", package_name)
        raise HTTPException(
            status_code=422,
            detail=f"PCAP analysis failed: {exc}",
        ) from exc
    finally:
        await file.close()

        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
                logger.debug("Removed temp file %s", temp_path)
            except OSError:
                logger.warning("Failed to remove temp file %s", temp_path)