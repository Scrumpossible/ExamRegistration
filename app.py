from flask import Flask, render_template, request, redirect, session, url_for, flash
from mysql.connector import connect
from werkzeug.security import generate_password_hash, check_password_hash

## Flask app initialization
# @brief Creates and configures the Flask application
app = Flask(__name__)
 # used for securely signing session cookies
app.secret_key = 'your_secret_key'

## Database connection
# Establishes connection with the MySQL database using creds
db = connect(
    host='localhost',
    user='root',
    # Make sure to change to match ur pw
    password='root',
    database='exam_registration'
)

## Authenticates users based on csn email and nshe/employee number (password)
# @rtype: redirect or html template
# @returns: Redirects to the student, faculty or rerenders the login page if invalid
@app.route('/', methods=['GET', 'POST'])
def login():
    # Checks if form is submitted via POST
    if request.method == 'POST':
        # Get user input from form
        email = request.form['email']
        nshe = request.form['nshe']

        # create a database cursor
        # returns results as dictionaries
        cur = db.cursor(dictionary=True)

        # Query the table to check for matching email
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))

        # Retrieve the record associated to the email
        user = cur.fetchone()

        # Closing the cursor
        cur.close()

        # If a user was found and password (hash) matches NSHE/employee number
        if user and check_password_hash(user['password'], nshe):
            # Store user info for access control
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['full_name'] = user['full_name']

            # Normalize role to lowercase to avoid case mismatch
            if user['role'].strip().lower() == 'student':
                # Redirect to student dashboard
                return redirect(url_for('student_home'))
            else:
                # Redirect to faculty dashboard
                return redirect(url_for('faculty_home'))
        
        # Flash an error message if creds are invalid
        flash("Invalid Credentials")

    # Render the login page for GET requests or failed login
    return render_template('login.html')


## Creates new account for students and faculty
# @rtype: redirect or template
# @returns: Redirects to login after successful registration or rerenders registration form with an error
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Checks if form is submitted via POST
    if request.method == 'POST':
        # Get user input from form
        email = request.form['email']
        full_name = request.form['full_name']
        role = request.form['role']
        
        # Inputs based on role
        if role == 'student':
            identifier = request.form['nshe']
            # Check for correct student email format
            if not email.endswith('@student.csn.edu'):
                flash('Student email must end with @student.csn.edu')
                return render_template('register.html')
        else:
            # Refering to employee number
            identifier = request.form['employee']
            # Check for correct faculty email format
            if not email.endswith('@csn.edu') or email.endswith('@student.csn.edu'):
                flash('Faculty email must end with @csn.edu')
                return render_template('register.html')
        
        # Hash the identifier (password)
        hashed_pw = generate_password_hash(identifier)

        # Create a database cursor
        cur = db.cursor()
        # Insert new record into database
        cur.execute(
            "INSERT INTO users (email, nshe_num, full_name, role, password) VALUES (%s,%s,%s,%s,%s)",
            (email, identifier, full_name, role, hashed_pw)
        )

        # Save changes
        db.commit()

        # Closing the cursor
        cur.close()

        # Notification of success
        flash('Account created successfully. Redirecting to login page...')

        # Redirects to success page (very brief)
        return render_template('register_success.html')

    # Render registration for GET requests
    return render_template('register.html')


## Displays student dashboard
#  @rtype: template
#  @returns: Renders student html with list of exams
@app.route('/student')
def student_home():
    # Check that user if logged in and is listed as 'student'
    if 'user_id' not in session or session['role'].strip().lower() != 'student':
        return redirect(url_for('login'))
    
    # Create a database cursor
    cur = db.cursor(dictionary=True)

    # Get all data from exams
    cur.execute("SELECT * FROM exams")
    exams = cur.fetchall()

    # Closing the cursor
    cur.close()

    # Render student dashboard with exam data
    return render_template('student_home.html', exams=exams, name=session['full_name'])


## Displays faculty dashboard
#  @rtype: template
#  @returns: Renders faculty html with list of sessions they proctor.
@app.route('/faculty')
def faculty_home():
    # Check user is logged in and is listed as 'faculty'
    if 'user_id' not in session or session['role'].strip().lower() != 'faculty':
        return redirect(url_for('login'))
    
    # Create a database cursor
    cur = db.cursor(dictionary=True)

    # Get all data from exams
    cur.execute("""
        SELECT e.name, s.session_date, s.session_time, l.campus_name, l.room_number
        FROM exam_sessions s
        JOIN exams e ON s.exam_id = e.id
        JOIN locations l ON s.location_id = l.id
        WHERE s.proctor_id = %s
    """, (session['user_id'],))
    sessions = cur.fetchall()

    # I am still working out some things to edit sessions
    # so i just have the above as default for rn

    # Closing the cursor
    cur.close()

    # Render faculty dashboard
    return render_template('faculty_home.html', sessions=sessions, name=session['full_name'])


## Clears all session data and redirects to the login page (aka logs out user)
#  @rtype: redirect
#  @returns: Redirects to login page after logging out
@app.route('/logout')
def logout():
    # remove all session vars
    session.clear()

    # Redirect to login page
    return redirect(url_for('login'))


## Runs Flask application
if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)
