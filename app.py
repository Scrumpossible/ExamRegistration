from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from datetime import date, datetime, timedelta, time
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="exam_registration",
        use_pure=True 
    )

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/faculty_home')
def faculty_home():
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect('/login')
    return render_template('faculty_home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['full_name']
            if user['role'] == 'student':
                return redirect('/student_home')
            elif user['role'] == 'faculty':
                return redirect('/faculty_home')
            elif user['role'] == 'admin':
                session['admin_logged_in'] = True
                return redirect('/admin_home')
        else:
            error = "Invalid credentials"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        if role == 'student':
            nshe_number = request.form.get('nhse_number', '')
        else:
            nshe_number = request.form.get('employee_number', '')

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            error = "Email already registered!"
        else:
            cursor.execute(
                "INSERT INTO users (full_name, email, nshe_num, role, password) VALUES (%s,%s,%s,%s,%s)",
                (name, email, nshe_number, role, password)
            )
            db.commit()
            cursor.close()
            db.close()
            return redirect('/login')

        cursor.close()
        db.close()

    return render_template('register.html', error=error)

# ---------- Student Home ----------
@app.route('/student_home')
def student_home():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    student_id = session['user_id']
    name = session.get('name', 'Student')

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.id AS session_id,
               e.name,
               s.session_date,
               s.session_time,
               l.campus_name,
               l.room_number,
               u.full_name AS proctor_name
        FROM registrations r
        JOIN exam_sessions s ON r.session_id = s.id
        JOIN exams e ON s.exam_id = e.id
        JOIN locations l ON s.location_id = l.id
        LEFT JOIN users u ON s.proctor_id = u.id
        WHERE r.user_id=%s
        ORDER BY s.session_date, s.session_time
    """, (student_id,))
    sessions = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('student_home.html', sessions=sessions, name=name)

# ---------- Remove registration ----------
@app.route('/remove_registration', methods=['POST'])
def remove_registration():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    session_id = request.form['session_id']
    user_id = session['user_id']

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM registrations WHERE user_id=%s AND session_id=%s", (user_id, session_id))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/student_home')

# ---------- Exam Registration Page ----------
from datetime import date, datetime, time, timedelta

@app.route('/exam_register', methods=['GET', 'POST'])
def exam_register():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    student_id = session['user_id']
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # --- POST: student submitted registration ---
    if request.method == 'POST':
        session_id = request.form['session_id']

        # Check student's current registration count
        cursor.execute("SELECT COUNT(*) AS count FROM registrations WHERE user_id=%s", (student_id,))
        count = cursor.fetchone()['count']
        if count >= 3:
            cursor.close()
            db.close()
            return redirect('/student_home')

        # Check if session is full
        cursor.execute("SELECT COUNT(*) AS count FROM registrations WHERE session_id=%s", (session_id,))
        reg_count = cursor.fetchone()['count']
        if reg_count >= 20:
            cursor.close()
            db.close()
            return redirect('/exam_register')

        # Insert registration
        cursor.execute("INSERT INTO registrations (user_id, session_id) VALUES (%s, %s)", (student_id, session_id))
        db.commit()
        cursor.close()
        db.close()
        return redirect('/student_home')

    # --- GET: show registration form ---
    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()

    cursor.execute("SELECT * FROM locations")
    locations = cursor.fetchall()

    # Get upcoming sessions
    today = date.today()
    now = datetime.now().time()

    cursor.execute("""
        SELECT s.id, s.exam_id, s.location_id, s.session_date, s.session_time,
               l.campus_name, l.room_number,
               u.full_name AS proctor_name,
               (SELECT COUNT(*) FROM registrations r WHERE r.session_id = s.id) AS reg_count
        FROM exam_sessions s
        JOIN locations l ON s.location_id = l.id
        LEFT JOIN users u ON s.proctor_id = u.id
        WHERE s.session_date >= %s
        ORDER BY s.session_date, s.session_time
    """, (today,))
    sessions = cursor.fetchall()

    # Filter out full or past timeslots and convert date/time to strings
    available_sessions = []
    for s in sessions:
        session_time = s['session_time']
        if isinstance(session_time, timedelta):
            session_time = (datetime.min + session_time).time()
        # Skip past times today
        if s['reg_count'] >= 20:
            continue
        if s['session_date'] == today and session_time <= now:
            continue

        # Convert for JSON usage in template
        s['session_date'] = s['session_date'].strftime("%Y-%m-%d")
        s['session_time'] = session_time.strftime("%H:%M")
        available_sessions.append(s)

    cursor.close()
    db.close()

    return render_template('student_exam_register.html',
                           exams=exams,
                           locations=locations,
                           sessions=available_sessions)

# ---------- Admin Home ----------
@app.route('/admin_home')
def admin_home():
    if not session.get('admin_logged_in'):
        return redirect('/login')

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Exams
    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()

    # Locations
    cursor.execute("SELECT * FROM locations")
    locations = cursor.fetchall()

    # Proctors
    cursor.execute("SELECT * FROM users WHERE role='faculty'")
    proctors = cursor.fetchall()

    # Students + registrations
    cursor.execute("SELECT * FROM users WHERE role='student'")
    students = cursor.fetchall() or []

    student_data = []
    for student in students:
        cursor.execute("""
            SELECT s.id AS session_id, e.name AS exam_name, l.campus_name, l.room_number, u.full_name AS proctor_name
            FROM registrations r
            JOIN exam_sessions s ON r.session_id = s.id
            JOIN exams e ON s.exam_id = e.id
            JOIN locations l ON s.location_id = l.id
            LEFT JOIN users u ON s.proctor_id = u.id
            WHERE r.user_id=%s
        """, (student['id'],))
        exams_for_student = cursor.fetchall() or []
        student_data.append({'student': student, 'exams': exams_for_student})

    cursor.close()
    db.close()
    return render_template('admin_home.html', exams=exams, locations=locations,
                           proctors=proctors, student_data=student_data)

# ---------- Add/Remove exams, locations, assign proctor, remove registration ----------
@app.route('/admin/add_exam', methods=['POST'])
def add_exam():
    if not session.get('admin_logged_in'):
        return redirect('/login')
    name = request.form['name']
    description = request.form['description']
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("INSERT INTO exams (name, descriptions) VALUES (%s,%s)", (name, description))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/admin_home')

@app.route('/admin/delete_exam/<int:exam_id>')
def delete_exam(exam_id):
    if not session.get('admin_logged_in'):
        return redirect('/login')
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM exams WHERE id=%s", (exam_id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/admin_home')

@app.route('/admin/add_location', methods=['POST'])
def add_location():
    if not session.get('admin_logged_in'):
        return redirect('/login')
    campus_name = request.form['campus_name']
    room_number = request.form['room_number']
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("INSERT INTO locations (campus_name, room_number) VALUES (%s,%s)", (campus_name, room_number))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/admin_home')

@app.route('/admin/delete_location/<int:location_id>')
def delete_location(location_id):
    if not session.get('admin_logged_in'):
        return redirect('/login')
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM locations WHERE id=%s", (location_id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/admin_home')

@app.route('/admin/assign_proctor', methods=['POST'])
def assign_proctor():
    if not session.get('admin_logged_in'):
        return redirect('/login')
    location_id = request.form['location_id']
    proctor_id = request.form['proctor_id']
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE exam_sessions SET proctor_id=%s WHERE location_id=%s", (proctor_id, location_id))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/admin_home')

@app.route('/admin/remove_registration', methods=['POST'])
def admin_remove_registration():
    if not session.get('admin_logged_in'):
        return redirect('/login')
    user_id = request.form['user_id']
    session_id = request.form['exam_session_id']
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM registrations WHERE user_id=%s AND session_id=%s", (user_id, session_id))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/admin_home')

if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)