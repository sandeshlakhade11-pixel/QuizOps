from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from io import BytesIO
import sqlite3

app = Flask(__name__)
app.secret_key = 'quizops_secret_key_123'

# ------------------------------------
# DATABASE CONNECTION & INITIALIZATION
# ------------------------------------
def get_db_connection():
    conn = sqlite3.connect('quizops.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # 2. Quizzes Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            subject TEXT,
            duration INTEGER NOT NULL,
            pass_percentage INTEGER NOT NULL,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    # 3. Questions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
        )
    ''')

    # 4. Results Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            percentage REAL NOT NULL,
            status TEXT NOT NULL,
            date_today TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES users (id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
        )
    ''')

    # Create Default Admin User
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute(
            'INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
            ('admin', 'admin@quizops.com', hashed_pw, 'Admin')
        )
        print("Default Admin Account Created -> Username: admin | Password: admin123")

    conn.commit()
    conn.close()

init_db()

# ------------------------------------
# AUTHENTICATION & HOME ROUTES
# ------------------------------------
@app.route('/')
def home():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'Admin':
            return redirect('/admin/dashboard')
        elif role == 'Teacher':
            return redirect('/teacher/dashboard')
        else:
            return redirect('/student/dashboard')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            flash('Login Successful!', 'success')
            if user['role'] == 'Admin':
                return redirect('/admin/dashboard')
            elif user['role'] == 'Teacher':
                return redirect('/teacher/dashboard')
            else:
                return redirect('/student/dashboard')
        else:
            flash('Invalid Username/Email or Password!', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'Student')
        
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                         (username, email, hashed_password, role))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash('Username or Email already exists!', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect('/login')

# ------------------------------------
# ADMIN ROUTES
# ------------------------------------
@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'Admin':
        return redirect('/login')
    
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    quizzes = conn.execute('SELECT * FROM quizzes').fetchall()
    conn.close()
    return render_template('admin_dashboard.html', users=users, quizzes=quizzes)

@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if session.get('role') != 'Admin':
        return redirect('/login')
        
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']
    
    hashed_password = generate_password_hash(password)
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                     (username, email, hashed_password, role))
        conn.commit()
        flash('User added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Username or Email already exists!', 'danger')
    finally:
        conn.close()
        
    return redirect('/admin/dashboard')

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if session.get('role') != 'Admin':
        return redirect('/login')
        
    conn = get_db_connection()
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        role = request.form['role']
        
        conn.execute('UPDATE users SET username = ?, email = ?, role = ? WHERE id = ?',
                     (username, email, role, user_id))
        conn.commit()
        conn.close()
        flash('User updated successfully!', 'success')
        return redirect('/admin/dashboard')
        
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'Admin':
        return redirect('/login')
        
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted successfully!', 'info')
    return redirect('/admin/dashboard')

# ------------------------------------
# TEACHER ROUTES
# ------------------------------------
@app.route('/teacher/dashboard')
def teacher_dashboard():
    if session.get('role') != 'Teacher':
        return redirect('/login')
    
    conn = get_db_connection()
    quizzes = conn.execute('SELECT * FROM quizzes WHERE created_by = ?', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('teacher_dashboard.html', quizzes=quizzes)

@app.route('/create_quiz', methods=['GET', 'POST'])
def create_quiz():
    if session.get('role') not in ['Teacher', 'Admin']:
        return redirect('/login')
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        subject = request.form.get('subject')
        duration = request.form.get('duration')
        pass_percentage = request.form.get('pass_percentage')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO quizzes (title, description, subject, duration, pass_percentage, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, description, subject, duration, pass_percentage, session['user_id']))
        quiz_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return redirect(f'/add_questions/{quiz_id}')
        
    return render_template('create_quiz.html')

@app.route('/add_questions/<int:quiz_id>', methods=['GET', 'POST'])
def add_questions(quiz_id):
    if session.get('role') not in ['Teacher', 'Admin']:
        return redirect('/login')
        
    conn = get_db_connection()
    if request.method == 'POST':
        question_text = request.form['question_text']
        option_a = request.form['option_a']
        option_b = request.form['option_b']
        option_c = request.form['option_c']
        option_d = request.form['option_d']
        correct_option = request.form['correct_option']
        
        conn.execute('''
            INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option))
        conn.commit()
        flash('Question added successfully!', 'success')
        
    questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    conn.close()
    return render_template('add_questions.html', quiz=quiz, questions=questions)

# ------------------------------------
# STUDENT ROUTES
# ------------------------------------
# --- STUDENT DASHBOARD ---
from io import BytesIO
from flask import send_file, render_template, session, redirect, flash

# --- STUDENT DASHBOARD ROUTE ---
@app.route('/student/dashboard')
def student_dashboard():
    if session.get('role') != 'Student':
        return redirect('/login')
        
    conn = get_db_connection()
    
    # 1. Quizzes List (with Teacher Name)
    quizzes = conn.execute('''
        SELECT q.*, u.username AS teacher_name 
        FROM quizzes q
        LEFT JOIN users u ON q.created_by = u.id
    ''').fetchall()
    
    # 2. Results History (with Quiz Title, Subject & Date)
    results = conn.execute('''
        SELECT r.*, q.title AS quiz_title, q.subject
        FROM results r
        JOIN quizzes q ON r.quiz_id = q.id
        WHERE r.student_id = ?
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    return render_template('student_dashboard.html', quizzes=quizzes, results=results)


@app.route('/download_certificate/<int:result_id>')
def download_certificate(result_id):
    if 'user_id' not in session:
        return redirect('/login')
        
    conn = get_db_connection()
    result = conn.execute('''
        SELECT r.*, q.title AS quiz_title, q.subject, u.username 
        FROM results r
        JOIN quizzes q ON r.quiz_id = q.id
        JOIN users u ON r.student_id = u.id
        WHERE r.id = ?
    ''', (result_id,)).fetchone()
    conn.close()

    if not result:
        flash('Result record not found!', 'danger')
        return redirect('/student/dashboard')

    # आता क्लासिक HTML सर्टिफिकेट पेज ओपन होईल
    return render_template('certificate.html', result=result)

@app.route('/take_quiz/<int:quiz_id>')
def take_quiz(quiz_id):
    if session.get('role') != 'Student':
        return redirect('/login')
        
    conn = get_db_connection()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    conn.close()
    
    return render_template('take_quiz.html', quiz=quiz, questions=questions)

from datetime import datetime

@app.route('/submit_quiz/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect('/login')
        
    conn = get_db_connection()
    questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    
    score = 0
    total_questions = len(questions)
    
    # मार्क्स मोजण्यासाठी लॉजिक
    for q in questions:
        selected_option = request.form.get(f"question_{q['id']}")
        if selected_option and str(selected_option).strip() == str(q['correct_option']).strip():
            score += 1
            
    # टक्केवारी आणि पास/फेअल स्टेटस
    percentage = round((score / total_questions) * 100, 2) if total_questions > 0 else 0
    pass_mark = quiz['pass_percentage'] if quiz and quiz['pass_percentage'] else 50
    status = 'Passed' if percentage >= pass_mark else 'Failed'
    
    # आजची तारीख आणि वेळ
    today_date = datetime.now().strftime('%d-%m-%Y %I:%M %p')
    
    # निकाल डेटाबेसमध्ये सेव्ह करा
    conn.execute('''
        INSERT INTO results (student_id, quiz_id, score, total_questions, percentage, status, date_taken)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], quiz_id, score, total_questions, percentage, status, today_date))
    
    conn.commit()
    conn.close()
    
    flash(f'Quiz Submitted! Score: {score}/{total_questions} ({percentage}%) - Status: {status}', 'success')
    return redirect('/student/dashboard')

if __name__ == '__main__':
    app.run(debug=True)