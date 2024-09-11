import os
import subprocess
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return "Welcome to the Cloud Run migration service!"

@app.route('/run-migration', methods=['POST'])
def run_migration():
    try:
        result = subprocess.run(["alembic", "-c", "globant/alembic.ini", "upgrade", "head"], check=True, capture_output=True, text=True)
        return jsonify({"message": "Migration successful!", "output": result.stdout}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({"error": str(e), "output": e.output}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)


