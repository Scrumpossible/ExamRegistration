from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from datetime import date, datetime, timedelta, time
import mysql.connector

app = Flask(__name__, static_folder='Static')
app.secret_key = 'your_secret_key'

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="exam_registration",
        use_pure=True 
    )


def get_user_name_expr():
    """Return a SQL expression for user's display name (first_name + last_name)."""
    return "CONCAT(u.first_name, ' ', u.last_name)"

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/faculty_home')
def faculty_home():
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect('/login')

    faculty_name = session.get('name', 'Faculty')
    today = date.today()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    name_expr = get_user_name_expr()
    cursor.execute(f"""
        SELECT s.session_date, s.session_time, e.name AS exam_name,
               l.campus_name, l.room_number,
               {name_expr} AS student_name
        FROM exam_sessions s
        JOIN exam_proctors ep ON s.proctor_id = ep.id
        JOIN registrations r ON r.session_id = s.id
        JOIN users u ON r.user_id = u.id
        JOIN exams e ON ep.exam_id = e.id
        JOIN locations l ON s.location_id = l.id
        WHERE s.session_date >= %s
        ORDER BY s.session_date, s.session_time, student_name
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
            session['name'] = (user.get('first_name', '') + ' ' + user.get('last_name', '')).strip()
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
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        role = request.form.get('role', 'student')
        # Map the form field to the DB `nshe_num` column. For faculty use the employee field.
        if role == 'student':
            nshe_num = request.form.get('nshe_num')
        else:
            nshe_num = request.form.get('employee')
        password = request.form.get('password')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                message = "Email already registered!"
            else:
                # Insert new user (exam_registration.sql schema: first_name, last_name, nshe_num)
                cursor.execute(
                    "INSERT INTO users (first_name, last_name, email, nshe_num, role, password) VALUES (%s, %s, %s, %s, %s, %s)",
                    (first_name, last_name, email, nshe_num, role, password)
                )
                conn.commit()

                # ✅ Flash message and redirect to success page
                flash("Registration successful!")
                return redirect('/register_success')

        except mysql.connector.Error as err:
            message = f"Database error: {err}"

        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    return render_template('register.html')


@app.route('/register_success')
def register_success():
    return render_template('register_success.html')

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
        JOIN exam_proctors ep ON s.proctor_id = ep.id
        JOIN exams e ON ep.exam_id = e.id
        JOIN locations l ON s.location_id = l.id
        LEFT JOIN users u ON ep.user_id = u.id
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

    # --- POST: student submitted registration ---
    if request.method == 'POST':
        session_id = request.form['session_id']

        # Check student's current registration count
        cursor.execute("SELECT COUNT(*) AS count FROM registrations WHERE user_id=%s", (student_id,))
        count = cursor.fetchone()['count']
        if count >= 3:
            cursor.close()
            db.close()
            flash("You have already registered for 3 exams.")
            return redirect('/student_home')

        # Check if session is full
        cursor.execute("SELECT COUNT(*) AS count FROM registrations WHERE session_id=%s", (session_id,))
        reg_count = cursor.fetchone()['count']
        if reg_count >= 20:
            cursor.close()
            db.close()
            flash("That session is full.")
            return redirect('/exam_register')

        # Get exam_id from exam_sessions -> exam_proctors
        cursor.execute("SELECT ep.exam_id AS exam_id FROM exam_sessions s JOIN exam_proctors ep ON s.proctor_id = ep.id WHERE s.id=%s", (session_id,))
        exam_row = cursor.fetchone()
        # cursor is dictionary=True, so fetch returns a dict
        exam_id = exam_row['exam_id'] if exam_row and 'exam_id' in exam_row else None
        
        # Insert registration with exam_id
        cursor.execute("INSERT INTO registrations (user_id, session_id, exam_id) VALUES (%s, %s, %s)", (student_id, session_id, exam_id))
        db.commit()
        cursor.close()
        db.close()
        flash("Exam registered successfully!")
        return redirect('/student_home')

    # --- GET: show registration form ---
    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()

    cursor.execute("SELECT * FROM locations")
    locations = cursor.fetchall()

    today = date.today()
    now = datetime.now().time()

    cursor.execute("""
        SELECT s.id, ep.exam_id, s.location_id, s.session_date, s.session_time,
               l.campus_name, l.room_number,
               CONCAT(u.first_name, ' ', u.last_name) AS proctor_name,
               (SELECT COUNT(*) FROM registrations r WHERE r.session_id = s.id) AS reg_count
        FROM exam_sessions s
        JOIN locations l ON s.location_id = l.id
        JOIN exam_proctors ep ON s.proctor_id = ep.id
        LEFT JOIN users u ON ep.user_id = u.id
        WHERE s.session_date >= %s
        ORDER BY s.session_date, s.session_time
    """, (today,))
    sessions = cursor.fetchall()

    available_sessions = []
    for s in sessions:
        # Convert string date/time to Python types if necessary
        if isinstance(s['session_date'], str):
            s['session_date'] = datetime.strptime(s['session_date'], "%Y-%m-%d").date()
        if isinstance(s['session_time'], timedelta):
            s['session_time'] = (datetime.min + s['session_time']).time()
        elif isinstance(s['session_time'], str):
            s['session_time'] = datetime.strptime(s['session_time'], "%H:%M:%S").time()

        # Skip full sessions or past times today
        if s['reg_count'] >= 20:
            continue
        if s['session_date'] == today and s['session_time'] <= now:
            continue

        s['session_date'] = s['session_date'].strftime("%Y-%m-%d")
        s['session_time'] = s['session_time'].strftime("%I:%M %p").lstrip('0')
        available_sessions.append(s)

    cursor.close()
    db.close()

    return render_template(
        'student_exam_register.html',
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
    # Add full_name field for templates
    for p in proctors:
        p['full_name'] = (p.get('first_name', '') + ' ' + p.get('last_name', '')).strip()

    # Students + registrations
    cursor.execute("SELECT * FROM users WHERE role='student'")
    students = cursor.fetchall() or []
    for s in students:
        s['full_name'] = (s.get('first_name', '') + ' ' + s.get('last_name', '')).strip()

    student_data = []
    for student in students:
        cursor.execute("""
            SELECT s.id AS session_id, e.name AS exam_name, l.campus_name, l.room_number,
                   CONCAT(u.first_name, ' ', u.last_name) AS proctor_name
            FROM registrations r
            JOIN exam_sessions s ON r.session_id = s.id
            JOIN exam_proctors ep ON s.proctor_id = ep.id
            JOIN exams e ON ep.exam_id = e.id
            JOIN locations l ON s.location_id = l.id
            LEFT JOIN users u ON ep.user_id = u.id
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
