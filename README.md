# 🚖 NYC Taxi Data Pipeline with Apache Airflow

This project automates the **download, ingestion, and warehousing** of NYC Yellow Taxi data into a **PostgreSQL** database using **Apache Airflow**. The pipeline follows an ELT pattern and includes optional dbt models for a staging + analytics layer.

---

## 🧠 Project Overview

The pipeline consists of two main workflows:

### 1. Data Ingestion Pipeline (`data_ingestion_local`)
- **Extract**: Downloads monthly NYC Yellow Taxi trip data from the DataTalksClub GitHub releases
- **Load**: Uses Pandas and SQLAlchemy to load the dataset into a PostgreSQL table (`yellow_taxi_data`)
- **Transform**: Runs `sql/transform.sql` (currently a placeholder `SELECT 1` so the task succeeds)

### 2. Warehouse Fact Table Pipeline (`warehouse_fact_trips`)
- **Load Fact Table**: Aggregates trip data from staging into a dimensional fact table
- **Data Quality Checks**: Validates data integrity with multiple DQ checks

### 🔹 Tools Used
- **Apache Airflow** — workflow orchestration (LocalExecutor)
- **PostgreSQL** — data warehouse
- **Docker & Docker Compose** — containerized setup
- **Python, Pandas, SQLAlchemy** — data processing
- **dbt (Data Build Tool)** — optional SQL transformation layer (DAG included + models available)
- **Postgres Operators** — database operations and data quality checks

### 🔹 Data Flow

```
GitHub Releases (CSV.gz)
    ↓
[Data Ingestion DAG]
    ↓
yellow_taxi_data (Raw Data)
    ↓
staging.stg_yellow_taxi (Staging Layer)
    ↓
analytics.fact_trips (Analytics/Data Warehouse Layer)
```

---

## ⚙️ Project Structure

```
airflow/
├── dags/
│   ├── data_ingestion_dag.py          # Data ingestion pipeline DAG
│   └── warehouse_fact_trips_dag.py    # Fact table loading and DQ DAG
├── dbt_project/
│   └── ny_taxi_dbt/                   # dbt project for transformations
│       ├── models/
│       │   ├── staging/               # Staging layer models
│       │   │   ├── stg_yellow_taxi.sql
│       │   │   └── schema.yml
│       │   ├── analytics/             # Analytics layer models
│       │   │   ├── fact_trips.sql
│       │   │   └── schema.yml
│       │   └── sources/               # Source definitions
│       │       └── raw_sources.yml
│       └── dbt_project.yml
├── data/                              # Local data folder (mounted in containers)
├── sql/                               # SQL transformation scripts
│   └── transform.sql
├── scripts/                           # Utility scripts
│   └── ensure_database.py            # Database initialization script
├── logs/                              # Airflow logs
├── plugins/                           # Custom Airflow plugins (optional)
├── docker-compose.yaml                # Airflow multi-container setup
├── requirements.txt                   # Python dependencies
├── .env                               # Environment variables (ignored in Git)
├── .gitignore
└── README.md
```

---

## 🚀 Setup Instructions

### 1️⃣ Prerequisites

- Docker and Docker Compose installed
- At least 4GB of free disk space
- Port 8080 available (for Airflow Web UI)

### 2️⃣ Clone the repository

```bash
git clone https://github.com/Adeniceadebo/nyc-taxi-data-pipeline.git
cd nyc-taxi-data-pipeline/airflow
```

### 3️⃣ Generate Fernet Key

Generate a Fernet key for Airflow encryption:

```bash
# Using Docker (recommended)
docker run --rm apache/airflow:2.9.1-python3.10 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Or using Python (if cryptography is installed)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4️⃣ Configure Environment Variables

Create a `.env` file in the project root and add your generated Fernet key and **Postgres connection details**.

This repo’s `docker-compose.yaml` is configured to point Airflow’s metadata DB at `${DB_HOST}:${DB_PORT}/${DB_NAME}` (i.e., an external Postgres/RDS-style database), rather than running a local `postgres` container.

```bash
# Create .env file
cat > .env << EOF
AIRFLOW__CORE__FERNET_KEY=your_generated_fernet_key_here
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=your_db_name
AIRFLOW_UID=50000
EOF
```

**Required environment variables:**
- `AIRFLOW__CORE__FERNET_KEY`: Your generated Fernet key from step 3
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database host (e.g., AWS RDS endpoint)
- `DB_PORT`: Database port (default: `5432`)
- `DB_NAME`: Database name
- `AIRFLOW_UID`: Airflow user ID (optional, default: `50000`)

### 5️⃣ Set Airflow User ID (Optional)

On Linux, set the Airflow user ID to match your system user:

```bash
echo -e "AIRFLOW_UID=$(id -u)" > .env
```

Add your Fernet key to the same file.

### 6️⃣ Initialize and Start Services

Initialize Airflow database and create admin user:

```bash
docker-compose up airflow-init
```

Start all services:

```bash
docker-compose up -d
```

### 7️⃣ Access Airflow Web UI

- Open your browser and navigate to: `http://localhost:8080`
- Login with:
  - Username: `airflow`
  - Password: `airflow`

### 8️⃣ Enable and Run the DAGs

1. In the Airflow UI, find the following DAGs:
   - `data_ingestion_local` — Data ingestion pipeline
   - `warehouse_fact_trips` — Fact table loading and data quality checks

2. Toggle them ON (unpause) using the switch on the left

3. The DAGs will run according to their schedules:
   - **data_ingestion_local**: Monthly starting from 2021-01-01 to 2021-03-01
   - **warehouse_fact_trips**: Daily (incremental loads)

4. Monitor the progress in the Airflow UI

---

## 🔧 Configuration

### Database Configuration

The pipeline uses a PostgreSQL database (configured via environment variables).

Notes:
- **Airflow metadata DB**: `docker-compose.yaml` sets `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` using `DB_*` env vars.
- **Target DB creation**: the helper script `scripts/ensure_database.py` can create the target database (defaults to `ny_taxi`) if it doesn’t exist, but it is **not automatically run by docker-compose**.

- **Host**: Configured via `DB_HOST` environment variable (e.g., AWS RDS endpoint)
- **Port**: Configured via `DB_PORT` environment variable (default: `5432`)
- **Database**: Configured via `DB_NAME` environment variable
- **User**: Configured via `DB_USER` environment variable
- **Password**: Configured via `DB_PASSWORD` environment variable

### Postgres Connection

The DAGs use a Postgres connection ID: `pg_ny_taxi`. Ensure this connection is configured in Airflow:

1. Go to **Admin → Connections** in Airflow UI
2. Add/edit connection with ID: `pg_ny_taxi`
3. Configure with your database credentials:
   - **Connection Type**: `Postgres`
   - **Host**: Your database host
   - **Schema**: Your database name
   - **Login**: Database username
   - **Password**: Database password
   - **Port**: 5432

### Accessing Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Airflow Web UI** | http://localhost:8080 | Username: `airflow`, Password: `airflow` |

---

## 📊 Data Pipeline Details

### DAG 1: Data Ingestion (`data_ingestion_local`)

**Schedule**: Monthly (`@monthly`)
- **Start Date**: 2021-01-01
- **End Date**: 2021-03-01
- **Catchup**: Enabled (will backfill missing months)
- **Max Active Runs**: 1

**Tasks:**
1. **create_data_dir**: Ensures the data directory exists
2. **download_dataset**: Downloads monthly CSV.gz file from GitHub
3. **ingest_to_postgres**: Loads data into PostgreSQL table `yellow_taxi_data` in chunks (100k rows per chunk)
4. **transform_data**: Executes SQL transformation script

**Data Source:**
NYC Yellow Taxi trip data from [DataTalksClub GitHub releases](https://github.com/DataTalksClub/nyc-tlc-data/releases)

**Output Table:**
- `yellow_taxi_data` — Raw ingested taxi trip data

**Important**: `transform_data` currently runs `sql/transform.sql`, which is a placeholder `SELECT 1` (it does not create staging tables).

### DAG 2: Warehouse Fact Table (`warehouse_fact_trips`)

**Schedule**: Daily (`@daily`)
- **Start Date**: 2021-01-01
- **Catchup**: Disabled (incremental loads only)
- **Tags**: `warehouse`, `dq`

**Tasks:**
1. **load_fact_trips**: Incrementally loads aggregated trip data into `analytics.fact_trips` fact table
   - Aggregates data from `staging.stg_yellow_taxi`
   - Dimensions: trip_date, vendor_id, pickup_location_id, dropoff_location_id, payment_type
   - Metrics: trip_count, total_passengers, total_distance, total_fare, total_tips, total_revenue

2. **dq_row_count**: Data quality check ensuring fact table is not empty

3. **dq_no_null_trip_date**: Data quality check ensuring no NULL trip_date values

4. **dq_no_duplicates**: Data quality check ensuring no duplicate grain (composite key uniqueness)

**Output Tables:**
- `analytics.fact_trips` — Dimensional fact table for trip analytics

**Note**: This DAG assumes the following already exist:
- `staging.stg_yellow_taxi` (source table/view with the columns referenced in the DAG SQL)
- `analytics.fact_trips` (target table with the columns referenced in the DAG SQL)

You can create/populate these via:
- **dbt** (recommended): run the dbt models in `dbt_project/ny_taxi_dbt/`
- Manual SQL / migrations
- Additional Airflow tasks

### dbt Models (Optional)

The project includes dbt models for data transformation:

**Staging Layer** (`models/staging/`):
- `stg_yellow_taxi` — Cleaned and standardized Yellow Taxi trip data

**Analytics Layer** (`models/analytics/`):
- `fact_trips` — Fact table with surrogate key (trip_id) for individual trips

To use dbt models, run dbt separately or integrate dbt operators into Airflow DAGs.

### DAG 3: dbt Transform (`dbt_transform_pipeline`) (Optional)

There is also a dbt DAG:
- `dbt_transform_pipeline` (schedule: `@daily`)
  - `dbt run`
  - `dbt test`

The container mounts `dbt_project/ny_taxi_dbt/.dbt/` into `/opt/airflow/.dbt` so dbt can read profiles from there.

---

## 🛠️ Troubleshooting

### Common Issues

**Issue**: DAG fails with "database does not exist"
- **Solution**: Ensure `airflow-init` service completed successfully. Check logs: `docker-compose logs airflow-init`

**Issue**: Download task fails
- **Solution**: Check network connectivity and verify the URL is accessible

**Issue**: Ingestion task runs out of memory
- **Solution**: The pipeline uses chunked processing (100k rows). For very large files, reduce `chunk_size` in the DAG

**Issue**: Port already in use
- **Solution**: Change ports in `docker-compose.yaml` or stop conflicting services

**Issue**: `warehouse_fact_trips` DAG fails with "relation staging.stg_yellow_taxi does not exist"
- **Solution**: Ensure the staging table exists. You may need to create it manually or run dbt models first

**Issue**: dbt DAG fails with profile/connection errors
- **Solution**: Check `dbt_project/ny_taxi_dbt/.dbt/profiles.yml` and ensure credentials are available (it uses `DB_PASSWORD` via `env_var` and `sslmode: require`).

**Issue**: Postgres connection not found
- **Solution**: Ensure the `pg_ny_taxi` connection is configured in Airflow Admin → Connections

### Viewing Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs airflow-scheduler
docker-compose logs airflow-webserver

# Follow logs
docker-compose logs -f
```

### Stopping Services

```bash
# Stop services
docker-compose down

# Stop and remove volumes (⚠️ deletes data)
docker-compose down -v
```

---

## 📁 Complete Project Structure

```
airflow/
├── dags/
│   ├── data_ingestion_dag.py          # Main data ingestion DAG
│   └── warehouse_fact_trips_dag.py    # Fact table loading DAG
├── dbt_project/
│   └── ny_taxi_dbt/                   # dbt transformation project
│       ├── models/
│       │   ├── staging/               # Staging layer models
│       │   ├── analytics/             # Analytics layer models
│       │   └── sources/               # Source definitions
│       └── dbt_project.yml
├── data/                              # Downloaded data files (gitignored)
├── sql/                               # SQL transformation scripts
│   └── transform.sql
├── scripts/                           # Utility scripts
│   └── ensure_database.py            # Database initialization
├── logs/                              # Airflow logs (gitignored)
├── plugins/                           # Custom Airflow plugins
├── docker-compose.yaml                # Docker Compose configuration
├── requirements.txt                   # Python dependencies
├── .env                               # Environment variables (gitignored)
├── .gitignore
└── README.md
```

---

## 🔒 Security Notes

- **Default credentials**: Change default Airflow username/password in production
- **Database passwords**: Update PostgreSQL credentials in `.env` file for production
- **Fernet Key**: Always use a unique Fernet key in production
- **Environment variables**: Never commit `.env` file to version control

---

## 📝 License

All rights reserved.
