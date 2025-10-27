from flask import Flask, render_template, request, redirect, session
import mysql.connector
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # required for sessions

# MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="$Q7!",       # your admin password
    database="exam_registration"
)
cursor = db.cursor(dictionary=True)

@app.route('/')
def home():
    return render_template('Login.html')

@app.route('/faculty_home')
def faculty_home():
    return render_template('faculty_home.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s AND role='admin'", (email, password))
        admin_user = cursor.fetchone()
        if admin_user:
            session['admin_logged_in'] = True
            return redirect('/admin/dashboard')
        else:
            return render_template('AdminLogin.html', error="Invalid credentials")
    return render_template('AdminLogin.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    # Existing data
    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()
    
    cursor.execute("SELECT * FROM locations")
    locations = cursor.fetchall()
    
    cursor.execute("SELECT * FROM users WHERE role='faculty'")
    proctors = cursor.fetchall()
    
    # New student registrations section
    cursor.execute("SELECT * FROM users WHERE role='student'")
    students = cursor.fetchall() or []  # Ensure we get an empty list if no students

    student_data = []
    for student in students:  # This loop only runs if there are students
        cursor.execute("""
            SELECT s.id AS session_id, e.name AS exam_name, l.campus_name, l.room_number, u.full_name AS proctor_name
            FROM registrations r
            JOIN exam_sessions s ON r.session_id = s.id
            JOIN exams e ON s.exam_id = e.id
            JOIN locations l ON s.location_id = l.id
            LEFT JOIN users u ON s.proctor_id = u.id
            WHERE r.user_id = %s
        """, (student['id'],))
        exams_for_student = cursor.fetchall() or []  # Ensure list even if no registrations
        student_data.append({'student': student, 'exams': exams_for_student})
    
    return render_template(
        'AdminDashboard.html',
        exams=exams,
        locations=locations,
        proctors=proctors,
        student_data=student_data
    )

@app.route('/admin/add_exam', methods=['POST'])
def add_exam():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    name = request.form['name']
    description = request.form['description']
    cursor.execute("INSERT INTO exams (name, descriptions) VALUES (%s, %s)", (name, description))
    db.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/delete_exam/<int:exam_id>')
def delete_exam(exam_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    cursor.execute("DELETE FROM exams WHERE id=%s", (exam_id,))
    db.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/add_location', methods=['POST'])
def add_location():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    campus_name = request.form['campus_name']
    room_number = request.form['room_number']
    cursor.execute("INSERT INTO locations (campus_name, room_number) VALUES (%s, %s)", (campus_name, room_number))
    db.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/delete_location/<int:location_id>')
def delete_location(location_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    cursor.execute("DELETE FROM locations WHERE id=%s", (location_id,))
    db.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/assign_proctor', methods=['POST'])
def assign_proctor():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    location_id = request.form['location_id']
    proctor_id = request.form['proctor_id']
    # For simplicity, just update exam_sessions table's proctor_id for location
    # If your schema requires, insert into exam_proctors table instead
    cursor.execute("UPDATE exam_sessions SET proctor_id=%s WHERE location_id=%s", (proctor_id, location_id))
    db.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/remove_registration', methods=['POST'])
def remove_registration():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    user_id = request.form['user_id']
    session_id = request.form['exam_session_id']
    
    cursor.execute("DELETE FROM registrations WHERE user_id=%s AND session_id=%s", (user_id, session_id))
    db.commit()
    
    return redirect('/admin/dashboard')

# Get all students
cursor.execute("SELECT * FROM users WHERE role='student'")
students = cursor.fetchall()

# Get registrations for each student
student_data = []
for student in students:
    cursor.execute("""
        SELECT e.name AS exam_name, l.campus_name, l.room_number, u.full_name AS proctor_name
        FROM registrations r
        JOIN exam_sessions s ON r.session_id = s.id
        JOIN exams e ON s.exam_id = e.id
        JOIN locations l ON s.location_id = l.id
        LEFT JOIN users u ON s.proctor_id = u.id
        WHERE r.user_id = %s
    """, (student['id'],))
    exams = cursor.fetchall()
    student_data.append({'student': student, 'exams': exams})

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='localhost', port = 5000, debug = True)
    print('The flask server is running')


# Email
def is_csn_student_email(email):
    # NSHE#@student.csn.edu (e.g., 1234567890@student.csn.edu)
    return re.fullmatch(r"\d{10}@student\.csn\.edu", email) is not None

# Role
def require_role(role):
    return session.get('role') == role

# Get User Info
def current_user_id():
    return session.get('user_id')

# Capacity
def seats_left(session_id):
    cursor.execute("SELECT capacity FROM exam_sessions WHERE id=%s", (session_id,))
    row = cursor.fetchone()
    if not row:
        return 0
    cap = int(row['capacity'])
    cursor.execute("SELECT COUNT(*) AS c FROM registrations WHERE session_id=%s", (session_id,))
    used = int(cursor.fetchone()['c'])
    return max(0, cap - used)


# Faculty/Student Login
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email'].strip().lower()
    password = request.form['password'].strip()

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user:
        return render_template('Login.html', error="Invalid credentials")

    # Requirement: NSHE number is the password (store the same value or check equivalently)
    # Accept either stored password match OR nshe_num match to be flexible.
    if password != user['password'] and password != user['nshe_num']:
        return render_template('Login.html', error="Invalid credentials")

    # Enforce student email format for student role
    if user['role'] == 'student' and not is_csn_student_email(email):
        return render_template('Login.html', error="Students must use NSHE#@student.csn.edu")

    session['user_id'] = user['id']
    session['role'] = user['role']
    session['email'] = user['email']
    session['full_name'] = user['full_name']

    if user['role'] == 'admin':
        return redirect('/admin/dashboard')
    if user['role'] == 'faculty':
        return redirect('/faculty_home')
    return redirect('/student/home')

# Faculty/Student Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/faculty_home')
def faculty_home():
    if not require_role('faculty'):
        return redirect('/')
    # Sessions this faculty member is proctoring, with roster per hour
    faculty_id = current_user_id()
    cursor.execute("""
        SELECT s.id AS session_id, s.session_date, s.session_time, s.capacity,
               l.campus_name, l.room_number
        FROM exam_sessions s
        JOIN locations l ON s.location_id = l.id
        WHERE s.proctor_id = %s
        ORDER BY s.session_date, s.session_time
    """, (faculty_id,))
    sessions = cursor.fetchall()

    schedule = []
    for s in sessions:
        cursor.execute("""
            SELECT u.full_name AS student_name, u.email AS student_email,
                   e.name AS exam_name
            FROM registrations r
            JOIN users u ON r.user_id = u.id
            JOIN exams e ON r.exam_id = e.id
            WHERE r.session_id=%s
            ORDER BY student_name
        """, (s['session_id'],))
        roster = cursor.fetchall()
        s['roster'] = roster
        s['seats_left'] = seats_left(s['session_id'])
        schedule.append(s)

    return render_template('faculty_home.html', schedule=schedule)