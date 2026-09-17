# AppVista

AppVista is a containerized data collection and analytics platform for monitoring Android applications from two complementary perspectives:

- **Google Play Store data** — application metadata, ratings, install counts, and user reviews.
- **Network traffic data** — PCAP-based measurements for selected applications under upload and download scenarios.

The project implements a complete pipeline from data collection to message queuing, persistent storage, analytical views, and Metabase dashboards.

---

## Architecture

The project is composed of independent services that communicate through PostgreSQL and Redis.

- The **API** manages the list of applications that the system tracks. It acts as the source of truth for active applications.
- The **Crawler** periodically reads the active application list from the API and scrapes Google Play Store for stats and reviews. It publishes results to Redis queues.
- The **Network Analyzer** receives PCAP files through an HTTP endpoint, extracts network quality metrics using Scapy, and publishes the results to Redis.
- The **Storage** service consumes Redis queues and writes everything into PostgreSQL in a structured way.
- **Metabase** connects to PostgreSQL and provides the analytical layer, dashboards, and SQL views over the stored data.

All components are Dockerized and orchestrated through Docker Compose.

---

## Main Components

### 1. Application Management API

The `api/` service provides a FastAPI-based CRUD API for managing the applications that participate in the crawling process.

Each application contains `name`, `package_name`, `category`, `is_active`, and creation/update timestamps.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | API status |
| `GET` | `/health` | Health check |
| `POST` | `/applications` | Create an application |
| `GET` | `/applications` | List applications |
| `GET` | `/applications/{id}` | Retrieve one application |
| `PUT` | `/applications/{id}` | Update an application |
| `DELETE` | `/applications/{id}` | Deactivate an application |

The API uses PostgreSQL through SQLAlchemy and enforces unique application package names.

**Why FastAPI instead of Django REST Framework or Flask?** FastAPI was chosen because it provides automatic OpenAPI/Swagger documentation out of the box (available at `/docs`), native support for Pydantic v2 for request/response validation, and async request handling. For a service with only a handful of CRUD endpoints, Django REST Framework would introduce significant framework overhead (ORM admin, migrations, settings layout) that is not justified. Flask, while lighter, requires manual setup for validation and documentation, which FastAPI provides for free.

**Why SQLAlchemy 2.0?** SQLAlchemy is the de-facto ORM in Python and works consistently across both PostgreSQL (production) and SQLite (tests). Its 2.0 style with `Mapped[...]` typing gives static type checking and better readability than raw SQL or lighter alternatives such as `databases`.

---

### 2. Google Play Store Crawler

The `crawler/` service periodically collects application information from Google Play Store using `google-play-scraper`.

For each configured application, the crawler collects:

- Minimum installs, overall score, ratings count, reviews count
- Last update information, application version, advertisement support

For user reviews, it preserves the review ID, timestamp, user name, helpful vote count, score, and content.

Review messages are identified by `reviewId`, allowing the storage layer to update existing reviews instead of treating every crawl as a new record. The default crawl interval is one hour. To reduce request pressure, configurable delays are used between requests. HTTP/HTTPS proxies can also be configured through environment variables.

**Why `google-play-scraper`?** Google Play does not offer a public API for reading application reviews; the only reliable way to obtain them is to parse the Play Store web pages. `google-play-scraper` is a mature, actively maintained library that handles pagination, retries, and the internal Play Store API that is called by the website. It also supports sorting by newest reviews and batch retrieval with a continuation token.

**Alternatives considered.** `play-scraper` and `google-play-api` are less actively maintained and do not support the review pagination format that the current Play Store uses. Building a custom scraper directly with `requests` and `BeautifulSoup` was rejected because Play Store's internal API is undocumented and changes frequently — maintaining a hand-rolled parser would be fragile and out of scope.

**Why `tenacity` for retries?** Play Store can return transient HTTP errors (rate limits, incomplete reads, connection resets). `tenacity` provides a declarative retry policy with exponential backoff and integrates cleanly with the existing fetch functions.

**Why `apscheduler`?** The crawler needs to trigger a recurring job for every active application with a jitter to avoid synchronised bursts. `apscheduler` provides an in-process scheduler with an interval trigger and per-job configuration, which is enough for this project. A heavier alternative like Celery Beat would require an additional worker and broker, and is not justified at this scale.

---

### 3. Redis Message Queues

Redis is used as the messaging layer between data producers and the storage service.

The crawler publishes to `playstore:stats` and `playstore:reviews`. Network measurements are published to `network:measurements`.

Each message contains a generated `message_id` and an enqueue timestamp in addition to its payload. Redis operations include retry handling for connection errors and batched publishing for review messages.

**Why Redis lists instead of Kafka or RabbitMQ?** The project requires a simple, low-latency buffer between producers and a single consumer, with at-least-once semantics for the duration of the buffer. Redis lists with `RPUSH` and `LPOP` provide exactly that with almost no operational cost. Kafka would introduce topics, partitions, consumer groups, and a broker to manage, which is overkill for a single-consumer pipeline. RabbitMQ would add a heavier messaging protocol and additional configuration. Redis was already required elsewhere in the stack (as a cache layer for Metabase), so reusing it keeps the number of moving parts small.

---

### 4. Network Traffic Analyzer

The `network_analyzer/` service analyzes PCAP/PCAPNG files captured from network traffic.

It exposes `POST /analyze`, which accepts a PCAP/PCAPNG file, a package name, and a scenario (`upload` or `download`). The analyzer validates the application against the configured package allow-list and enforces a maximum PCAP size.

The analyzer calculates network indicators such as packet count, TCP packet count, TCP flow count, handshake RTT, TCP retransmission count, zero-window events, TCP reset drops, total transferred bytes, total payload bytes, and network overhead ratio.

The resulting measurement is published to Redis and later persisted by the storage service. The health endpoint is at `http://localhost:8010/health`.

**Why Scapy?** Scapy is the standard Python library for reading and dissecting network captures. It supports both `.pcap` and `.pcapng`, exposes TCP flags, sequence numbers, window sizes, and payloads with a uniform API, and streams packets via `PcapReader`/`PcapNgReader` without loading the entire capture into memory. This streaming behaviour is essential for large captures.

**Alternatives considered.** `dpkt` is faster but lower-level, requires manual parsing of TCP flags and options, and does not provide the same clean object model. `pyshark` wraps `tshark` and requires installing Wireshark binaries in the image, which would significantly increase the image size and add a non-Python runtime dependency. A pure-`ctypes` libpcap binding was rejected as too low-level and error-prone for the metrics this project needs.

**Why is the analysis done in Python and not in SQL or in Metabase?** Retransmission detection, TCP handshake RTT, and zero-window events require reasoning across consecutive packets in the same flow. SQL has no natural way to express this. Doing it once in the analyzer and persisting the aggregated metrics into `network_measurements` keeps the database queryable and dashboards fast.

---

### 5. Storage Service

The `storage/` service continuously consumes messages from Redis and persists the resulting data in PostgreSQL.

Its responsibilities include consuming Play Store statistics, reviews, and network measurements; parsing and normalizing incoming data; creating or updating database records; and maintaining historical observations with crawl timestamps.

This historical storage makes it possible to analyze changes over time rather than only the latest state of an application.

**Why a dedicated consumer instead of writing directly from producers?** Keeping writers decoupled from readers avoids a tight coupling between the crawler/analyzer and the PostgreSQL schema. If the schema evolves, only the storage service needs to change. It also allows the producers to keep operating even if the database is temporarily unavailable.

**Why batch upserts and savepoints?** Each consumer loop drains a bounded number of messages per queue and applies them in a single transaction. Reviews use a grouped `IN (...)` lookup instead of one `SELECT` per review, and network measurements are staged inside savepoints so that a single malformed message cannot roll back an entire batch.

---

### 6. PostgreSQL Data Layer

PostgreSQL is the central persistent data store. The project separates application metadata, application statistics, user reviews, and network measurements from the analytical layer.

The Metabase bootstrap process creates and maintains SQL-based analytical views over the stored data. These views provide a cleaner interface for business and trend analysis without requiring dashboard queries to directly reconstruct the underlying data model.

**Why PostgreSQL?** PostgreSQL is the natural choice for a data platform that also uses Metabase: Metabase officially recommends it as the application database in production, and it handles the operational tables (statistics, reviews, measurements) with the same instance. Features used in this project include `timezone`-aware timestamps, `DISTINCT ON`, window functions, `CREATE OR REPLACE VIEW`, and savepoints.

---

### 7. Metabase Analytics

The `metabase/` service provides the visualization and analytical layer.

During startup, the bootstrap service waits for PostgreSQL, applies the analytical SQL views, waits for Metabase, configures the PostgreSQL data source, creates or updates analytical questions, and provisions the AppVista dashboard.

The project includes analytical questions covering application performance, review behavior, popularity, and network quality — for example:

- Score trend by application
- Review score trend by application
- Install trends
- Messaging application network stability
- Latest application business snapshot
- Messaging application network comparison
- Rating/review divergence
- Popularity vs. quality classification
- Average score of the latest 100 reviews
- Review volume over time

The dashboard combines Play Store and network indicators to support analysis of application quality, popularity, user feedback, and network behavior. Metabase is available at `http://localhost:3000`.

**Why Metabase instead of Grafana, Superset or Kibana?** Metabase is explicitly named in the project specification and is one of the few self-hosted BI tools that a non-technical user can operate without writing SQL. It offers a native SQL editor, a visual query builder, saved questions, and dashboards with an approachable UI. Grafana is designed for time-series monitoring rather than ad-hoc business analysis. Superset is more powerful but requires more setup and a steeper learning curve. Kibana is tied to the Elasticsearch ecosystem. Metabase also has a well-documented HTTP API, which this project uses to provision questions and dashboards automatically.

**Why a custom `metabase-bootstrap` job?** Metabase does not ship with a native "provision from file" mechanism. Without it, every deployment would require creating dashboards by hand. The bootstrap job uses the Metabase HTTP API to install views, connect the data source, create or update each question, and reconcile the dashboard. It is idempotent: re-running it does not duplicate questions or cards.

**Why an init container for the Metabase database?** Metabase needs its own application database to store users, dashboards, and metadata, and this must exist before Metabase starts. The `metabase-db-init` container creates that database idempotently inside the same PostgreSQL instance, keeping the setup self-contained.

---

## Dockerized Deployment

The complete stack is defined in `docker-compose.yml`. It includes PostgreSQL, Redis, Metabase, Metabase database initialization, Metabase bootstrap, the FastAPI application service, the Play Store crawler, the network analyzer, and the storage consumer.

Health checks and service dependencies are configured so that services start in the required order. PostgreSQL data is stored in a persistent Docker volume named `postgres_data`, and stopping the stack with the provided setup script does not remove this volume.

**Why Docker Compose and not Kubernetes?** The project runs on a single machine and needs a predictable local deployment. Compose is the lowest-friction way to express multi-service startup order, health checks, and shared networks without the operational cost of a cluster. Docker was an explicit requirement of the project.

---

## Quick Start

### Requirements

Install the following on the host machine: Docker, Docker Compose V2, and Git. Make sure the Docker daemon is running.

### Start the project

From the repository root:

```bash
bash setup.sh
```