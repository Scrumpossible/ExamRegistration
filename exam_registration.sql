CREATE SCHEMA IF NOT EXISTS exam_registration;
USE exam_registration;

CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    nshe_num VARCHAR(10) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role ENUM('student', 'faculty', 'admin') NOT NULL,
    password VARCHAR(255) NOT NULL
);

CREATE TABLE locations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    campus_name ENUM('Henderson', 'North Las Vegas', 'West Charleston') NOT NULL,
    room_number VARCHAR(50) NOT NULL,
    UNIQUE (campus_name, room_number)
);

CREATE TABLE exams (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT
);

-- Each proctor is a user (faculty) assigned to one location
CREATE TABLE exam_proctors (
    id INT PRIMARY KEY AUTO_INCREMENT,
    exam_id INT NOT NULL,
    user_id INT NOT NULL,
    location_id INT NOT NULL,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    UNIQUE (exam_id, user_id)
);

CREATE TABLE exam_sessions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    location_id INT NOT NULL,
    proctor_id INT NOT NULL,
    session_date DATE NOT NULL,
    session_time TIME NOT NULL,
    capacity INT NOT NULL DEFAULT 20,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (proctor_id) REFERENCES exam_proctors(id) ON DELETE CASCADE
);

CREATE TABLE registrations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    session_id INT NOT NULL,
    exam_id INT NOT NULL,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    UNIQUE (user_id, exam_id, session_id)
    -- Optional: CHECK constraint to limit to 3 exams per student would go here (not directly enforceable in MySQL without trigger)
);
