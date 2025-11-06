from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector

app = Flask(__name__)
app.secret_key= 'your_secret_key'

def get_db_connection():
    import mysql.connector
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
    return render_template('faculty_home.html')

@app.route('/register', methods= ['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        nhse_number = request.form['nhse_number']
        password = request.form['password']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                message = "Email already registered!"
            else:
                # Insert new user
                cursor.execute(
                    "INSERT INTO users (name, email, nhse_number, password) VALUES (%s, %s, %s, %s)",
                    (name, email, nhse_number, password)
                )
                conn.commit()

                # ✅ Flash message and redirect to success page
                flash("Registration successful!")
                return redirect(url_for('/success'))

        except mysql.connector.Error as err:
            message = f"Database error: {err}"

        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    return render_template('register.html')

@app.route('/success')
def success():
    return render_template('register_success.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s AND role='admin'",
            (email, password)
        )
        admin_user = cursor.fetchone()
        cursor.close()
        db.close()
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

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Existing data
    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()

    cursor.execute("SELECT * FROM locations")
    locations = cursor.fetchall()

    cursor.execute("SELECT * FROM users WHERE role='faculty'")
    proctors = cursor.fetchall()

    # Students and their registrations
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
            WHERE r.user_id = %s
        """, (student['id'],))
        exams_for_student = cursor.fetchall() or []
        student_data.append({'student': student, 'exams': exams_for_student})

    cursor.close()
    db.close()

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

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("INSERT INTO exams (name, descriptions) VALUES (%s, %s)", (name, description))
    db.commit()
    cursor.close()
    db.close()

    return redirect('/admin/dashboard')

@app.route('/admin/delete_exam/<int:exam_id>')
def delete_exam(exam_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin')

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM exams WHERE id=%s", (exam_id,))
    db.commit()
    cursor.close()
    db.close()

    return redirect('/admin/dashboard')

@app.route('/admin/add_location', methods=['POST'])
def add_location():
    if not session.get('admin_logged_in'):
        return redirect('/admin')

    campus_name = request.form['campus_name']
    room_number = request.form['room_number']

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("INSERT INTO locations (campus_name, room_number) VALUES (%s, %s)", (campus_name, room_number))
    db.commit()
    cursor.close()
    db.close()

    return redirect('/admin/dashboard')

@app.route('/admin/delete_location/<int:location_id>')
def delete_location(location_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin')

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM locations WHERE id=%s", (location_id,))
    db.commit()
    cursor.close()
    db.close()

    return redirect('/admin/dashboard')

@app.route('/admin/assign_proctor', methods=['POST'])
def assign_proctor():
    if not session.get('admin_logged_in'):
        return redirect('/admin')

    location_id = request.form['location_id']
    proctor_id = request.form['proctor_id']

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE exam_sessions SET proctor_id=%s WHERE location_id=%s", (proctor_id, location_id))
    db.commit()
    cursor.close()
    db.close()

    return redirect('/admin/dashboard')

@app.route('/admin/remove_registration', methods=['POST'])
def remove_registration():
    if not session.get('admin_logged_in'):
        return redirect('/admin')

    user_id = request.form['user_id']
    session_id = request.form['exam_session_id']

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM registrations WHERE user_id=%s AND session_id=%s", (user_id, session_id))
    db.commit()
    cursor.close()
    db.close()

    return redirect('/admin/dashboard')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # create a fresh connection and cursor
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
            if user['role'] == 'faculty':
                return redirect('/faculty')
            elif user['role'] == 'student':
                return redirect('/student')
            else:
                return redirect('/')
        else:
            error = "Invalid credentials"
    return render_template('login.html', error=error)

if __name__ == '__main__':
    app.run(host='localhost', port = 5000, debug = True)



