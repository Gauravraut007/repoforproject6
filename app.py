import boto3
import pandas as pd
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from io import BytesIO

app = Flask(__name__)

# Secret key for session management (for authentication)
import os
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))  # fallback to random key if env var is not set
# Set to a random secret key in production

# AWS S3 Configuration
S3_BUCKET = "placement-trends-data2"
S3_BUCKET_Marker = "markers-for-batches2"
S3_REGION = "us-east-1"  # Change to your AWS region
s3_client = boto3.client('s3')

# AWS Credentials (replace with environment variables for security purposes in production)
s3_client = boto3.client(
    's3',
    aws_access_key_id="xxx",
    aws_secret_access_key="xxxxx",
    aws_session_token="xxx",
    region_name="us-east-1"
)

FILE_TYPES = ["DAC", "DBDA", "Registration", "MasterData", "Placement"]
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# Simple hardcoded credentials (for demonstration, replace with a database or other secure method)
USER_CREDENTIALS = {
    "admin": "password123"  # Username: admin, Password: password123 (for example purposes)
}


# Function to check file extension
def allowed_file(filename):
    return "." in filename and ("." + filename.rsplit(".", 1)[-1].lower()) in ALLOWED_EXTENSIONS


# Authentication check for route access
def is_logged_in():
    return "logged_in" in session and session["logged_in"]


@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    return render_template('upload.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check credentials
        if USER_CREDENTIALS.get(username) == password:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return "Invalid credentials. Please try again.", 401
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/upload', methods=['POST'])
def upload_files():
    if not is_logged_in():
        return redirect(url_for('login'))

    batch_month = request.form.get('batch_month')
    batch_year = request.form.get('batch_year')
    if not batch_month or not batch_year:
        return jsonify({"error": "Batch month and year are required"}), 400

    batch_name = f"{batch_month}_{batch_year}"
    uploaded_files = {}

    for file_type in FILE_TYPES:
        file = request.files.get(file_type)
        if not file:
            return jsonify({"error": f"Missing file: {file_type}"}), 400

        file_ext = "." + file.filename.rsplit(".", 1)[-1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return jsonify({"error": f"{file_type} file must be in .csv, .xlsx, or .xls format"}), 400

        try:
            # Process MasterData and Placement files separately
            if file_type == "MasterData" or file_type == "Placement":
                dac_sheet_name = request.form.get(f"{file_type}_DAC")
                dbda_sheet_name = request.form.get(f"{file_type}_DBDA")

                df = pd.read_excel(file, sheet_name=None)  # Load all sheets

                if not dac_sheet_name or dac_sheet_name not in df:
                    return jsonify({"error": f"Missing or incorrect sheet name for DAC in {file_type}"}), 400
                if not dbda_sheet_name or dbda_sheet_name not in df:
                    return jsonify({"error": f"Missing or incorrect sheet name for DBDA in {file_type}"}), 400

                # Convert DAC Sheet
                dac_buffer = BytesIO()
                df[dac_sheet_name].to_csv(dac_buffer, index=False)
                dac_buffer.seek(0)
                dac_key = f"{batch_name}/{file_type}_DAC.csv"
                s3_client.upload_fileobj(dac_buffer, S3_BUCKET, dac_key)
                uploaded_files[f"{file_type}_DAC"] = dac_key

                # Convert DBDA Sheet
                dbda_buffer = BytesIO()
                df[dbda_sheet_name].to_csv(dbda_buffer, index=False)
                dbda_buffer.seek(0)
                dbda_key = f"{batch_name}/{file_type}_DBDA.csv"
                s3_client.upload_fileobj(dbda_buffer, S3_BUCKET, dbda_key)
                uploaded_files[f"{file_type}_DBDA"] = dbda_key
            else:
                # Process normal files (DAC, DBDA, Registration)
                if file_ext in {".xlsx", ".xls"}:
                    if file_type == "DAC":
                        df = forDACResult(file)
                    elif file_type == "DBDA":
                        df = forDBDAResult(file)
                    else:
                        df = pd.read_excel(file)
                    buffer = BytesIO()
                    df.to_csv(buffer, index=False)
                    buffer.seek(0)
                    s3_key = f"{batch_name}/{file_type}_result.csv"
                    s3_client.upload_fileobj(buffer, S3_BUCKET, s3_key)
                else:
                    s3_key = f"{batch_name}/{file_type}.csv"
                    s3_client.upload_fileobj(file, S3_BUCKET, s3_key)

                uploaded_files[file_type] = s3_key

            upload_marker_file(batch_name)

        except Exception as e:
            return jsonify({"error": f"Failed to process {file_type}: {str(e)}"}), 500

    return jsonify({"message": "All files uploaded successfully", "files": uploaded_files}), 200


# Function to process DAC result files
def forDACResult(file):
    df = pd.read_excel(file)
    # Your specific processing logic for DAC files
    return df

# Function to process DBDA result files
def forDBDAResult(file):
    df = pd.read_excel(file)
    # Your specific processing logic for DBDA files
    return df

# Function to upload marker file to S3
def upload_marker_file(batch_name):
    marker_data = {"batch_name": batch_name, "status": "uploaded"}
    marker_buffer = BytesIO(str(marker_data).encode('utf-8'))
    marker_key = f"{batch_name}/marker.json"
    s3_client.upload_fileobj(marker_buffer, S3_BUCKET_Marker, marker_key)


if __name__ == '__main__':
    app.run(debug=True)
