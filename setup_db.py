"""
setup_db.py
Initializes the MySQL database for the Flask Exam Registration app, including exam sessions.

Run this ONCE before running app.py on a new computer:
    python setup_db.py
"""

import mysql.connector
from datetime import date, timedelta, time

# Database connection settings — adjust if needed
DB_NAME = "exam_registration"
DB_USER = "root"
DB_PASSWORD = "root"
DB_HOST = "localhost"

# --- Connect to MySQL server (no database yet) ---
conn = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()

# --- Create database if not exists ---
cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
cursor.execute(f"USE {DB_NAME}")

# --- Create all tables if not exist ---
TABLES = {}

TABLES["users"] = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    password VARCHAR(100),
    role ENUM('admin','faculty','student') NOT NULL
)
"""

TABLES["exams"] = """
CREATE TABLE IF NOT EXISTS exams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    descriptions TEXT
)
"""

TABLES["locations"] = """
CREATE TABLE IF NOT EXISTS locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    campus_name VARCHAR(100),
    room_number VARCHAR(50)
)
"""

TABLES["exam_sessions"] = """
CREATE TABLE IF NOT EXISTS exam_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT,
    location_id INT,
    session_date DATE,
    session_time TIME,
    proctor_id INT NULL,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (proctor_id) REFERENCES users(id) ON DELETE SET NULL
)
"""

TABLES["registrations"] = """
CREATE TABLE IF NOT EXISTS registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    session_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE
)
"""

for name, ddl in TABLES.items():
    print(f"Creating table `{name}`...")
    cursor.execute(ddl)

# --- Insert a default admin user if not present ---
cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
(admin_exists,) = cursor.fetchone()
if admin_exists == 0:
    cursor.execute("""
        INSERT INTO users (full_name, email, password, role)
        VALUES ('Administrator', 'admin@example.com', 'admin', 'admin')
    """)
    print("Default admin user created: email='admin@example.com', password='admin'")
else:
    print("Admin user already exists.")

# --- Populate exam sessions for all exams and locations ---
cursor.execute("SELECT id FROM exams")
exams = cursor.fetchall()
cursor.execute("SELECT id FROM locations")
locations = cursor.fetchall()

# Configurable date range for exam sessions
start_date = date.today()
end_date = start_date + timedelta(days=14)  # 2 weeks of sessions

time_slots = [time(hour=h) for h in range(8, 17)]  # 8:00 - 16:00 (inclusive)

for exam in exams:
    exam_id = exam[0]
    for loc in locations:
        loc_id = loc[0]
        current_date = start_date
        while current_date <= end_date:
            for t in time_slots:
                cursor.execute("""
                    INSERT INTO exam_sessions (exam_id, location_id, session_date, session_time)
                    VALUES (%s, %s, %s, %s)
                """, (exam_id, loc_id, current_date, t))
            current_date += timedelta(days=1)

conn.commit()
cursor.close()
conn.close()

print("\nDatabase setup complete. Exam sessions created for all exams and locations.")
print("You can now run `python app.py`.")