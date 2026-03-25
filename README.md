# Report Export Service

This project is a FastAPI-based service that accepts a text file, builds frequency statistics for word forms, and returns the result as an Excel report.

The original task can be summarized like this:

- implement a FastAPI endpoint that accepts a text file
- the file may be very large, from kilobytes to gigabytes
- each line contains words
- words should be normalized to their base form, so different inflected forms are treated as the same word
- the report should contain the normalized word form, total count in the document, and per-line counts
- the result should be written as an `xlsx` file
- the service should remain available even when several users upload large files at the same time
- code structure should preferably follow a layered or DDD-like style

## What is implemented

The final solution is asynchronous. A single synchronous request is not a good fit for large files, so the processing flow is split into three steps:

1. `POST /public/report/export` uploads the file and creates a job.
2. `GET /public/report/export/{job_id}` returns the current job status.
3. `GET /public/report/export/{job_id}/download` downloads the generated report.

There is also a simple `GET /health` endpoint.

This split is intentional. Large reports can take noticeable time to build, so returning a `job_id` and processing the file in a worker is safer than keeping the HTTP request open.

## Main idea

The service is built around a simple separation of concerns:

- `api` contains FastAPI routers, schemas, handlers and dependency wiring.
- `application` contains the main use cases such as report export and report build.
- `domain` contains core entities and abstractions.
- `infra` contains concrete infrastructure: temporary storage, tokenizer, lemmatizer, queue adapter, SQL persistence, XLSX writer, cleaner, logging.
- `worker` contains the background task entrypoint used by RQ.

The current architecture is close to a lightweight DDD style: business flow is kept in application services, while infrastructure details are hidden behind repositories and adapters.

## Stack

The project uses the following stack:

- Python 3.12+
- FastAPI
- RQ
- Redis
- PostgreSQL
- SQLite
- SQLAlchemy
- pymorphy3
- XlsxWriter
- Docker
- Docker Compose
- unittest

## Processing pipeline

### 1. Upload

The API accepts a multipart file and saves it chunk by chunk to disk. The upload is not loaded fully into memory.

Validation is done in storage before the file is persisted:

- file extension must be `.txt`
- declared content type must be text-like
- the first chunk is inspected to reject obvious binary payloads
- the first chunk must decode as text

This means the service does not blindly trust client metadata.

### 2. Queueing

After the file is saved, the API creates a background job in Redis via RQ and returns `202 Accepted` with `job_id`.

Heavy work is done in a separate worker process, so large jobs do not block the web process.

### 3. Processing

The worker:

- reads the file line by line
- tokenizes words
- normalizes word forms through `pymorphy3`
- aggregates counts in a temporary SQLite database
- builds the final XLSX report

### 4. Status tracking

Redis is used only as a queue. Job status is stored in PostgreSQL.

This is important because queue data can expire or be cleaned, while the API should still be able to return the job status after processing is complete.

### 5. Cleanup

A separate cleaner container runs on cron and removes old files from:

- `uploads`
- `work`

Result files are intentionally not deleted automatically, so users can download them later.

## Report format

The report contains three logical columns:

1. lemma / normalized word form
2. total count in the whole document
3. counts by line

Originally the third column in the task looked like this:

```text
0,11,32,0,0,3
```

That dense representation becomes impractical on large files. If a document has many lines and many distinct lemmas, the output size explodes and the write phase becomes the real bottleneck. It also collides with Excel cell size limits.

Because of that, the current implementation uses a sparse representation:

```text
2:11,3:32,6:3
```

Here each fragment means `line_no:count`, and only non-zero values are stored.

This is the main performance-oriented deviation from the original literal format. The meaning of the data is preserved, but the result becomes feasible for large files.

If strict compliance with the dense string is required, the write phase becomes dramatically heavier and for some inputs effectively impractical.

## Performance-related decisions

Several changes were introduced specifically to make the service usable with larger inputs.

### Asynchronous processing through queue + worker

The API only accepts the file and creates a job. The actual report generation happens in a separate worker process.

This keeps the FastAPI application responsive when multiple users upload large files.

### Chunked upload to disk

Files are written to disk in chunks instead of being buffered completely in memory.

### Temporary SQLite aggregation

Intermediate statistics are stored in SQLite inside the `work` directory. This avoids keeping the entire dataset in memory and makes it possible to process larger files safely.

### Builder optimizations

The report builder includes several optimizations:

- large buffer size for batch flushing to SQLite
- SQLite `PRAGMA` settings for faster temporary writes
- line-by-line streaming instead of loading the full document
- `pymorphy3` lemma cache for repeated tokens
- sparse per-line count format instead of dense zero-filled strings

Without the sparse format, the write phase quickly becomes the slowest part of the whole pipeline.

### Durable status storage in PostgreSQL

Status is stored in PostgreSQL instead of reading it directly from RQ. This makes `GET /public/report/export/{job_id}` stable even after queue metadata is gone.

### Logging

Two dedicated log streams were added:

- `app.builder`
- `app.cleaner`

Builder logs include:

- start and finish of build
- SQLite flush statistics
- progress by processed lines
- estimated write phase size
- lemmatizer cache hits and misses
- total timings

Cleaner logs include:

- start and finish of cleanup
- deleted file names
- cleanup timings

## API

### `POST /public/report/export`

Accepts a multipart file field named `file`.

Example response:

```json
{
  "job_id": "6bfc5f6f4c384c16b5d6f8c366fd9f0f",
  "status": "queued"
}
```

### `GET /public/report/export/{job_id}`

Returns current status.

Example response:

```json
{
  "job_id": "6bfc5f6f4c384c16b5d6f8c366fd9f0f",
  "status": "finished",
  "download_url": "http://localhost:8000/public/report/export/6bfc5f6f4c384c16b5d6f8c366fd9f0f/download",
  "error_msg": null
}
```

Possible statuses:

- `queued`
- `started`
- `finished`
- `failed`

### `GET /public/report/export/{job_id}/download`

Downloads the generated `xlsx` file.

### `GET /health`

Returns:

```json
{
  "status": "ok"
}
```

## Running the project

## Build

### Build with Docker Compose

Build all containers:

```bash
docker compose build
```

Build and start the whole project in one command:

```bash
docker compose up --build
```

If the images are already built:

```bash
docker compose up
```

### Build API image directly

If you want to build the application image without starting the full stack:

```bash
docker build -f app/Dockerfile -t report-export-service .
```

### Local setup without Docker

Create a virtual environment, install dependencies and run the app locally:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Then start the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For the full local stack you would also need Redis, PostgreSQL and a separate RQ worker.

### Docker Compose

The easiest way to run the project is through Docker Compose.

Services:

- `api` - FastAPI application
- `worker` - background processor
- `redis` - RQ backend
- `postgres` - job status storage
- `cleaner` - cron-based cleanup service

Start the system:

```bash
docker compose up --build
```

Run several workers in parallel:

```bash
docker compose up --build --scale worker=3
```

If the images are already built:

```bash
docker compose up --scale worker=3
```

API will be available at:

```text
http://localhost:8000
```

## Environment variables

The main variables are defined in `.env.example`.

Important ones:

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `REPORT_QUEUE_NAME`
- `REPORT_DATABASE_URL`
- `REPORT_UPLOADS_DIR`
- `REPORT_RESULTS_DIR`
- `REPORT_WORK_DIR`
- `RQ_JOB_TIMEOUT_SECONDS`
- `RQ_RESULT_TTL_SECONDS`
- `RQ_FAILURE_TTL_SECONDS`
- `CLEANER_CRON_SCHEDULE`
- `CLEANER_UPLOADS_TTL_HOURS`
- `CLEANER_WORK_TTL_HOURS`

## Data directories

When the project is started with Docker Compose, these directories are mounted from the current project:

- `./data/uploads`
- `./data/results`
- `./data/work`

This makes it easy to inspect uploaded files, generated reports and temporary SQLite files locally.

## Tests

There are integration tests for:

- health endpoint
- successful export request
- invalid upload rejection
- status endpoint
- download endpoint
- sparse per-line count generation
- XLSX column splitting for long cell values

Run tests with:

```bash
python -m unittest discover -s tests/integration -v
```

## Logging

Container logs are enough to inspect the system in practice:

```bash
docker compose logs api
docker compose logs worker
docker compose logs cleaner
```

The most informative stream during report generation is usually the worker log.

## Scalability

The project is designed to handle large files better than a single synchronous FastAPI endpoint would.

What already scales reasonably well:

- the API does not perform heavy report generation itself
- report generation is moved to background workers
- several worker containers can consume the same Redis queue in parallel
- uploaded files, temporary work files and final results are stored on disk instead of in memory
- job status is stored in PostgreSQL, so status checks do not depend on worker memory or Redis job lifetime
- sparse per-line counts keep report size under control much better than the original dense format

In practice this means that if several users upload large files at the same time, the API can keep accepting jobs and the queue can be processed by multiple workers. A simple way to increase throughput is to scale the worker service:

```bash
docker compose up --scale worker=3
```

This allows up to three reports to be processed at the same time.

Current limits and trade-offs:

- a single huge report is still processed by one worker, so horizontal scaling improves throughput, not the speed of one job
- upload itself still goes through the FastAPI application, so many simultaneous large uploads can still put pressure on disk I/O and network I/O
- SQLite temporary aggregation is local to each job, which is fine for isolated workers, but disk performance becomes important under load

If the project had to be pushed further, the next steps would be:

- object storage or a separate upload gateway for very large files
- request throttling or upload limits
- better resource isolation for workers
- external monitoring and alerting
- a production-grade deployment for Redis and PostgreSQL

## Notes and trade-offs

### Why the API is split into three endpoints

The original task named one endpoint, but in practice long-running processing is better handled asynchronously. That is why the implementation uses:

- upload
- status
- download

instead of trying to return the Excel file from the original request.

### Why the third column is sparse

The dense form from the task is simple for small inputs, but it does not scale. On large files it creates enormous strings and turns report writing into the dominant cost. The sparse form keeps the same information while remaining usable.

### Why Redis is not used as the source of truth for status

RQ metadata can expire, be cleaned or disappear together with the queue state. PostgreSQL is a better place for durable job state that must still be available to the API later.

### Why validation is done in storage

Upload validation is closest to the place where the file is actually read. This makes it possible to validate the first bytes of the payload instead of trusting only HTTP metadata from the router layer.
