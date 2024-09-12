import io
import os
import csv
import sys
import fastavro
import traceback
import importlib
import subprocess
from datetime import datetime

from flask import (Flask, jsonify,
                   request, render_template)
app = Flask(__name__)

from google.cloud import storage
storage_client = storage.Client()

from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (Integer, String,
                        Float, Boolean, DateTime)

BASE_PATH = 'database'
BUCKET_NAME = 'globant-db-test-data'

host, port = os.getenv("MYSQL_HOST").split(':')
database_url = URL.create(
    "mysql+mysqlconnector",
    username=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    host=host,
    port=int(port),
    database="pruebaglobant"
)

engine = create_engine(database_url)
Session = sessionmaker(bind=engine)


@app.route('/')
def index():
    return "Welcome to the Cloud Run migration service!"


def get_model_and_headers(table_name):
    try:
        module_name = f"globant.models.{table_name}"
        Model = getattr(importlib.import_module(module_name),
                        ''.join([word.capitalize()
                                 for word in table_name.split('_')]))
        headers = [column.name for column in Model.__table__.columns]
        print(f"Loaded model: {table_name}", file=sys.stdout)
        return Model, headers
    except (ImportError, AttributeError) as e:
        print({"Exception": e,
               "Traceback": traceback.format_exc()},
               file=sys.stderr)
        return jsonify({"error": f"Unknown table: {table_name}"}), 400
    

def validate_and_prepare_records(Model, headers, data):
    if Model is None:
        return None, headers
    validated_records = []
    for row_dict in data:
        try:
            for column in Model.__table__.columns:
                col_name = column.name
                col_type = column.type
                if col_name in row_dict:
                    if isinstance(col_type, Integer):
                        row_dict[col_name] = int(row_dict[col_name])
                    elif isinstance(col_type, Float):
                        row_dict[col_name] = float(row_dict[col_name])
                    elif isinstance(col_type, Boolean):
                        row_dict[col_name] = bool(int(row_dict[col_name]))
                    elif 'datetime' in col_name:
                        if "Z" not in row_dict[col_name]:
                            dt = datetime.strptime(row_dict[col_name],
                                                   '%Y-%m-%dT%H:%M:%S')
                            row_dict[col_name] = str(dt.isoformat() + 'Z')
                        else:
                            dt = datetime.strptime(row_dict[col_name],
                                                   '%Y-%m-%dT%H:%M:%SZ')
                            row_dict[col_name] = str(dt.isoformat() + 'Z')
                    elif isinstance(col_type, String):
                        row_dict[col_name] = str(row_dict[col_name])
            record = Model(**row_dict)
            validated_records.append(record)
        except Exception as e:
            print(f"Error processing row {row_dict}: {e}", file=sys.stdout)
    return validated_records, None


@app.route('/load_historic_data/<table_name>', methods=['POST'])
def load_historic_csv_data_to_db(table_name):
    session = Session()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"{BASE_PATH}/{table_name}/historic/{table_name}.csv")
    csv_reader = csv.reader(
        io.StringIO(blob.download_as_string().decode('utf-8')))
    Model, headers = get_model_and_headers(table_name)
    data = [dict(zip(headers, row)) for row in csv_reader]
    validated_records, error = validate_and_prepare_records(
        Model, headers, data)
    print({"validated records": validated_records,
           "error": error}, file=sys.stdout)
    if error:
        return jsonify({"error": error}), 400
    try:
        for record in validated_records:
            session.add(record)
        session.commit()
        return jsonify({"message": f"Data successfully loaded into {table_name}"}), 200
    except Exception as e:
        session.rollback()
        print({"Exception": e,
               "Traceback": traceback.format_exc()}, file=sys.stderr)
        return jsonify({"error": f"Failed to commit transaction: {e}"}), 500
    finally:
        session.close()


@app.route('/load_data_from_payload/<table_name>', methods=['POST'])
def load_data_from_payload(table_name: str):
    session = Session()
    data = request.get_json()
    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        return jsonify({"error": "Invalid data format. Expected a list or a single dictionary."}), 400
    if len(data) > 1000:
        return jsonify({"error": "Record limit exceeded. Maximum allowed is 1000 records."}), 400
    Model, headers = get_model_and_headers(table_name)
    validated_records, error = validate_and_prepare_records(Model, headers, data)
    print({"validated records": validated_records, "error": error}, file=sys.stdout)
    if error:
        return jsonify({"error": error}), 400
    try:
        for record in validated_records:
            session.add(record)
        session.commit()
        return jsonify({"message": f"Data successfully loaded into {table_name}"}), 200
    except Exception as e:
        session.rollback()
        print({"Exception": e, "Traceback": traceback.format_exc()}, file=sys.stderr)
        return jsonify({"error": f"Failed to commit transaction: {e}"}), 500
    finally:
        session.close()


@app.route('/backup_table/<table_name>', methods=['POST'])
def backup_table_to_avro(table_name):
    session = Session()
    try:
        Model, headers = get_model_and_headers(table_name)
        records = session.query(Model).all()
        if not records:
            return jsonify({"error": f"No data found in table {table_name}"}), 404
        avro_schema = {
            "type": "record",
            "name": f"{table_name}_record",
            "fields": [
                {"name": column.name, "type": "string"} if column.type.python_type == str else
                {"name": column.name, "type": "int"} if column.type.python_type == int else
                {"name": column.name, "type": "float"} if column.type.python_type == float else
                {"name": column.name, "type": "boolean"} if column.type.python_type == bool else
                {"name": column.name, "type": ["null", "string"]} for column in Model.__table__.columns
            ]
        }
        avro_records = []
        for record in records:
            avro_record = {}
            for header in headers:
                value = getattr(record, header)
                if isinstance(value, (int, float, bool)) or value is None:
                    avro_record[header] = value
                else:
                    avro_record[header] = str(value)
            avro_records.append(avro_record)
        with io.BytesIO() as buffer:
            fastavro.writer(buffer, avro_schema, avro_records)
            avro_data = buffer.getvalue()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"{BASE_PATH}/{table_name}/backup/{table_name}.avro")
        blob.upload_from_string(avro_data, content_type='application/octet-stream')
        return jsonify({"message": f"Backup for table {table_name} created successfully in Avro format."}), 200
    except (ImportError, AttributeError) as e:
        print({"traceback": traceback.format_exc()}, file=sys.stderr)
        return jsonify({"error": f"Unknown table: {table_name}"}), 400
    except Exception as e:
        print({"traceback": traceback.format_exc()}, file=sys.stderr)
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    finally:
        session.close()


@app.route('/restore_backup/<table_name>', methods=['POST'])
def restore_backup_from_avro(table_name):
    session = Session()
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"{BASE_PATH}/{table_name}/backup/{table_name}.avro")
        if not blob.exists():
            return jsonify({"error": f"Backup file for table {table_name} not found"}), 404
        avro_data = io.BytesIO(blob.download_as_bytes())
        Model, _ = get_model_and_headers(table_name)
        with io.BytesIO(avro_data.read()) as buffer:
            buffer.seek(0)
            reader = fastavro.reader(buffer)
            records = []
            for avro_record in reader:
                row_dict = {}
                for column in Model.__table__.columns:
                    col_name = column.name
                    col_type = column.type        
                    if col_name in avro_record:
                        if isinstance(col_type, Integer):
                            row_dict[col_name] = int(avro_record[col_name])
                        elif isinstance(col_type, Float):
                            row_dict[col_name] = float(avro_record[col_name])
                        elif isinstance(col_type, Boolean):
                            row_dict[col_name] = bool(avro_record[col_name])
                        elif isinstance(col_type, DateTime):
                            row_dict[col_name] = datetime.fromisoformat(
                                avro_record[col_name].replace("Z", ""))
                        else:
                            row_dict[col_name] = avro_record[col_name]
                record = Model(**row_dict)
                records.append(record)
        session.bulk_save_objects(records)
        session.commit()
        return jsonify({"message": f"Data successfully restored into {table_name}"}), 200
    except (ImportError, AttributeError) as e:
        print({"traceback": traceback.format_exc()}, file=sys.stderr)
        return jsonify({"error": f"Unknown table: {table_name}"}), 400
    except Exception as e:
        session.rollback()
        print({"traceback": traceback.format_exc()}, file=sys.stderr)
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    finally:
        session.close()


@app.route('/run-migration', methods=['POST'])
def run_migration():
    try:
        result = subprocess.run(
            ["alembic", "-c", "globant/alembic.ini", "upgrade", "head"],
            check=True, capture_output=True, text=True
        )
        return jsonify({"message": "Migration successful!", "output": result.stdout}), 200
    except subprocess.CalledProcessError as e:
        print({"Exception": e, "Traceback": traceback.format_exc()}, file=sys.stderr)
        return jsonify({"error": "verify logs for error"}), 500


@app.route('/hired_by_quarter/<year>', methods=['GET'])
def hired_by_quarter(year):
    session = Session()
    query = f"""
        SELECT d.department, j.job, 
               SUM(CASE WHEN QUARTER(h.datetime) = 1 THEN 1 ELSE 0 END) AS Q1,
               SUM(CASE WHEN QUARTER(h.datetime) = 2 THEN 1 ELSE 0 END) AS Q2,
               SUM(CASE WHEN QUARTER(h.datetime) = 3 THEN 1 ELSE 0 END) AS Q3,
               SUM(CASE WHEN QUARTER(h.datetime) = 4 THEN 1 ELSE 0 END) AS Q4
        FROM hired_employees h
        LEFT JOIN departments d ON h.department_id = d.id
        LEFT JOIN jobs j ON h.job_id = j.id
        WHERE YEAR(h.datetime) = {year}
        GROUP BY d.department, j.job
        ORDER BY d.department ASC, j.job ASC;
    """
    result = session.execute(query).fetchall()
    session.close()
    return render_template('hired_by_quarter.html', data=result)


@app.route('/departments_above_mean/<year>', methods=['GET'])
def departments_above_mean(year):
    session = Session()
    query = f"""
        WITH dept_hires AS (
            SELECT d.id, d.department, COUNT(h.id) AS hired
            FROM hired_employees h
            LEFT JOIN departments d ON h.department_id = d.id
            WHERE YEAR(h.datetime) = {year}
            GROUP BY d.id, d.department
        ),
        dept_mean AS (
            SELECT AVG(hired) AS mean_hired
            FROM dept_hires
        )
        SELECT dh.id, dh.department, dh.hired
        FROM dept_hires dh
        CROSS JOIN dept_mean dm
        WHERE dh.hired > dm.mean_hired
        ORDER BY dh.hired DESC;
    """
    result = session.execute(query).fetchall()
    session.close()
    return render_template('departments_above_mean.html', data=result)


@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    output = []
    for rule in app.url_map.iter_rules():
        methods = ', '.join(rule.methods - {'HEAD', 'OPTIONS'})
        output.append({
            "endpoint": rule.endpoint,
            "methods": methods,
            "url": rule.rule
        })
    return jsonify(output), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
