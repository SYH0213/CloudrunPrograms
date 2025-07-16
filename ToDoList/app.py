from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'tasks.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        conn = get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                completed BOOLEAN NOT NULL DEFAULT 0,
                priority TEXT NOT NULL DEFAULT '보통' -- priority 컬럼 추가
            );
        """)
        conn.commit()
        conn.close()

@app.route('/')
def index():
    conn = get_db_connection()
    filter_by = request.args.get('filter', 'all') # 기본값은 'all'

    if filter_by == 'active':
        tasks = conn.execute('SELECT * FROM tasks WHERE completed = 0').fetchall()
    elif filter_by == 'completed':
        tasks = conn.execute('SELECT * FROM tasks WHERE completed = 1').fetchall()
    else: # 'all' 또는 유효하지 않은 필터
        tasks = conn.execute('SELECT * FROM tasks').fetchall()
    
    conn.close()
    return render_template('index.html', tasks=tasks, current_filter=filter_by)

@app.route('/add', methods=['POST'])
def add_task():
    if request.method == 'POST':
        task_content = request.form['content']
        task_priority = request.form.get('priority', '보통') # priority 값 추가
        if task_content:
            conn = get_db_connection() # 연결을 함수 시작 부분에서 한 번만 엽니다。
            existing_task = conn.execute('SELECT * FROM tasks WHERE content = ?', (task_content,)).fetchone()
            if existing_task:
                flash('중복된 내용의 할 일은 추가할 수 없습니다.')
                tasks = conn.execute('SELECT * FROM tasks').fetchall()
                conn.close() # 에러 발생 시에도 연결을 닫고 렌더링
                return render_template('index.html', tasks=tasks, current_filter='all')
            else:
                conn.execute('INSERT INTO tasks (content, priority) VALUES (?, ?)', (task_content, task_priority))
                conn.commit()
        conn.close() # 모든 경우에 함수 끝에서 연결을 닫습니다.
    return redirect(url_for('index'))

@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if task:
        new_status = 1 if not task['completed'] else 0
        conn.execute('UPDATE tasks SET completed = ? WHERE id = ?', (new_status, task_id))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()

    if request.method == 'POST':
        new_content = request.form['content']
        new_priority = request.form.get('priority', '보통') # priority 값 추가
        if new_content:
            # Check for duplicate content, excluding the current task being edited
            existing_task = conn.execute('SELECT * FROM tasks WHERE content = ? AND id != ?', (new_content, task_id)).fetchone()
            if existing_task:
                flash('중복된 내용으로 수정할 수 없습니다.')
                conn.close() # Close connection before rendering template
                return render_template('edit.html', task=task) # Stay on edit page
            else:
                conn.execute('UPDATE tasks SET content = ?, priority = ? WHERE id = ?', (new_content, new_priority, task_id)) # priority 업데이트
                conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    conn.close()
    return render_template('edit.html', task=task)

@app.route('/clear_completed', methods=['POST'])
def clear_completed():
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE completed = 1')
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

import os

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
