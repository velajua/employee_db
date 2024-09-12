# Project Documentation

## Overview

This project leverages a MariaDB SQL instance on a VM connected to a Cloud Run service via VPC. It manages the loading of historical data from Cloud Storage into a database and allows for backups of the data to be stored and retrieved in Avro format. Additionally, it includes endpoints for specific data exploration metrics.

## Architecture

### MariaDB SQL Instance (VM)

The MariaDB instance is hosted on a VM and serves as the primary database for the application. It is connected to the Cloud Run service through a VPC (Virtual Private Cloud) connector. (Although GCP offers managed SQL isntances thorugh the SQL service, due to costs, it was opted to use shared core VM running a MariaDB instance)

- MariaDB VM: Hosts the MariaDB instance.
- Database Name: `pruebaglobant`
- Port: `3306`
- VPC Connector: Facilitates secure and low-latency communication between the Cloud Run service and the MariaDB instance. The VPC connector is set up in the same region as the VM to ensure fast data access.

Example Connection:
```python
database_url = URL.create(
    "mysql+mysqlconnector",
    username=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    host=host,  # IP address of the MariaDB instance
    port=int(port),  # Port of the MariaDB instance, usually 3306
    database="pruebaglobant"
)
```

### Cloud Run Service

Cloud run offers an easy and effective way to deploy a server with a free tier for deployments each month. It can be paired with GCP cloud Scheduler to create cronjobs, and with GCP Cloud Build to create a CI/CD pipeline when connected to a github repository.

- API endpoints: This service exposes multiple REST API endpoints to handle database operations such as loading historical data, creating backups, and restoring data from backups.
- VPC Access: The service communicates with the MariaDB instance via VPC, ensuring secure and scalable connectivity.

Endpoints:

- `/load_historic_data/<table_name>`: Loads historical data from Cloud Storage into the specified table.
- `/backup_table/<table_name>`: Backs up the specified table into an Avro file.
- `/restore_backup/<table_name>`: Restores the specified table from the Avro backup.
- `/load_data_from_payload/<table_name>`: Loads data from a payload into the specified table.
- `/run-migration`: Executes Alembic database migrations.

### VPC configuration

The VPC connector is configured to allow traffic from Cloud Run to access the MariaDB instance hosted on a VM. The VPC connector ensures secure, high-throughput communication with the database and other services within the same VPC.

- VPC Connector Name: `vpc1`
- Region: `us-central1`
- Access Type: All traffic is routed through the VPC connector for security.

```yaml
annotations:
    run.googleapis.com/vpc-access-connector: projects/{project_id}/locations/us-central1/connectors/vpc1
    run.googleapis.com/vpc-access-egress: all-traffic
```

## Historic and Backup Files

### Historic Files

Historical data for the tables is stored in `.csv` format in a Google Cloud Storage bucket.

- Bucket Name: `globant-db-test-data`
- File Path Template: `database/{table_name}/historic/{table_name}.csv`

The files are organized by table and loaded into the respective database tables via the `/load_historic_data` endpoint.

### Backup Files

Backup files are stored in Avro format and can be created and restored via API endpoints. They are stored in the same Google Cloud Storage bucket.

- File Path Template: `database/{table_name}/backup/{table_name}.avro`

Backups can be triggered manually and restored from Avro format via the `/backup_table` and `/restore_backup` endpoints.

## Server Functionality

### Flask Application

The backend server is built using Flask and provides a REST API for data operations. It integrates with Google Cloud services (such as Cloud Storage) and MariaDB on the VM via SQLAlchemy for database management.

Core Technologies:

- Flask: Python-based web framework to expose RESTful API endpoints.
- SQLAlchemy: Used for database ORM and handling migrations.
- Alembic: Database migration tool.
- Google Cloud Storage: Stores historic and backup files.
- MariaDB: The primary SQL database hosted on the VM.

### Deployment

The Flask app runs on Google Cloud Run, a fully managed serverless platform. It is configured with proper access to the VPC for secure communication with the MariaDB instance.

## Database Migration

### Alembic Setup for Migrations

Alembic is used to handle schema changes and database migrations for the MariaDB instance in this project. Alembic provides a systematic way to apply schema changes (e.g., adding new columns, modifying tables) without affecting the integrity of the data or structure.

### Alembic Configuration

Alembic is configured using an `alembic.ini` file located within the project structure. The relevant database settings are stored in the configuration file, which Alembic uses to connect to the MariaDB instance and apply migrations.

Alembic Configuration (Sample):

```python
[alembic]
script_location = globant/alembic

sqlalchemy.url = mysql+mysqlconnector://<MYSQL_USER>:<MYSQL_PASSWORD>@<MYSQL_HOST>/pruebaglobant
```

### Migration Example

The following example shows a migration that creates three tables: `departments, jobs, and hired_employees`, including foreign key relationships between the tables.

```python
"""First migration

Revision ID: abcdef123456
Revises: None
Create Date: 2024-09-10 14:20:00.123456
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic
revision = 'abcdef123456'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Creating departments table
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('department', sa.String(50), nullable=False),
        schema='pruebaglobant'  # Specify schema for the database
    )

    # Creating jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('job', sa.String(50), nullable=False),
        schema='pruebaglobant'
    )

    # Creating hired_employees table with foreign keys to departments and jobs
    op.create_table(
        'hired_employees',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('datetime', sa.DateTime, nullable=False),
        sa.Column('department_id', sa.Integer, sa.ForeignKey('pruebaglobant.departments.id'), nullable=False),
        sa.Column('job_id', sa.Integer, sa.ForeignKey('pruebaglobant.jobs.id'), nullable=False),
        schema='pruebaglobant'
    )


def downgrade():
    # Dropping tables in reverse order
    op.drop_table('hired_employees', schema='pruebaglobant')
    op.drop_table('jobs', schema='pruebaglobant')
    op.drop_table('departments', schema='pruebaglobant')
```
