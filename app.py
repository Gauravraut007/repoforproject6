import boto3
import pandas as pd
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
import sqlite3
from dotenv import load_dotenv


app = Flask(__name__)

app.config['SECRET_KEY'] = 'FLASK_SECRET_KEY1'


load_dotenv()

S3_BUCKET = "placecdment-trends-datag6"
S3_BUCKET_Marker = "markers-for-batchesg6"
S3_REGION = "us-east-1"
AWS_ACCESS_KEY_ID = "xxxxx"
AWS_SECRET_ACCESS_KEY = "xxxxx"
AWS_SESSION_TOKEN = "xxxxxxx"

# Initialize the S3 client with environment variables
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
    region_name=S3_REGION
)

FILE_TYPES = ["DAC", "DBDA", "Registration", "MasterData", "Placement"]
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# Database setup for user authentication
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Utility functions
def allowed_file(filename):
    return "." in filename and ("." + filename.rsplit(".", 1)[-1].lower()) in ALLOWED_EXTENSIONS

def is_logged_in():
    return "logged_in" in session and session["logged_in"]


def forDACResult(file):
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    engine = "xlrd" if file_ext == "xls" else "openpyxl"

    df = pd.read_excel(file, header=[0, 1], engine=engine)
    df.columns = [
        f"{str(col[0]).strip()}_{str(col[1]).strip()}" if isinstance(col, tuple) and col[0] and col[1]
        else str(col[1]).strip() if isinstance(col, tuple) and col[1]
        else str(col[0]).strip()
        for col in df.columns
    ]

    column_mapping = {
        "unnamed: 0_level_0_prn": "PRN",
        "total_800": "Total800",
        "total_600": "Total800",
        "web-based java programming_total/600": "Total800",
        "web-based java programming_total/800": "Total800",
        "total_%": "CDAC_Percentage",
        "web-based java programming_%": "CDAC_Percentage",
        "total_grade": "Grade",
        "web-based java programming_grade": "Grade",
        "total_result": "Result",
        "web-based java programming_result": "Result",
        "total_apti & ec grade": "Apti_EC_Grade",
        "web-based java programming_apti & ec grade": "Apti_EC_Grade",
        "total_project grade": "Project_Grade",
        "web-based java programming_project grade": "Project_Grade",


    }
    df.rename(columns=lambda x: column_mapping.get(x.lower(), x), inplace=True)

    expected_columns = ["PRN", "Total800", "CDAC_Percentage", "Grade", "Result", "Apti_EC_Grade", "Project_Grade"]
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    subject_total_columns = [col for col in df.columns if "Total" in col and col not in ["Total800"]]
    df["Total800"] = df[subject_total_columns].apply(pd.to_numeric, errors='coerce').sum(axis=1)

    return df[expected_columns]

def forDBDAResult(file):
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    engine = "xlrd" if file_ext == "xls" else "openpyxl"

    df = pd.read_excel(file, header=[0, 1], engine=engine)
    df.columns = [
        f"{str(col[0]).strip()}_{str(col[1]).strip()}" if isinstance(col, tuple) and col[0] and col[1]
        else str(col[1]).strip() if isinstance(col, tuple) and col[1]
        else str(col[0]).strip()
        for col in df.columns
    ]

    column_mapping = {
        "Unnamed: 0_level_0_PRN": "PRN",
        "total_800": "Total800",
        "total_600": "Total800",
        "total_%": "CDAC_Percentage",
        "total_grade": "Grade",
        "total_result": "Result",
        "total_apti & ec grade": "Apti_EC_Grade",
        "total_project grade": "Project_Grade",

        "Practical Machine learning_Total/600": "Total800",
        "Practical Machine learning_%": "CDAC_Percentage",
        "Practical Machine learning_Apti & EC Grade": "Apti_EC_Grade",
        "Practical Machine Learning_Apti & EC Grade": "Apti_EC_Grade",

        "Practical Machine learning_Result": "Result",
        "Practical Machine Learning_Project Grade": "Project_Grade",

        "Practical Machine Learning_Total/800": "Total800",
        "Practical Machine Learning_Grade": "Grade",
        "Practical Machine Learning_Result": "Result",

        "Practical Machine Learning_%": "CDAC_Percentage",
        "Practical Machine learning_Grade": "Grade",
        "Practical Machine learning_Project Grade": "Project_Grade",

    }
    df.rename(columns=lambda x: column_mapping.get(x.strip(), x), inplace=True)

    expected_columns = ["PRN", "Total800", "CDAC_Percentage", "Grade", "Result", "Apti_EC_Grade", "Project_Grade"]
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None  # Assign missing columns as empty
    subject_total_columns = [col for col in df.columns if "Total" in col and col not in ["Total800"]]
    df["Total800"] = df[subject_total_columns].apply(pd.to_numeric, errors='coerce').sum(axis=1)

    return df[expected_columns]


@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    return render_template('upload.html')

def upload_marker_file(batch_name):
    marker_key = f"{batch_name}.txt"

    s3_client.put_object(Bucket=S3_BUCKET_Marker, Key=marker_key, Body="Batch upload complete")
    print(f"Marker file uploaded: {marker_key}")



# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html')

        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different one.', 'error')

    return render_template('register.html')

# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['logged_in'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload_files():
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
                    if file_type=="DAC":
                        df = forDACResult(file)
                    elif file_type=="DBDA":
                        df = forDBDAResult(file)
                    else:
                        df = pd.read_excel(file)
                    buffer = BytesIO()
                    df.to_csv(buffer, index=False)
                    buffer.seek(0)
                    s3_key = f"{batch_name}/{file_type}_Result.csv"
                    s3_client.upload_fileobj(buffer, S3_BUCKET, s3_key)
                else:
                    s3_key = f"{batch_name}/{file_type}.csv"
                    s3_client.upload_fileobj(file, S3_BUCKET, s3_key)

                uploaded_files[file_type] = s3_key

            upload_marker_file(batch_name)

        except Exception as e:
            return jsonify({"error": f"Failed to process {file_type}: {str(e)}"}), 500

    return jsonify({"message": "All files uploaded successfully", "files": uploaded_files}), 200

if __name__ == '__main__':
    app.run(debug=True)
