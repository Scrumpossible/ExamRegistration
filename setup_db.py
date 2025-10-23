"""
setup_db.py
Initializes the MySQL database for the Flask Exam Registration app.

Run this ONCE before running app.py on a new computer:
    python setup_db.py
"""

import mysql.connector

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

conn.commit()
cursor.close()
conn.close()

print("\nDatabase setup complete. You can now run `python app.py`.")
