from flask import Flask, render_template, request, redirect, session
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # required for sessions

# MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",       # your admin password
    database="exam_registration"
)
cursor = db.cursor(dictionary=True)

@app.route('/')
def home():
    return render_template('Login.html')
        

@app.route('/info')
def info():
    return render_template('Info.html')


@app.route('/faculty')
def faculty():
    return render_template('Faculty.html')

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
    students = cursor.fetchall()
    
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
        exams_for_student = cursor.fetchall()
        student_data.append({'student': student, 'exams': exams_for_student})
    
    # Updated render_template call
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
