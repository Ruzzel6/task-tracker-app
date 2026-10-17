import os
import logging
import psycopg
from psycopg.rows import dict_row
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
logging.basicConfig(level=logging.INFO)

def connect():
    return psycopg.connect(host=os.getenv('PGHOST', 'db'),
        port=os.getenv('PGPORT', '5432'), dbname=os.getenv('PGDATABASE', 'tasks'),
        user=os.getenv('PGUSER', 'tasks'), password=os.environ['PGPASSWORD'],
        connect_timeout=3, row_factory=dict_row)

@app.cli.command('init-db')
def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            completed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    print('Schema ready')

@app.errorhandler(psycopg.Error)
def database_error(error):
    app.logger.exception('Database operation failed')
    return jsonify(error='Database temporarily unavailable'), 503

@app.get('/')
def home():
    return render_template('index.html')

@app.get('/health/live')
def live():
    return jsonify(status='ok')

@app.get('/health/ready')
def ready():
    with connect() as db:
        db.execute('SELECT id FROM tasks LIMIT 1')
    return jsonify(status='ready')

@app.get('/api/tasks')
def list_tasks():
    with connect() as db:
        rows = db.execute('SELECT * FROM tasks ORDER BY id DESC LIMIT 500').fetchall()
    return jsonify(rows)

@app.post('/api/tasks')
def create_task():
    data = request.get_json(silent=True)
    title = data.get('title') if isinstance(data, dict) else None
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
        return jsonify(error='Title must contain 1–200 characters'), 400
    with connect() as db:
        row = db.execute('INSERT INTO tasks (title) VALUES (%s) RETURNING *',
                         (title.strip(),)).fetchone()
    return jsonify(row), 201

@app.patch('/api/tasks/<int:task_id>')
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or type(data.get('completed')) is not bool:
        return jsonify(error='completed must be a boolean'), 400
    with connect() as db:
        row = db.execute('UPDATE tasks SET completed=%s WHERE id=%s RETURNING *',
                         (data['completed'], task_id)).fetchone()
    return (jsonify(row), 200) if row else (jsonify(error='Task not found'), 404)

@app.delete('/api/tasks/<int:task_id>')
def delete_task(task_id):
    with connect() as db:
        row = db.execute('DELETE FROM tasks WHERE id=%s RETURNING id', (task_id,)).fetchone()
    return ('', 204) if row else (jsonify(error='Task not found'), 404)
