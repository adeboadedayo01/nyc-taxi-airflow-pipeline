# 🚖 NYC Taxi Data Ingestion with Apache Airflow

This project automates the **download and ingestion** of NYC Yellow Taxi data into a **PostgreSQL** database using **Apache Airflow**.  
---

## 🧠 Project Overview
The pipeline performs the following steps:

Download Dataset: Fetch monthly NYC Yellow Taxi trip data from the DataTalksClub GitHub releases.
Load to Postgres: Use Pandas and SQLAlchemy to load the dataset into a PostgreSQL table (yellow_taxi_data).
Orchestrate with Airflow: Manage task dependencies and scheduling with Airflow DAGs.

### 🔹 Tools Used
- **Apache Airflow** — workflow orchestration  
- **PostgreSQL** — data warehouse  
- **Docker & Docker Compose** — containerized setup  
- **Python, Pandas, SQLAlchemy** — data processing  
- **Redis + Celery** — distributed task queue for Airflow  

### 🔹 Workflow
The Airflow DAG (`data_ingestion_local`) performs:
1. **Download** — retrieves monthly NYC Yellow Taxi data (CSV.gz) from GitHub  
2. **Ingestion** — loads data into a PostgreSQL table (`yellow_taxi_data`)  

---

## ⚙️ Project Structure
├── dags/
│ └── data_ingestion_dag.py # Airflow DAG
├── data/ # Local data folder (mounted in containers)
├── logs/ # Airflow logs
├── plugins/ # Custom Airflow plugins (optional)
├── docker-compose.yaml # Airflow multi-container setup
├── .env # Environment variables (ignored in Git)
├── .gitignore
└── README.md

---

## 🚀 Setup Instructions

### 1️⃣ Prerequisites

- Docker and Docker Compose installed
- At least 4GB of free disk space
- Port 8080 available (for Airflow Web UI)
- Port 6379 available (for Redis)

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

Create a `.env` file in the project root and add your generated Fernet key and database configuration:

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
- `DB_HOST`: Database host (e.g., RDS endpoint)
- `DB_PORT`: Database port (default: 5432)
- `DB_NAME`: Database name
- `AIRFLOW_UID`: Airflow user ID (optional, default: 50000)

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

### 8️⃣ Enable and Run the DAG

1. In the Airflow UI, find the `data_ingestion_local` DAG
2. Toggle it ON (unpause) using the switch on the left
3. The DAG will run monthly starting from 2021-01-01 to 2021-03-01
4. Monitor the progress in the Airflow UI

---

## 🔧 Configuration

### Database Configuration

The pipeline uses a PostgreSQL database (configured via environment variables). The database is automatically created during initialization if it doesn't exist.

- **Host**: Configured via `DB_HOST` environment variable (e.g., AWS RDS endpoint)
- **Port**: Configured via `DB_PORT` environment variable (default: `5432`)
- **Database**: Configured via `DB_NAME` environment variable
- **User**: Configured via `DB_USER` environment variable
- **Password**: Configured via `DB_PASSWORD` environment variable

### Accessing Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Airflow Web UI** | http://localhost:8080 | Username: `airflow`, Password: `airflow` |

### Customizing Database Settings

You can override database settings using Airflow Variables:

1. Go to Admin → Variables in Airflow UI
2. Add variables:
   - `DB_USER`: Database username (default: `airflow`)
   - `DB_PASSWORD`: Database password (default: `airflow`)
   - `DB_HOST`: Database host (default: `postgres`)
   - `DB_PORT`: Database port (default: `5432`)
   - `DB_NAME`: Database name (default: `ny_taxi`)

---

## 📊 Data Pipeline Details

### DAG Schedule

- **Schedule**: Monthly (`@monthly`)
- **Start Date**: 2021-01-01
- **End Date**: 2021-03-01
- **Catchup**: Enabled (will backfill missing months)

### Tasks

1. **create_data_dir**: Ensures the data directory exists
2. **download_dataset**: Downloads monthly CSV.gz file from GitHub
3. **ingest_to_postgres**: Loads data into PostgreSQL in chunks (100k rows per chunk)

### Data Source

NYC Yellow Taxi trip data from [DataTalksClub GitHub releases](https://github.com/DataTalksClub/nyc-tlc-data/releases)

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

### Viewing Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs airflow-scheduler
docker-compose logs airflow-worker

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

## 📁 Project Structure

```
airflow/
├── dags/
│   └── data_ingestion_dag.py    # Main DAG definition
├── data/                         # Downloaded data files (gitignored)
├── logs/                         # Airflow logs (gitignored)
├── plugins/                      # Custom Airflow plugins
├── scripts/                      # Utility scripts
│   └── ensure_database.py        # Database initialization script
├── docker-compose.yaml           # Docker Compose configuration
├── requirements.txt              # Python dependencies
├── .env                          # Your environment variables (gitignored)
├── .gitignore
└── README.md
```

---

## 🔒 Security Notes

- **Default credentials**: Change default Airflow username/password in production
- **Database passwords**: Update PostgreSQL credentials in `docker-compose.yaml` for production
- **Fernet Key**: Always use a unique Fernet key in production
- **Environment variables**: Never commit `.env` file to version control

---

## 📝 License

All rights reserved.

