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

    faculty_name = session.get('name', 'Faculty')
    today = date.today()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.session_date, s.session_time, e.name AS exam_name,
               l.campus_name, l.room_number, CONCAT(u.first_name, ' ', u.last_name) AS student_name
        FROM exam_sessions s
        JOIN registrations r ON r.session_id = s.id
        JOIN users u ON r.user_id = u.id
        JOIN exams e ON s.exam_id = e.id
        JOIN locations l ON s.location_id = l.id
        WHERE s.session_date >= %s
        ORDER BY s.session_date, s.session_time, u.first_name, u.last_name
    """, (today,))

    results = cursor.fetchall()
    cursor.close()
    db.close()

    # --- Build schedule dictionary safely ---
    schedule = {}
    for row in results:
        session_date = row['session_date']
        session_time = row['session_time']

        # Handle MySQL TIME fields that may come as timedelta
        if isinstance(session_time, timedelta):
            session_time = (datetime.min + session_time).time()

        if session_date is None or session_time is None:
            continue  # Skip incomplete rows

        date_str = session_date.strftime("%Y-%m-%d")
        time_str = session_time.strftime("%I:%M %p")

        # Initialize day structure if missing
        if date_str not in schedule:
            schedule[date_str] = {f"{hour:02d}:00 AM" if hour < 12 else f"{hour-12:02d}:00 PM": []
                                  for hour in range(8, 17)}

        # Append student info to correct time slot
        if time_str not in schedule[date_str]:
            schedule[date_str][time_str] = []

        schedule[date_str][time_str].append(row)

    return render_template('faculty_home.html', name=faculty_name, schedule=schedule)

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
            session['name'] = f"{user['first_name']} {user['last_name']}"
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
    print("DEBUG: Registration POST received")
    print("Form data:", request.form)

    if request.method == 'POST':
        role = request.form['role']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        nshe_num = request.form.get('nshe_num')
        employee_number = request.form.get('employee_number')
        password = request.form['password']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                error_msg = "Email already registered!"
                cursor.close()
                conn.close()
                return render_template('register.html', error=error_msg)

            # Insert new user
            cursor.execute("""
                INSERT INTO users 
                    (first_name, last_name, email, nshe_num, role, password)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, email, nshe_num, role, password))

            conn.commit()
            return render_template('register_success.html')

        except mysql.connector.Error as err:
            error_msg = f"Database error: {err}"
            try:
                if cursor:
                    cursor.close()
                if conn and conn.is_connected():
                    conn.close()
            except Exception:
                pass
            return render_template('register.html', error=error_msg)
        finally:
            try:
                if conn and conn.is_connected():
                    cursor.close()
                    conn.close()
            except Exception:
                pass

    return render_template('register.html')

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
            CONCAT(u.first_name, ' ', u.last_name) AS proctor_name
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
@app.route('/exam_register', methods=['GET', 'POST'])
def exam_register():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    student_id = session['user_id']
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        session_str = request.form.get('session_id')
        if not session_str:
            flash("Please select exam, location, date, and time.")
            return redirect('/exam_register')

        try:
            # Split pseudo session_id from hidden input
            exam_id, location_id, session_date, session_time = session_str.split("_")
            exam_id = int(exam_id)
            location_id = int(location_id)
            session_date_obj = datetime.strptime(session_date, "%Y-%m-%d").date()
            session_time_obj = datetime.strptime(session_time, "%H:%M").time()
        except Exception:
            flash("Invalid session selection.")
            return redirect('/exam_register')

        # Check if session exists
        cursor.execute("""
            SELECT id FROM exam_sessions
            WHERE exam_id=%s AND location_id=%s AND session_date=%s AND session_time=%s
        """, (exam_id, location_id, session_date_obj, session_time_obj))
        row = cursor.fetchone()

        if row:
            session_id = row['id']
        else:
            # Create session if not exists
            cursor.execute("""
                INSERT INTO exam_sessions (exam_id, location_id, proctor_id, session_date, session_time)
                VALUES (%s, %s, NULL, %s, %s)
            """, (exam_id, location_id, session_date_obj, session_time_obj))
            db.commit()
            session_id = cursor.lastrowid

        # Check if student already has 3 exams
        cursor.execute("SELECT COUNT(*) AS count FROM registrations WHERE user_id=%s", (student_id,))
        if cursor.fetchone()['count'] >= 3:
            flash("You have already registered for 3 exams.")
            cursor.close()
            db.close()
            return redirect('/student_home')

        # Register student (only user_id and session_id)
        cursor.execute("""
            INSERT INTO registrations (user_id, session_id)
            VALUES (%s, %s)
        """, (student_id, session_id))
        db.commit()
        cursor.close()
        db.close()
        return render_template('exam_register_success.html')

    # GET request: fetch exams and locations
    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()

    cursor.execute("SELECT * FROM locations")
    locations = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('student_exam_register.html', exams=exams, locations=locations)

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
            SELECT s.id AS session_id,
                e.name AS exam_name,
                l.campus_name,
                l.room_number,
                CONCAT(u.first_name, ' ', u.last_name) AS proctor_name
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
