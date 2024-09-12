import io
import os
import csv
import sys
import traceback
import importlib
import subprocess
from datetime import datetime

from flask import Flask, jsonify, request
app = Flask(__name__)

from google.cloud import storage
storage_client = storage.Client()

from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Integer, String, DateTime, Float, Boolean

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
                        ''.join([word.capitalize() for word in table_name.split('_')]))
        headers = [column.name for column in Model.__table__.columns]
        print(f"Loaded model: {table_name}", file=sys.stdout)
        return Model, headers
    except (ImportError, AttributeError) as e:
        print({"Exception": e, "Traceback": traceback.format_exc()}, file=sys.stderr)
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
                    elif isinstance(col_type, DateTime):
                        if "Z" not in row_dict[col_name]:
                            dt = datetime.strptime(row_dict[col_name], '%Y-%m-%dT%H:%M:%S')
                            row_dict[col_name] = dt.isoformat() + 'Z'
                    elif isinstance(col_type, String):
                        row_dict[col_name] = str(row_dict[col_name])
            record = Model(**row_dict)
            validated_records.append(record)
        except Exception as e:
            return None, f"Error processing row {row_dict}: {e}"
    return validated_records, None


@app.route('/load_historic_data/<table_name>', methods=['POST'])
def load_historic_csv_data_to_db(table_name):
    session = Session()

    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"{BASE_PATH}/{table_name}/historic/{table_name}.csv")
    csv_reader = csv.reader(io.StringIO(blob.download_as_string().decode('utf-8')))

    Model, headers = get_model_and_headers(table_name)

    data = [dict(zip(headers, row)) for row in csv_reader]
    validated_records, error = validate_and_prepare_records(Model, headers, data)
    print({"message": f"validated records: {len(validated_records)}", "vals": validated_records}, file=sys.stdout)

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

    validated_records, error = validate_and_prepare_records(table_name, data)
    print({"message": f"validated records: {len(validated_records)}", "vals": validated_records}, file=sys.stdout)
    
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
