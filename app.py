from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import qrcode
from io import BytesIO
import base64
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import secrets

app = Flask(__name__)
app.secret_key = "your_secret_key"
polls = {}
TEACHER_DB = "teacher.db"
STUDENT_DB = "student.db"

# Google Sheets setup (replace with your credentials)
CREDENTIALS_FILE = "your-credentials.json"  # Path to your Google Sheets credentials file
SHEET_NAME = "Attendance"

def create_teacher_table():
    conn = sqlite3.connect(TEACHER_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            class TEXT
        )
    """)
    conn.commit()
    conn.close()

def create_student_table():
    conn = sqlite3.connect(STUDENT_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT NOT NULL,
            rollno TEXT UNIQUE NOT NULL,
            class TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

create_teacher_table()
create_student_table()

def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    print(f"DEBUG: Sheet object: {sheet}") #debug
    return sheet

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "Diatm@226" and password == "226@Diatm":
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html", error=None)

@app.route("/admin_panel")
def admin_panel():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        if "add_teacher" in request.form:
            name = request.form["name"]
            username = request.form["username"]
            password = request.form["password"]
            conn = sqlite3.connect(TEACHER_DB)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO teachers (name, username, password) VALUES (?, ?, ?)", (name, username, password))
                conn.commit()
            except sqlite3.IntegrityError:
                return render_template("teacher_panel.html", error="Username already exists", teachers=get_teachers())

            conn.close()
        elif "delete_teacher" in request.form:
            teacher_id = request.form["teacher_id"]
            conn = sqlite3.connect(TEACHER_DB)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))
            conn.commit()
            conn.close()
    return render_template("admin_panel.html")

@app.route("/teacher_panel", methods=["GET", "POST"])
def teacher_panel():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        if "add_teacher" in request.form:
            name = request.form["name"]
            username = request.form["username"]
            password = request.form["password"]
            conn = sqlite3.connect(TEACHER_DB)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO teachers (name, username, password) VALUES (?, ?, ?)", (name, username, password))
                conn.commit()
            except sqlite3.IntegrityError:
                return render_template("teacher_panel.html", error="Username already exists", teachers=get_teachers())

            conn.close()
        elif "delete_teacher" in request.form:
            teacher_id = request.form["teacher_id"]
            conn = sqlite3.connect(TEACHER_DB)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))
            conn.commit()
            conn.close()

    return render_template("teacher_panel.html", teachers=get_teachers())

def get_teachers():
    conn = sqlite3.connect(TEACHER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teachers")
    teachers = cursor.fetchall()
    conn.close()
    return teachers

@app.route("/student_panel", methods=["GET", "POST"])
def student_panel():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        if "add_student" in request.form:
            name = request.form["name"]
            dob = request.form["dob"]
            rollno = request.form["rollno"]
            conn = sqlite3.connect(STUDENT_DB)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO students (name, dob, rollno) VALUES (?, ?, ?)", (name, dob, rollno))
                conn.commit()
            except sqlite3.IntegrityError:
                return render_template("student_panel.html", error="Roll number already exists", students=get_students())
            conn.close()
        elif "delete_student" in request.form:
            student_id = request.form["student_id"]
            conn = sqlite3.connect(STUDENT_DB)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
            conn.commit()
            conn.close()
    return render_template("student_panel.html", students=get_students())

def get_students():
    conn = sqlite3.connect(STUDENT_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    conn.close()
    return students

@app.route("/teacher_login", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(TEACHER_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teachers WHERE username = ? AND password = ?", (username, password))
        teacher = cursor.fetchone()
        conn.close()
        if teacher:
            session["teacher_id"] = teacher[0]
            session["teacher_class"]= teacher[3]
            return redirect(url_for("teacher_dashboard"))
        else:
            return render_template("teacher_login.html", error="Invalid credentials")
    return render_template("teacher_login.html", error=None)

@app.route("/teacher_dashboard", methods=["GET", "POST"])
def teacher_dashboard():
    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))
    qr_image = None
    if request.method == "POST":
        try:
            now = datetime.datetime.now()
            date_str = now.strftime("%d-%m-%Y")
            data = f"Date: {date_str}, Class: {session['teacher_class']}"

            print(f"DEBUG: QR code data generated: {data}")  # debug

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            img_buffer = BytesIO()
            img.save(img_buffer, format="PNG")
            img_buffer.seek(0)
            qr_image = base64.b64encode(img_buffer.read()).decode("utf-8")
        except Exception as e:
            print(f"Error generating QR code: {e}")
            qr_image = None  # Set to None if error occurs

    return render_template("teacher_dashboard.html", qr_image=qr_image, teacher_class=session["teacher_class"], polls=polls)

@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        rollno = request.form["rollno"]
        dob = request.form["dob"]
        conn = sqlite3.connect(STUDENT_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE rollno = ? AND dob = ?", (rollno, dob))
        student = cursor.fetchone()
        conn.close()
        if student:
            session["student_id"] = student[0]
            session["student_class"] = student[2]
            return redirect(url_for("student"))
        else:
            return render_template("student_login.html", error="Invalid credentials")
    return render_template("student_login.html", error=None)

@app.route("/student", methods=["GET", "POST"])
def student():
    if "student_id" not in session:
        return redirect(url_for("student_login"))
    
    if request.method == "POST":
        qr_data = request.form.get("qr_data")

        print(f"DEBUG: QR code data received: {qr_data}") #debug line
        print(f"DEBUG: Student class from session: {session['student_class']}") #debug line
        
        date_str = qr_data.split("Date: ")[1].split(",")[0]
        sheet = get_google_sheet()
        try:
            rollno = None
            conn = sqlite3.connect(STUDENT_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT rollno FROM students WHERE id = ?", (session["student_id"],))
            result = cursor.fetchone()
            if result:  # Check if a row was found
                rollno = result[0]  # rollno is the first (and only) column selected
                print(rollno)  # debug line
            else:
                print("Student not found")
            conn.close()

            students = sheet.get_all_values()
            header = students[0]
            if date_str not in header:
                sheet.update_cell(1, len(header) + 1, date_str)

            students = sheet.get_all_values()
            header = students[0]
            date_column = header.index(date_str) + 1
            for row_index, row in enumerate(students):
                if row[3] == rollno:
                    sheet.update_cell(row_index + 1, date_column, "Present")
                    return "Attendance marked successfully"
            return "Student not found in sheet"
        except Exception as e:
            return f"Error marking attendance: {e}"
    

    return render_template("student.html", polls=polls, student_class=session["student_class"])

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)