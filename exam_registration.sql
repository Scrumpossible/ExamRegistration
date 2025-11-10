CREATE DATABASE IF NOT EXISTS exam_registration;
USE exam_registration;

-- stores all account info (students, faculty, admins)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    nshe_num CHAR(10) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('student', 'faculty', 'admin') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- includes three official CSN campuses and room numbers
CREATE TABLE IF NOT EXISTS locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    campus_name ENUM('Henderson', 'North Las Vegas', 'West Charleston') NOT NULL,
    room_number VARCHAR(20) NOT NULL,
    UNIQUE KEY uq_campus_room (campus_name, room_number)
);

-- different exam types
CREATE TABLE IF NOT EXISTS exams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exam_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- sixty min intervs
CREATE TABLE IF NOT EXISTS time_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    start_time TIME NOT NULL,
    CONSTRAINT chk_start_minute CHECK (MINUTE(start_time) = 0),
    UNIQUE KEY uq_start_time (start_time)
);

-- connects campus, date, time, and proctor
CREATE TABLE IF NOT EXISTS exam_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_date DATE NOT NULL,
    session_time TIME NOT NULL,
    time_slot_id INT,
    location_id INT NOT NULL,
    proctor_id INT,
    capacity INT DEFAULT 20,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (proctor_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (time_slot_id) REFERENCES time_slots(id) ON DELETE SET NULL,
    CONSTRAINT chk_capacity CHECK (capacity BETWEEN 1 AND 20)
);

-- which exams are offered per session
CREATE TABLE IF NOT EXISTS exam_sessions_offered (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    exam_id INT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    UNIQUE KEY uq_session_exam (session_id, exam_id)
);

-- stores student bookings
CREATE TABLE IF NOT EXISTS registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_id INT NOT NULL,
    exam_id INT NOT NULL,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    UNIQUE KEY uq_user_exam (user_id, exam_id),
    UNIQUE KEY uq_user_session (user_id, session_id)
);

-- for confirmation notifications
-- CREATE TABLE IF NOT EXISTS email_outbox (
--    id BIGINT AUTO_INCREMENT PRIMARY KEY,
--    recipient_email VARCHAR(255) NOT NULL,
--    subject VARCHAR(255) NOT NULL,
--    body TEXT NOT NULL,
--    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--    sent_at TIMESTAMP NULL
--);