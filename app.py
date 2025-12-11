from flask import Flask, render_template, request, redirect, session, url_for, flash
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

# ---------- Home ----------
@app.route('/')
def home():
    return render_template('login.html')

# ---------- Register ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form['role']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        nshe_num = request.form.get('nshe_num')
        password = request.form['password']

        if not nshe_num:
            flash(f"NSHE Number is required for {role}.", "error")
            return redirect('/register')

        try:
            db = get_db_connection()
            cursor = db.cursor()

            # Check email
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("Email already registered!", "error")
                return redirect('/register')

            # Check nshe_num
            cursor.execute("SELECT id FROM users WHERE nshe_num=%s", (nshe_num,))
            if cursor.fetchone():
                flash(f"{role.capitalize()} number already registered!", "error")
                return redirect('/register')

            # Insert
            cursor.execute(
                "INSERT INTO users (first_name, last_name, email, password, role, nshe_num) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (first_name, last_name, email, password, role, nshe_num)
            )
            db.commit()
            return render_template('register_success.html')

        except mysql.connector.Error as e:
            db.rollback()
            flash(f"Database error: {e}", "error")
            return redirect('/register')

        finally:
            if db.is_connected():
                cursor.close()
                db.close()

    return render_template('register.html')

# ---------- Login ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
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

# ---------- Logout ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

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
            e.name AS exam_name,
            s.session_date,
            s.session_time,
            l.campus_name,
            l.room_number,
            CONCAT(u.first_name, ' ', u.last_name) AS proctor_name
        FROM registrations r
        JOIN exam_sessions s ON r.session_id = s.id
        JOIN exams e ON s.exam_id = e.id
        JOIN locations l ON s.location_id = l.id
        LEFT JOIN exam_proctors ep ON ep.location_id = l.id
        LEFT JOIN users u ON ep.user_id = u.id
        WHERE r.user_id=%s
        ORDER BY s.session_date, s.session_time
    """, (student_id,))
    sessions = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('student_home.html', sessions=sessions, name=name)

# ---------- Faculty Home ----------
@app.route('/faculty_home')
def faculty_home():
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect('/login')

    faculty_id = session['user_id']
    faculty_name = session.get('name', 'Faculty')
    today = date.today()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.id AS session_id,
            s.session_date,
            s.session_time,
            e.name AS exam_name,
            l.campus_name,
            l.room_number,
            CONCAT(u.first_name, ' ', u.last_name) AS student_name
        FROM exam_sessions s
        LEFT JOIN registrations r ON r.session_id = s.id
        LEFT JOIN users u ON r.user_id = u.id
        JOIN exams e ON s.exam_id = e.id
        JOIN locations l ON s.location_id = l.id
        WHERE s.session_date >= %s
        ORDER BY s.session_date, s.session_time
    """, (today,))
    results = cursor.fetchall()
    cursor.close()
    db.close()

    schedule = {}
    for row in results:
        date_str = row['session_date'].strftime("%Y-%m-%d") if row['session_date'] else "N/A"
        time_val = row['session_time']
        if isinstance(time_val, timedelta):
            time_val = (datetime.min + time_val).time()
        time_str = time_val.strftime("%H:%M") if time_val else "N/A"

        if date_str not in schedule:
            schedule[date_str] = {}
        if time_str not in schedule[date_str]:
            schedule[date_str][time_str] = []
        schedule[date_str][time_str].append(row)

    return render_template('faculty_home.html', name=faculty_name, schedule=schedule)

# ---------- Exam Registration ----------
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
            flash("Please select exam session.")
            return redirect('/exam_register')

        try:
            exam_id, location_id, session_date, session_time = session_str.split("_")
            exam_id = int(exam_id)
            location_id = int(location_id)
            session_date_obj = datetime.strptime(session_date, "%Y-%m-%d").date()
            session_time_obj = datetime.strptime(session_time, "%H:%M").time()
        except Exception:
            flash("Invalid session selection.")
            return redirect('/exam_register')

        # Check existing registrations
        cursor.execute("""
            SELECT s.exam_id, s.session_date, s.session_time
            FROM registrations r
            JOIN exam_sessions s ON r.session_id = s.id
            WHERE r.user_id=%s
        """, (student_id,))
        existing_regs = cursor.fetchall()

        for reg in existing_regs:
            if reg['exam_id'] == exam_id:
                flash("Already registered for this exam.")
                cursor.close()
                db.close()
                return redirect('/exam_register')
            if reg['session_date'] == session_date_obj and reg['session_time'] == session_time_obj:
                flash("Time conflict with another exam.")
                cursor.close()
                db.close()
                return redirect('/exam_register')

        # Limit 3 exams
        cursor.execute("SELECT COUNT(*) AS count FROM registrations WHERE user_id=%s", (student_id,))
        if cursor.fetchone()['count'] >= 3:
            flash("Already registered for 3 exams.")
            cursor.close()
            db.close()
            return redirect('/student_home')

        # Create session if not exists
        cursor.execute("""
            SELECT id FROM exam_sessions
            WHERE exam_id=%s AND location_id=%s AND session_date=%s AND session_time=%s
        """, (exam_id, location_id, session_date_obj, session_time_obj))
        row = cursor.fetchone()
        if row:
            session_id = row['id']
        else:
            # session created without a proctor
            cursor.execute("""
                INSERT INTO exam_sessions (exam_id, location_id, session_date, session_time)
                VALUES (%s,%s,%s,%s)
            """, (exam_id, location_id, session_date_obj, session_time_obj))
            db.commit()
            session_id = cursor.lastrowid

        cursor.execute("INSERT INTO registrations (user_id, session_id, exam_id, registration_date) VALUES (%s,%s,%s,NOW())",
                       (student_id, session_id, exam_id))
        db.commit()
        cursor.close()
        db.close()
        flash("Exam registered successfully!")
        return redirect('/student_home')

    # GET request
    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()

    cursor.execute("SELECT * FROM locations")
    locations = cursor.fetchall()

    # Fetch student's existing registrations
    cursor.execute("""
        SELECT s.exam_id, s.session_date, s.session_time
        FROM registrations r
        JOIN exam_sessions s ON r.session_id = s.id
        WHERE r.user_id = %s
    """, (student_id,))
    existing_regs = cursor.fetchall()

    # Convert times to strings for JSON serialization
    for reg in existing_regs:
        if isinstance(reg['session_time'], (time, timedelta)):
            if isinstance(reg['session_time'], timedelta):
                reg['session_time'] = (datetime.min + reg['session_time']).time()
            reg['session_time'] = reg['session_time'].strftime("%H:%M")

    cursor.close()
    db.close()

    return render_template('student_exam_register.html', exams=exams, locations=locations, existing_regs=existing_regs)

# ---------- Remove Student Registration ----------
@app.route('/remove_registration', methods=['POST'])
def remove_registration():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    student_id = session['user_id']
    session_id = request.form.get('session_id')
    if not session_id:
        flash("No session selected to remove.")
        return redirect('/student_home')

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM registrations WHERE user_id=%s AND session_id=%s", (student_id, session_id))
    db.commit()
    cursor.close()
    db.close()
    flash("Registration removed successfully!")
    return redirect('/student_home')

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

    # Faculty (proctors)
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
            LEFT JOIN exam_proctors ep ON ep.location_id = l.id
            LEFT JOIN users u ON ep.user_id = u.id
            WHERE r.user_id=%s
        """, (student['id'],))
        exams_for_student = cursor.fetchall() or []
        student_data.append({'student': student, 'exams': exams_for_student})

    cursor.close()
    db.close()
    return render_template('admin_home.html', exams=exams, locations=locations, proctors=proctors, student_data=student_data)

# ---------- Add/Delete Exams ----------
@app.route('/admin/add_exam', methods=['POST'])
def add_exam():
    if not session.get('admin_logged_in'):
        return redirect('/login')
    name = request.form['name']
    description = request.form['description']
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("INSERT INTO exams (name, description) VALUES (%s,%s)", (name, description))
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

# ---------- Add/Delete Locations ----------
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

# ---------- Assign Proctor ----------
@app.route('/admin/assign_proctor', methods=['POST'])
def assign_proctor():
    if not session.get('admin_logged_in'):
        return redirect('/login')

    location_id = int(request.form['location_id'])
    proctor_id = int(request.form['proctor_id'])

    db = get_db_connection()
    cursor = db.cursor()

    # Check if a proctor already exists for this location
    cursor.execute("SELECT id FROM exam_proctors WHERE location_id=%s", (location_id,))
    row = cursor.fetchone()

    if row:
        cursor.execute("UPDATE exam_proctors SET user_id=%s WHERE id=%s", (proctor_id, row[0]))
    else:
        cursor.execute("INSERT INTO exam_proctors (location_id, user_id) VALUES (%s, %s)", (location_id, proctor_id))

    db.commit()
    cursor.close()
    db.close()
    return redirect('/admin_home')

# ---------- Remove Admin Registration ----------
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