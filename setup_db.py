-- =====================================
-- Drop existing database (start fresh)
-- =====================================
DROP DATABASE IF EXISTS exam_registration;

-- =====================================
-- Create database and use it
-- =====================================
CREATE DATABASE exam_registration;
USE exam_registration;

-- =====================================
-- Users table
-- =====================================
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    nshe_num VARCHAR(10) UNIQUE NOT NULL,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    role ENUM('student', 'faculty', 'admin') NOT NULL,
    password VARCHAR(255) NOT NULL
);

-- =====================================
-- Locations table
-- =====================================
CREATE TABLE locations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    campus_name ENUM('Henderson', 'North Las Vegas', 'West Charleston') NOT NULL,
    room_number VARCHAR(50) NOT NULL,
    UNIQUE (campus_name, room_number)
);

-- =====================================
-- Exams table
-- =====================================
CREATE TABLE exams (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT
);

-- =====================================
-- Exam Proctors table
-- =====================================
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

-- =====================================
-- Exam Sessions table
-- =====================================
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

-- =====================================
-- Registrations table
-- =====================================
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
);

-- =====================================
-- Insert sample locations
-- =====================================
INSERT INTO locations (campus_name, room_number) VALUES
('Henderson', '101'),
('North Las Vegas', '202'),
('West Charleston', '303');

-- =====================================
-- Insert sample exams
-- =====================================
INSERT INTO exams (name, description) VALUES
('Math 101', 'Basic Mathematics'),
('Physics 101', 'Intro to Physics'),
('Chemistry 101', 'Basic Chemistry');

-- =====================================
-- Insert sample users
-- =====================================
-- Students
INSERT INTO users (email, nshe_num, first_name, last_name, role, password) VALUES
('student1@example.com', '1001', 'Alice', 'Smith', 'student', 'password'),
('student2@example.com', '1002', 'Bob', 'Johnson', 'student', 'password');

-- Faculty
INSERT INTO users (email, nshe_num, first_name, last_name, role, password) VALUES
('faculty1@example.com', '2001', 'Dr', 'Brown', 'faculty', 'password'),
('faculty2@example.com', '2002', 'Prof', 'Green', 'faculty', 'password');

-- =====================================
-- Assign faculty as exam proctors
-- =====================================
INSERT INTO exam_proctors (exam_id, user_id, location_id) VALUES
(1, 3, 1),
(2, 4, 2),
(3, 3, 3);

-- =====================================
-- Create exam sessions
-- =====================================
INSERT INTO exam_sessions (location_id, proctor_id, session_date, session_time) VALUES
(1, 1, '2025-12-15', '09:00:00'),
(2, 2, '2025-12-16', '10:00:00'),
(3, 3, '2025-12-17', '11:00:00');

-- =====================================
-- Example registrations (optional)
-- =====================================
INSERT INTO registrations (user_id, session_id, exam_id) VALUES
(1, 1, 1),
(2, 2, 2);