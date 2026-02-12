# NYC Taxi Data Pipeline with Apache Airflow

This project automates **downloading**, **loading**, and **warehousing** NYC Yellow Taxi data into PostgreSQL using **Apache Airflow**. You get an ELT-style pipeline with optional **dbt** models for staging and analytics—all orchestrated in one place.

---

## What’s in the box

Two main workflows power the pipeline:

**1. Data ingestion** (`data_ingestion_local`)  
Downloads monthly Yellow Taxi trip data from DataTalksClub’s GitHub releases and loads it into Postgres. Raw data lands in a single table; a small transform step runs afterward (currently a no-op so the DAG stays simple).

**2. Warehouse fact table** (`warehouse_fact_trips`)  
Builds a staging view on top of the raw table, then creates an analytics fact table and loads it **incrementally** (only new days). After each load it runs a few data-quality checks so you can trust the numbers.

There’s also an **optional** dbt DAG (`dbt_transform_pipeline`) that runs `dbt run` and `dbt test` on a schedule—useful if you want dbt to own part of the transformation layer.

**Tech you’ll use**

- **Apache Airflow** — workflow orchestration (LocalExecutor)
- **PostgreSQL** — warehouse and Airflow metadata
- **Docker & Docker Compose** — run everything in containers
- **Python, Pandas, SQLAlchemy** — download and chunked load
- **dbt** — optional SQL transformations (separate DAG + models in the repo)
- **Postgres / SQL operators** — schema, views, fact load, and DQ checks

**How data moves**

```
GitHub (CSV.gz)
    → data_ingestion_local
    → yellow_taxi_data (raw)
    → warehouse_fact_trips
        → staging schema + staging.stg_yellow_taxi (view)
        → analytics schema + analytics.fact_trips (aggregated fact)
    → (optional) dbt_transform_pipeline
```

---

## Project layout

```
airflow/
├── dags/
│   ├── data_ingestion_dag.py          # Download + load raw data
│   ├── warehouse_fact_trips_dag.py    # Staging view, fact table, incremental load, DQ
│   └── dbt_transform_dag.py           # Optional: dbt run + dbt test
├── dbt_project/
│   └── ny_taxi_dbt/
│       ├── models/
│       │   ├── staging/               # e.g. stg_yellow_taxi
│       │   ├── analytics/             # e.g. fact_trips (trip-level, different from DAG fact)
│       │   └── sources/               # raw_sources.yml
│       └── .dbt/
│           └── profiles.yml
├── data/                              # Downloaded files (mounted in containers)
├── sql/
│   └── transform.sql                  # Run after ingest (placeholder for now)
├── scripts/
│   └── ensure_database.py             # Optional DB setup
├── docker-compose.yaml
├── requirements.txt
├── .env                               # Your secrets (not in Git)
└── README.md
```

---

## Getting started

### Prerequisites

- **Docker** and **Docker Compose**
- Enough disk space for a few months of taxi CSVs (on the order of a few GB)
- Port **8080** free for the Airflow UI

### 1. Clone and enter the repo

```bash
git clone https://github.com/Adeniceadebo/nyc-taxi-data-pipeline.git
cd nyc-taxi-data-pipeline/airflow
```

### 2. Generate a Fernet key

Airflow uses this to encrypt secrets. Generate one and keep it safe:

```bash
# With Docker (recommended)
docker run --rm apache/airflow:2.9.1-python3.10 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Or with local Python (if you have cryptography installed)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Configure environment variables

Create a `.env` file in this directory. The Compose setup is built to use an **external** Postgres (e.g. RDS) for both Airflow metadata and your data—no Postgres container in the stack.

```bash
# Example .env
AIRFLOW__CORE__FERNET_KEY=your_generated_fernet_key_here
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=your_db_name
AIRFLOW_UID=50000
```

**What each variable is for**

- `AIRFLOW__CORE__FERNET_KEY` — from step 2
- `DB_*` — used by `docker-compose` for the Airflow metadata DB connection
- `AIRFLOW_UID` — optional; on Linux you can set `AIRFLOW_UID=$(id -u)` so files on mounts are owned by your user

### 4. (Optional) Set your user ID on Linux

If you’re on Linux and want log/data directories to match your user:

```bash
echo "AIRFLOW_UID=$(id -u)" >> .env
```

Then add or keep your Fernet key in the same `.env`.

### 5. Initialize Airflow and start the stack

One-time init (migrates DB, creates default admin user):

```bash
docker-compose up airflow-init
```

Then start everything:

```bash
docker-compose up -d
```

### 6. Open the Airflow UI

- URL: **http://localhost:8080**
- Default login: **airflow** / **airflow** (change these in production)

### 7. Configure the Postgres connection for the pipelines

The DAGs talk to your **data** Postgres using the connection ID **`pg_ny_taxi`**. You need to create it once:

1. In the UI: **Admin → Connections**
2. Add a connection:
   - **Connection Id**: `pg_ny_taxi`
   - **Connection Type**: Postgres
   - **Host / Schema / Login / Password / Port**: same database where you want `yellow_taxi_data` and the staging/analytics objects

If your Airflow metadata DB and your data DB are the same instance, you can reuse the same host and credentials; just set the connection ID to `pg_ny_taxi`.

### 8. Turn on and run the DAGs

- Find **data_ingestion_local** and **warehouse_fact_trips** (and optionally **dbt_transform_pipeline**).
- Unpause them (toggle on).
- **data_ingestion_local** runs monthly and will backfill from 2021-01-01 through 2021-03-01.
- **warehouse_fact_trips** runs daily and only processes **new** days (incremental).
- Watch runs and logs in the UI.

---

## Configuration details

### Database

- **Airflow metadata**: connection string is built from `DB_*` in `.env` (see `docker-compose.yaml`).
- **Target data DB**: the same Postgres can hold `yellow_taxi_data`, `staging`, and `analytics`. The DAGs use the **`pg_ny_taxi`** connection for all of that.
- **Creating the DB**: the repo includes `scripts/ensure_database.py` if you need to create a database (e.g. `ny_taxi`) yourself; Compose does **not** run it automatically.

### Access

| What            | Where                  | Default credentials   |
|-----------------|------------------------|------------------------|
| Airflow Web UI  | http://localhost:8080  | airflow / airflow      |

---

## Pipeline behavior (what each DAG does)

### DAG 1: Data ingestion (`data_ingestion_local`)

- **Schedule**: monthly (`@monthly`)
- **Start / end**: 2021-01-01 → 2021-03-01, with catchup (backfills missing months)
- **Max active runs**: 1

**Tasks in order**

1. **create_data_dir** — ensures the data directory exists.
2. **download_dataset** — downloads the monthly CSV.gz from DataTalksClub (e.g. `yellow_tripdata_2021-01.csv.gz`) into `/opt/airflow/data`.
3. **ingest_to_postgres** — reads the file in chunks (100k rows), normalizes column names to lowercase, and appends into **`yellow_taxi_data`**.
4. **transform_data** — runs `sql/transform.sql` (currently a placeholder like `SELECT 1` so the DAG still succeeds).

**Source**: [DataTalksClub NYC TLC data (yellow taxi)](https://github.com/DataTalksClub/nyc-tlc-data/releases).

**Note:** This DAG does **not** create the staging view or analytics tables; that’s done by **warehouse_fact_trips**.

---

### DAG 2: Warehouse fact table (`warehouse_fact_trips`)

- **Schedule**: daily (`@daily`)
- **Start**: 2021-01-01, **catchup**: off (incremental only)
- **Tags**: `warehouse`, `dq`
- **Max active runs**: 1

**Tasks in order**

1. **create_staging_schema** — `CREATE SCHEMA IF NOT EXISTS staging`.
2. **create_stg_yellow_taxi_view** — `CREATE OR REPLACE VIEW staging.stg_yellow_taxi` over `public.yellow_taxi_data` with cleaned column names and basic filters (e.g. non-null pickup time, non-negative distance and total amount). This view exposes **pickup_datetime** so the next step can do incremental loads by date.
3. **create_analytics_schema_and_fact_table** — `CREATE SCHEMA IF NOT EXISTS analytics` and `CREATE TABLE IF NOT EXISTS analytics.fact_trips` with columns and primary key matching the aggregate grain (see below). No tables are dropped; existing data is preserved.
4. **load_fact_trips** — Inserts **only** rows for dates **after** the latest `trip_date` already in `analytics.fact_trips`. Aggregates by `(trip_date, pickup_location_id, dropoff_location_id)` and uses `ON CONFLICT ... DO NOTHING` so re-runs don’t duplicate data.
5. **dq_row_count** — Asserts the fact table has at least one row.
6. **dq_no_null_trip_date** — Asserts no `trip_date` is NULL.
7. **dq_no_duplicates** — Asserts there are no duplicate keys (same grain as the primary key).

**Fact table grain and columns**

- **Grain**: one row per `(trip_date, pickup_location_id, dropoff_location_id)`.
- **Dimensions**: `trip_date`, `pickup_location_id`, `dropoff_location_id`.
- **Metrics**: `trip_count`, `total_passengers`, `total_distance`, `total_fare`, `total_tips`, `total_revenue`.

So you don’t need to create staging or analytics yourself—this DAG creates the schema, the staging view, and the fact table, then keeps the fact table updated incrementally and runs the three DQ checks.

---

### DAG 3: dbt transform (`dbt_transform_pipeline`) — optional

- **Schedule**: daily, catchup off
- **Tags**: `dbt`, `warehouse`

**Tasks**

1. **dbt_run** — `dbt run` in the project directory.
2. **dbt_test** — `dbt test` in the same project.

The Compose setup mounts `dbt_project/ny_taxi_dbt/.dbt` into `/opt/airflow/.dbt` so dbt can use your `profiles.yml` (e.g. credentials via `env_var`). Project directory used in the DAG is `/opt/airflow/dbt_project/ny_taxi_dbt`.

**Note:** The dbt **analytics** model (e.g. trip-level `fact_trips` with a surrogate key) is separate from the **warehouse** `analytics.fact_trips` table that the Airflow DAG builds (which is daily aggregate by location/vendor/payment). Same name, different grain—something to be aware of if you use both.

---

## dbt models (optional)

In **dbt_project/ny_taxi_dbt** you’ll find:

- **Staging**: e.g. `stg_yellow_taxi` (view over the raw source).
- **Analytics**: e.g. `fact_trips` (trip-level fact with generated `trip_id`).
- **Sources**: `raw_sources.yml` pointing at the raw table.

You can run these via the **dbt_transform_pipeline** DAG or by hand with `dbt run` and `dbt test` from inside the container or your own environment.

---

## Troubleshooting

**“Database does not exist” or metadata DB errors**  
Make sure `docker-compose up airflow-init` finished successfully. Check: `docker-compose logs airflow-init`.

**Download task fails**  
Check network access to GitHub and that the release file URL is still valid.

**Ingestion runs out of memory**  
The ingest task uses 100k-row chunks. If you still hit limits, lower the chunk size in `data_ingestion_dag.py` in the `ingest_to_postgres` callable.

**Port 8080 already in use**  
Change the host port in `docker-compose.yaml` (e.g. `8081:8080`) or stop whatever is using 8080.

**“relation staging.stg_yellow_taxi does not exist”**  
The **warehouse_fact_trips** DAG creates this view itself. So either the DAG hasn’t run yet (run it once), or the **create_staging_schema** / **create_stg_yellow_taxi_view** tasks failed—check their logs. Also ensure **data_ingestion_local** has run so `yellow_taxi_data` exists.

**dbt DAG fails (profile/connection)**  
Check `dbt_project/ny_taxi_dbt/.dbt/profiles.yml`: correct host, user, password (e.g. via `env_var`), and that the same DB is reachable from the Airflow container. If you use `sslmode: require`, ensure the container can reach the DB with TLS.

**“Connection pg_ny_taxi not found”**  
Add the connection in the Airflow UI under **Admin → Connections** with Connection Id **pg_ny_taxi** and the correct Postgres details.

**Viewing logs**

```bash
docker-compose logs
docker-compose logs airflow-scheduler
docker-compose logs -f
```

**Stopping and cleaning up**

```bash
docker-compose down
# Remove volumes too (deletes DB data and logs):
docker-compose down -v
```

---

## Security (quick notes)

- Change the default **airflow / airflow** login in production.
- Keep **DB_PASSWORD** and **AIRFLOW__CORE__FERNET_KEY** strong and never commit `.env`.
- Use a unique Fernet key per environment.

---

## License

All rights reserved.
