from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_session_management' # 실제 배포 시에는 더 복잡하고 안전한 키를 사용하세요.
DATABASE = 'tasks.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        conn = get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                nickname TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                completed BOOLEAN NOT NULL DEFAULT 0,
                priority TEXT NOT NULL DEFAULT '보통',
                start_date TEXT,
                end_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """)
        conn.commit()
        conn.close()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    filter_by = request.args.get('filter', 'all') # 기본값은 'all'

    user_id = session['user_id']
    user = conn.execute('SELECT nickname FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        session.pop('user_id', None)
        session.pop('username', None)
        flash('사용자 정보를 찾을 수 없습니다. 다시 로그인해주세요.')
        conn.close()
        return redirect(url_for('login'))

    if filter_by == 'active':
        tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND completed = 0', (user_id,)).fetchall()
    elif filter_by == 'completed':
        tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND completed = 1', (user_id,)).fetchall()
    else: # 'all' 또는 유효하지 않은 필터
        tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,)).fetchall()
    
    conn.close()
    return render_template('index.html', tasks=tasks, current_filter=filter_by, nickname=user['nickname'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('비밀번호와 비밀번호 확인이 일치하지 않습니다.')
            return render_template('register.html')

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (username, password_hash, nickname) VALUES (?, ?, ?)", (username, hashed_password, username))
            conn.commit()
            flash('회원가입이 완료되었습니다. 닉네임을 설정해주세요.')
            session['user_id'] = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()['id']
            session['username'] = username # 임시로 username을 세션에 저장
            return redirect(url_for('set_nickname'))
        except sqlite3.IntegrityError:
            flash('이미 존재하는 사용자 이름입니다.')
            return render_template('register.html')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/set_nickname', methods=['GET', 'POST'])
def set_nickname():
    if 'user_id' not in session:
        flash('먼저 로그인해주세요.')
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if request.method == 'POST':
        new_nickname = request.form['nickname']
        if new_nickname:
            conn.execute('UPDATE users SET nickname = ? WHERE id = ?', (new_nickname, session['user_id']))
            conn.commit()
            session['username'] = new_nickname # 세션의 username을 닉네임으로 업데이트
            flash('닉네임이 성공적으로 변경되었습니다.')
            conn.close()
            return redirect(url_for('index'))
        else:
            flash('닉네임을 입력해주세요.')

    conn.close()
    return render_template('set_nickname.html', current_nickname=user['nickname'] if user else '')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('로그인 성공!')
            return redirect(url_for('index'))
        else:
            flash('잘못된 사용자 이름 또는 비밀번호입니다.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('로그아웃되었습니다.')
    return redirect(url_for('login'))

@app.route('/create_task', methods=['GET', 'POST'])
def create_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        task_content = request.form['content']
        task_priority = request.form.get('priority', '보통')
        task_start_date = request.form.get('start_date')
        task_end_date = request.form.get('end_date')

        if task_content:
            conn = get_db_connection()
            existing_task = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND content = ?', (user_id, task_content,)).fetchone()
            if existing_task:
                flash('중복된 내용의 할 일은 추가할 수 없습니다.')
                conn.close()
                return render_template('create_task.html')
            else:
                conn.execute('INSERT INTO tasks (user_id, content, priority, start_date, end_date) VALUES (?, ?, ?, ?, ?)', (user_id, task_content, task_priority, task_start_date, task_end_date))
                conn.commit()
                flash('할 일이 성공적으로 추가되었습니다!')
        conn.close()
        return redirect(url_for('index'))
    
    return render_template('create_task.html')

@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id)).fetchone()
    if task:
        new_status = 1 if not task['completed'] else 0
        conn.execute('UPDATE tasks SET completed = ? WHERE id = ? AND user_id = ?', (new_status, task_id, user_id))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id)).fetchone()

    if not task:
        flash('해당 할 일을 찾을 수 없거나 권한이 없습니다.')
        conn.close()
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_content = request.form['content']
        new_priority = request.form.get('priority', '보통')
        new_start_date = request.form.get('start_date')
        new_end_date = request.form.get('end_date')

        if new_content:
            existing_task = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND content = ? AND id != ?', (user_id, new_content, task_id)).fetchone()
            if existing_task:
                flash('중복된 내용으로 수정할 수 없습니다.')
                conn.close()
                return render_template('edit.html', task=task)
            else:
                conn.execute('UPDATE tasks SET content = ?, priority = ?, start_date = ?, end_date = ? WHERE id = ? AND user_id = ?', (new_content, new_priority, new_start_date, new_end_date, task_id, user_id))
                conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    conn.close()
    return render_template('edit.html', task=task)

@app.route('/clear_completed', methods=['POST'])
def clear_completed():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE completed = 1 AND user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/calendar_events')
def calendar_events():
    if 'user_id' not in session:
        return jsonify([]) # 로그인되지 않은 경우 빈 배열 반환

    user_id = session['user_id']
    conn = get_db_connection()
    tasks = conn.execute('SELECT id, content, start_date, end_date FROM tasks WHERE user_id = ? AND start_date IS NOT NULL AND end_date IS NOT NULL', (user_id,)).fetchall()
    conn.close()
    events = []
    for task in tasks:
        events.append({
            'id': task['id'],
            'title': task['content'],
            'start': task['start_date'],
            'end': (datetime.strptime(task['end_date'], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        })
    return jsonify(events)

import os

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
