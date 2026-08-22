import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# PostgreSQL साठी psycopg2 लोड करणे
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

app = Flask(__name__)
app.secret_key = 'quizops_secret_key_123'

# Render Environment मधून Database URL घेणे
DATABASE_URL = os.environ.get('DATABASE_URL')

# SQLite साठी Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, 'quizops.db')

# ------------------------------------
# DATABASE CONNECTION & WRAPPER
# ------------------------------------
class DBConnection:
    def __init__(self):
        self.is_postgres = bool(DATABASE_URL and HAS_PSYCOPG2)
        if self.is_postgres:
            # Render PostgreSQL URL मधील postgres:// फिक्स करणे
            url = DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            self.conn = psycopg2.connect(url)
            self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            self.conn = sqlite3.connect(SQLITE_DB_PATH)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()

    def execute(self, query, params=()):
        # PostgreSQL आणि SQLite साठी placeholders (?) ट्यून करणे
        if self.is_postgres:
            query = query.replace('?', '%s')
            query = query.replace('AUTOINCREMENT', '')
        self.cursor.execute(query, params)
        return self.cursor

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.cursor.close()
        self.conn.close()

def get_db():
    return DBConnection()

def init_db():
    db = get_db()
    
    # Auto-Increment सुसंगतता
    pk_type = "SERIAL PRIMARY KEY" if db.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # 1. Users Table
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS users (
            id {pk_type},
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role VARCHAR(20) NOT NULL
        )
    ''')
    
    # 2. Quizzes Table
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS quizzes (
            id {pk_type},
            title VARCHAR(200) NOT NULL,
            description TEXT,
            subject VARCHAR(100),
            duration INTEGER NOT NULL,
            pass_percentage INTEGER NOT NULL,
            created_by INTEGER REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # 3. Questions Table
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS questions (
            id {pk_type},
            quiz_id INTEGER NOT NULL REFERENCES quizzes (id) ON DELETE CASCADE,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option VARCHAR(10) NOT NULL
        )
    ''')

    # 4. Results Table
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS results (
            id {pk_type},
            student_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            quiz_id INTEGER NOT NULL REFERENCES quizzes (id) ON DELETE CASCADE,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            percentage REAL NOT NULL,
            status VARCHAR(20) NOT NULL,
            date_today VARCHAR(50) NOT NULL
        )
    ''')

    # Create Default Admin User
    db.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not db.fetchone():
        hashed_pw = generate_password_hash('admin123')
        db.execute(
            'INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
            ('admin', 'admin@quizops.com', hashed_pw, 'Admin')
        )

    db.commit()
    db.close()

init_db()

# ------------------------------------
# AUTHENTICATION & HOME ROUTES
# ------------------------------------
@app.route('/')
def home():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'Admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'Teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        db = get_db()
        db.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username))
        user = db.fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            flash('Login Successful!', 'success')
            if user['role'] == 'Admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'Teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid Username/Email or Password!', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        role = request.form.get('role', 'Student')
        
        hashed_password = generate_password_hash(password)
        
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                       (username, email, hashed_password, role))
            db.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('Username or Email already exists!', 'danger')
        finally:
            db.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# ------------------------------------
# ADMIN ROUTES
# ------------------------------------
@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    
    db = get_db()
    db.execute('SELECT * FROM users')
    users = db.fetchall()
    
    db.execute('SELECT * FROM quizzes')
    quizzes = db.fetchall()
    db.close()
    
    return render_template('admin_dashboard.html', users=users, quizzes=quizzes)

@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
        
    username = request.form['username'].strip()
    email = request.form['email'].strip()
    password = request.form['password'].strip()
    role = request.form['role']
    
    hashed_password = generate_password_hash(password)
    
    db = get_db()
    try:
        db.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                   (username, email, hashed_password, role))
        db.commit()
        flash('User added successfully!', 'success')
    except Exception:
        flash('Username or Email already exists!', 'danger')
    finally:
        db.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
        
    db = get_db()
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        role = request.form['role']
        
        db.execute('UPDATE users SET username = ?, email = ?, role = ? WHERE id = ?',
                   (username, email, role, user_id))
        db.commit()
        db.close()
        flash('User updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
        
    db.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = db.fetchone()
    db.close()
    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
        
    db = get_db()
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    db.close()
    flash('User deleted successfully!', 'info')
    return redirect(url_for('admin_dashboard'))

# ------------------------------------
# TEACHER ROUTES
# ------------------------------------
@app.route('/teacher/dashboard')
def teacher_dashboard():
    if session.get('role') != 'Teacher':
        return redirect(url_for('login'))
    
    db = get_db()
    db.execute('SELECT * FROM quizzes WHERE created_by = ?', (session['user_id'],))
    quizzes = db.fetchall()
    db.close()
    return render_template('teacher_dashboard.html', quizzes=quizzes)

@app.route('/create_quiz', methods=['GET', 'POST'])
def create_quiz():
    if session.get('role') not in ['Teacher', 'Admin']:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        subject = request.form.get('subject')
        duration = request.form.get('duration')
        pass_percentage = request.form.get('pass_percentage')
        
        db = get_db()
        if db.is_postgres:
            db.execute('''
                INSERT INTO quizzes (title, description, subject, duration, pass_percentage, created_by)
                VALUES (?, ?, ?, ?, ?, ?) RETURNING id
            ''', (title, description, subject, duration, pass_percentage, session['user_id']))
            quiz_id = db.fetchone()['id']
        else:
            db.execute('''
                INSERT INTO quizzes (title, description, subject, duration, pass_percentage, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, description, subject, duration, pass_percentage, session['user_id']))
            quiz_id = db.cursor.lastrowid
            
        db.commit()
        db.close()
        
        return redirect(f'/add_questions/{quiz_id}')
        
    return render_template('create_quiz.html')

@app.route('/add_questions/<int:quiz_id>', methods=['GET', 'POST'])
def add_questions(quiz_id):
    if session.get('role') not in ['Teacher', 'Admin']:
        return redirect(url_for('login'))
        
    db = get_db()
    if request.method == 'POST':
        question_text = request.form['question_text']
        option_a = request.form['option_a']
        option_b = request.form['option_b']
        option_c = request.form['option_c']
        option_d = request.form['option_d']
        correct_option = request.form['correct_option']
        
        db.execute('''
            INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option))
        db.commit()
        flash('Question added successfully!', 'success')
        
    db.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,))
    questions = db.fetchall()
    
    db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,))
    quiz = db.fetchone()
    db.close()
    
    return render_template('add_questions.html', quiz=quiz, questions=questions)

# ------------------------------------
# STUDENT ROUTES
# ------------------------------------
@app.route('/student/dashboard')
def student_dashboard():
    if session.get('role') != 'Student':
        return redirect(url_for('login'))
        
    db = get_db()
    
    db.execute('''
        SELECT q.*, u.username AS teacher_name 
        FROM quizzes q
        LEFT JOIN users u ON q.created_by = u.id
    ''')
    quizzes = db.fetchall()
    
    db.execute('''
        SELECT r.*, q.title AS quiz_title, q.subject
        FROM results r
        JOIN quizzes q ON r.quiz_id = q.id
        WHERE r.student_id = ?
    ''', (session['user_id'],))
    results = db.fetchall()
    
    db.close()
    return render_template('student_dashboard.html', quizzes=quizzes, results=results)

@app.route('/download_certificate/<int:result_id>')
def download_certificate(result_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    db.execute('''
        SELECT r.*, q.title AS quiz_title, q.subject, u.username 
        FROM results r
        JOIN quizzes q ON r.quiz_id = q.id
        JOIN users u ON r.student_id = u.id
        WHERE r.id = ?
    ''', (result_id,))
    result = db.fetchone()
    db.close()

    if not result:
        flash('Result record not found!', 'danger')
        return redirect(url_for('student_dashboard'))

    return render_template('certificate.html', result=result)

@app.route('/take_quiz/<int:quiz_id>')
def take_quiz(quiz_id):
    if session.get('role') != 'Student':
        return redirect(url_for('login'))
        
    db = get_db()
    db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,))
    quiz = db.fetchone()
    
    db.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,))
    questions = db.fetchall()
    db.close()
    
    return render_template('take_quiz.html', quiz=quiz, questions=questions)

@app.route('/submit_quiz/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    if session.get('role') != 'Student' or 'user_id' not in session:
        return redirect(url_for('login'))
        
    student_id = session['user_id']
    
    db = get_db()
    db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,))
    quiz = db.fetchone()
    
    db.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,))
    questions = db.fetchall()
    
    if not quiz or not questions:
        db.close()
        flash('Quiz or questions not found!', 'danger')
        return redirect(url_for('student_dashboard'))

    score = 0
    total_questions = len(questions)

    for q in questions:
        selected_option = request.form.get(f'question_{q["id"]}')
        if selected_option and selected_option.strip().upper() == str(q['correct_option']).strip().upper():
            score += 1

    percentage = round((score / total_questions) * 100, 2) if total_questions > 0 else 0.0
    pass_percentage = quiz['pass_percentage']
    status = 'Pass' if percentage >= pass_percentage else 'Fail'
    date_today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        db.execute('''
            INSERT INTO results (student_id, quiz_id, score, total_questions, percentage, status, date_today)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, quiz_id, score, total_questions, percentage, status, date_today))
        db.commit()
        flash('Quiz submitted successfully!', 'success')
    except Exception:
        db.rollback()
        flash('An error occurred while submitting the quiz.', 'danger')
    finally:
        db.close()
        
    return redirect(url_for('student_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
