from flask import Flask, render_template, request, redirect, session, url_for, flash
import os
import smtplib
from email.message import EmailMessage
import mysql.connector

app = Flask(__name__)
app.secret_key= 'your_secret_key'

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="$Q7!",
        database="exam_registration",
        use_pure=True 
    )

## SEND EMAIL ##
EMAIL_FROM = "no-reply@csn.edu"
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587")) if os.environ.get("SMTP_HOST") else None
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

def send_email(to_addr: str, subject: str, body: str):
    # If SMTP not configured, just log and return (so the app works out of the box).
    if not SMTP_HOST:
        print(f"[EMAIL STUB] To: {to_addr}\nSubj: {subject}\n{body}\n---")
        return
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

## GET USER INFO ##
def get_user_info(user_id: int):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, first_name, last_name, email, nshe_num, role FROM users WHERE id=%s", (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()

## HOME ##
@app.route("/")
def home():
    if "user_id" in session:
        role = session.get("role")

        if role == "student":
            return redirect(url_for("student_home"))
        if role == "faculty":
            return redirect(url_for("faculty_home"))
        if role == "admin":
            return redirect(url_for("admin_dashboard"))

    return render_template("login.html")

## LOGIN ##
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # create a fresh connection and cursor
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
            user = cursor.fetchone()
        finally:
            cursor.close()
            db.close()

        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            if user["role"] == "student":
                return redirect(url_for("student_home"))
            if user["role"] == "faculty":
                return redirect(url_for("faculty_home"))
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("home"))
        error = "Invalid credentials."

    return render_template("login.html", error=error)

## LOGOUT ##
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

## CREATE USER ##
@app.route('/register', methods= ['GET', 'POST'])
def register():
    if request.method == "POST":
        role = request.form.get("role","").strip().lower()
        first_name = request.form.get("first_name","").strip()
        last_name = request.form.get("last_name","").strip()
        email = request.form.get("email","").strip().lower()
        nshe_num = request.form.get("nshe_num","").strip()
        password = request.form.get("password","").strip()

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        try:
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("Email already registered.", "warning")
                return render_template("register.html")
            cursor.execute("""
                INSERT INTO users (first_name, last_name, email, nshe_num, password, role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, email, nshe_num, password, role))
            db.commit()
            return render_template('register_success.html')
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
        finally:
            cursor.close()
            db.close()

    return render_template("register.html")

## ADMIN LOGIN ##
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT id, role FROM users
                WHERE email=%s AND password=%s AND role='admin'
            """, (email, password))
            user_row = cursor.fetchone()
        finally:
            cursor.close()
            db.close()

        if user_row:
            session["user_id"] = user_row["id"]
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "danger")

    return render_template("admin_login.html")

## ADMIN DASHBOARD ##
@app.route('/admin/dashboard')
def admin_dashboard():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM exams ORDER BY exam_name")
        exams = cursor.fetchall()

        cursor.execute("SELECT * FROM locations ORDER BY campus_name, room_number")
        locations = cursor.fetchall()

        cursor.execute("SELECT id, first_name, last_name, email FROM users WHERE role='faculty' ORDER BY last_name, first_name")
        proctors = cursor.fetchall()

        cursor.execute("SELECT id, start_time FROM time_slots ORDER BY start_time")
        time_slots = cursor.fetchall()

        # Sessions (w/ capacity + remaining + proctor name)
        cursor.execute("""
            SELECT s.id, s.session_date, s.session_time, s.capacity,
                   l.campus_name, l.room_number,
                   CONCAT(p.last_name, ', ', p.first_name) AS proctor_name,
                   COALESCE(seats.booked,0) AS booked,
                   (s.capacity - COALESCE(seats.booked,0)) AS remaining
            FROM exam_sessions s
            JOIN locations l ON l.id = s.location_id
            LEFT JOIN users p ON p.id = s.proctor_id
            LEFT JOIN (SELECT session_id, COUNT(*) AS booked FROM registrations GROUP BY session_id) seats
                   ON seats.session_id = s.id
            ORDER BY s.session_date, s.session_time, l.campus_name
        """)
        sessions = cursor.fetchall()

        # Exams offered per session
        cursor.execute("""
            SELECT eso.session_id, e.id AS exam_id, e.exam_name
            FROM exam_sessions_offered eso
            JOIN exams e ON e.id = eso.exam_id
            ORDER BY eso.session_id, e.exam_name
        """)
        offered = cursor.fetchall()

        # Simple student list and their registrations (for quick report)
        cursor.execute("SELECT id, first_name, last_name, email FROM users WHERE role='student' ORDER BY last_name, first_name")
        students = cursor.fetchall()

        cursor.execute("""
            SELECT r.user_id, e.exam_name,
                s.session_date, s.session_time,
                l.campus_name, l.room_number
            FROM registrations r
            JOIN exams e ON e.id = r.exam_id
            JOIN exam_sessions s ON s.id = r.session_id
            JOIN locations l ON l.id = s.location_id
            ORDER BY s.session_date DESC, s.session_time DESC
        """)
        registrations = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    return render_template(
        "admin_dashboard.html",
        exams=exams,
        locations=locations,
        proctors=proctors,
        time_slots=time_slots,
        sessions=sessions,
        offered=offered,
        students=students,
        registrations=registrations
    )

## ADMIN ADD EXAM ##
@app.route('/admin/add_exam', methods=['POST'])
def add_exam():
    exam_name = request.form.get("exam_name","").strip()
    description = request.form.get("description","").strip()

    if not exam_name:
        flash("Enter exam name.", "warning")
        return redirect('/admin/dashboard')

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    try:
        cursor.execute("INSERT INTO exams (exam_name, description) VALUES (%s, %s)", (exam_name, description))
        db.commit()
        flash("Exam added.", "success")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN DELETE EXAM ##
@app.route("/admin/delete_exam/<int:exam_id>", methods=["POST"])
def delete_exam(exam_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("DELETE FROM exams WHERE id=%s", (exam_id,))
        db.commit()
        flash("Exam deleted.", "info")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN ADD LOCATION ##
@app.route('/admin/add_location', methods=['POST'])
def add_location():
    campus_name = request.form.get("campus_name","").strip()
    room_number = request.form.get("room_number","").strip()

    if not campus_name or not room_number:
        flash("Campus and room required.", "warning")
        return redirect('/admin/dashboard')

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("INSERT INTO locations (campus_name, room_number) VALUES (%s, %s)", (campus_name, room_number))
        db.commit()
        flash("Location added.", "success")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN DELETE LOCATION ##
@app.route('/admin/delete_location/<int:location_id>')
def delete_location(location_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("DELETE FROM locations WHERE id=%s", (location_id,))
        db.commit()
        flash("Location deleted.", "info")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN ADD TIME SLOT ##
@app.route("/admin/add_slot", methods=["POST"])
def add_slot():
    start_time = request.form.get("start_time","").strip()  # e.g., "09:00:00"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("INSERT INTO time_slots (start_time) VALUES (%s)", (start_time,))
        db.commit()
        flash("Time slot added.", "success")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN DELETE SLOT ##
@app.route("/admin/delete_slot/<int:slot_id>", methods=["POST"])
def delete_slot(slot_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("DELETE FROM time_slots WHERE id=%s", (slot_id,))
        db.commit()
        flash("Time slot deleted.", "info")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN ADD SESSION ##
@app.route("/admin/add_session", methods=["POST"])
def add_session():
    session_date = request.form.get("session_date","").strip()   # YYYY-MM-DD
    session_time = request.form.get("session_time","").strip()   # HH:MM:SS
    location_id  = request.form.get("location_id", type=int)
    capacity     = request.form.get("capacity", type=int, default=20)
    proctor_id   = request.form.get("proctor_id", type=int) or None

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            INSERT INTO exam_sessions (session_date, session_time, location_id, proctor_id, capacity)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_date, session_time, location_id, proctor_id, capacity))
        db.commit()
        flash("Session added.", "success")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN DELETE SESSION ##
@app.route("/admin/delete_session/<int:session_id>", methods=["POST"])
def delete_session(session_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("DELETE FROM exam_sessions WHERE id=%s", (session_id,))
        db.commit()
        flash("Session deleted.", "info")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN ASSIGN PROCTOR ##
@app.route("/admin/assign_proctor", methods=["POST"])
def assign_proctor():
    session_id = request.form.get("session_id", type=int)
    proctor_id = request.form.get("proctor_id", type=int) or None

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("UPDATE exam_sessions SET proctor_id=%s WHERE id=%s", (proctor_id, session_id))
        db.commit()
        flash("Proctor updated.", "success")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN ADD OFFERING ##
@app.route("/admin/add_offering", methods=["POST"])
def add_offering():
    session_id = request.form.get("session_id", type=int)
    exam_id    = request.form.get("exam_id", type=int)

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            INSERT INTO exam_sessions_offered (session_id, exam_id)
            VALUES (%s, %s)
        """, (session_id, exam_id))
        db.commit()
        flash("Offering added to session.", "success")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN DELETE OFFERING ##
@app.route("/admin/delete_offering", methods=["POST"])
def delete_offering():
    session_id = request.form.get("session_id", type=int)
    exam_id    = request.form.get("exam_id", type=int)

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("DELETE FROM exam_sessions_offered WHERE session_id=%s AND exam_id=%s", (session_id, exam_id))
        db.commit()
        flash("Offering removed.", "info")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')

## ADMIN REMOVE REGISTRATION ##
@app.route("/admin/remove_registration", methods=["POST"])
def remove_registration():
    user_id    = request.form.get("user_id", type=int)
    session_id = request.form.get("session_id", type=int)

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("DELETE FROM registrations WHERE user_id=%s AND session_id=%s", (user_id, session_id))
        db.commit()
        flash("Registration removed.", "info")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect('/admin/dashboard')


## FACULTY PAGE ##
@app.route("/faculty")
def faculty_home():
    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT s.id AS session_id,
                s.session_date, s.session_time,
                l.campus_name, l.room_number,
                e.exam_name,
                stu.first_name AS student_first,
                stu.last_name AS student_last,
                stu.email AS student_email
            FROM exam_sessions s
            JOIN locations l ON l.id = s.location_id
            JOIN registrations r ON r.session_id = s.id
            JOIN users stu ON stu.id = r.user_id AND stu.role='student'
            JOIN exams e ON e.id = r.exam_id
            WHERE s.proctor_id = %s
            ORDER BY s.session_date, s.session_time, e.exam_name, student_last, student_first
        """, (session["user_id"],))
        rows = cur.fetchall()
    finally:
        cur.close()
        db.close()

    return render_template("faculty_home.html", rows=rows)

## STUDENT PAGE ##
@app.route("/student")
def student_home():
    return render_template("student_home.html")

## APP ENTRY ##
if __name__ == '__main__':
    app.run(host='localhost', port = 5000, debug = True)