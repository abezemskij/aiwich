from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import re
import mysql.connector
from functools import wraps

app = Flask(__name__)
app.secret_key = "aiwich-classroom-demo-key"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "phi3:mini"

# ---------------------------------------------------------------------------
# Demo accounts — intentionally simple and visible to students (classroom use)
# NOTE: these give a role for display purposes; the app does NOT enforce
# role-based access on the SQL the LLM generates. That gap is the lesson.
# ---------------------------------------------------------------------------
DEMO_USERS = {
    'alice': {'password': 'student123', 'name': 'Alice Johnson', 'role': 'Student', 'student_id': 'S1001'},
    'ben':   {'password': 'student123', 'name': 'Ben Carter',    'role': 'Student', 'student_id': 'S1002'},
    'prof':  {'password': 'lecturer123','name': 'Prof. Turing',  'role': 'Lecturer (COMP1671)', 'student_id': None},
}

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'database': 'students',
    'user': 'university',
    'password': 'university',
}

DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant for University of AI-Wich.

## MODE 1 — General University Questions
Answer questions about the university in a friendly, concise way (under 50 words).
Topics you can help with:
- Admissions and enrolment procedures
- Courses, programmes, and timetables
- Campus facilities, locations, and opening hours
- Library services and academic resources
- University AI initiatives and research
- Events, deadlines, and student support

## MODE 2 — Student Record Queries (SQL)
If the user asks about or wants to modify student data, respond ONLY with a SQL query using this exact format:

*** [SQL statement];

Database schema:
  Database : students
  Table    : student_info
  Columns  : student_id, student_name, student_course, student_grade

### SELECT — reading student data
Use when a user asks about a grade, result, or enrolment for a specific student and course.
Always select only the relevant column(s) and filter by both name and course:

*** SELECT student_grade FROM student_info WHERE student_name = '[name]' AND student_course = '[course_code]';

### UPDATE — changing a grade
Use when a lecturer asks to update or change a grade for a specific student and course:

*** UPDATE student_info SET student_grade = '[new_grade]' WHERE student_name = '[name]' AND student_course = '[course_code]';

### INSERT — adding a new student record
Use when a lecturer asks to add or enrol a new student:

*** INSERT INTO student_info (student_id, student_name, student_course, student_grade) VALUES ('[id]', '[name]', '[course_code]', '[grade]');

### SQL rules
- CRITICAL: Output ONLY the *** prefix followed by the SQL statement — no explanation, no extra text
- Always filter by both student_name and student_course unless the user explicitly asks for all records for a student
- If any required value (name, course, grade) is missing from the request, ask for it before generating the query
- Use exact values provided by the user — do not invent or assume names, course codes, or grades

## General Rules
- Be friendly and professional at all times
- Do not fabricate specific policies, dates, or personal data
- If a question falls outside university topics, politely say so
"""

system_prompt = DEFAULT_SYSTEM_PROMPT


def get_current_user():
    """Return the logged-in user from the session, if any."""
    username = session.get('username')
    if username and username in DEMO_USERS:
        u = DEMO_USERS[username]
        return {'username': username, 'name': u['name'], 'role': u['role'], 'student_id': u['student_id']}
    return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Not logged in.'}), 401
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = DEMO_USERS.get(username)
        if user and user['password'] == password:
            session['username'] = username
            target = request.args.get('next') or '/'
            if not target.startswith('/'):
                target = '/'
            return redirect(target)
        error = "Invalid username or password."
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


def run_sql(sql):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        verb = sql.strip().split()[0].upper()
        if verb == 'SELECT':
            rows = cursor.fetchall()
            return 'select', rows
        else:
            conn.commit()
            return 'modify', cursor.rowcount
    finally:
        conn.close()


def format_select_results(rows):
    if not rows:
        return "No records were found matching your query."
    lines = []
    for row in rows:
        lines.append('  |  '.join(f"{k}: {v}" for k, v in row.items()))
    return "Here is the information from your student record:\n" + '\n'.join(lines)


@app.route('/')
@login_required
def home():
    return render_template('index.html', user=get_current_user())


@app.route('/ai-tuning')
@login_required
def ai_tuning():
    return render_template('ai_tuning.html', prompt=system_prompt, default_prompt=DEFAULT_SYSTEM_PROMPT, user=get_current_user())


@app.route('/api/system-prompt', methods=['GET'])
def get_system_prompt():
    return jsonify({'prompt': system_prompt})


@app.route('/api/system-prompt', methods=['POST'])
def set_system_prompt():
    global system_prompt
    data = request.get_json()
    new_prompt = data.get('prompt', '').strip()
    if not new_prompt:
        return jsonify({'error': 'Prompt cannot be empty.'}), 400
    system_prompt = new_prompt
    return jsonify({'success': True, 'prompt': system_prompt})


@app.route('/api/system-prompt/reset', methods=['POST'])
def reset_system_prompt():
    global system_prompt
    system_prompt = DEFAULT_SYSTEM_PROMPT
    return jsonify({'success': True, 'prompt': system_prompt})


@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    user_message = data.get('message', '')

    # Tell the model who is logged in so "my grade" questions work naturally.
    # NOTE (teaching point): this is information only — the app still executes
    # whatever SQL the model generates, with no role or ownership checks.
    sys_content = system_prompt
    u = get_current_user()
    if u:
        id_part = f"; student ID: {u['student_id']}" if u['student_id'] else ""
        sys_content += f"\n\n## Current Session\nThe visitor is logged in as {u['name']} (role: {u['role']}{id_part}).\nTreat questions about \"my\" records as referring to this account."

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": sys_content},
            {"role": "user",   "content": user_message}
        ],
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        reply = response.json()["message"]["content"]

        # Extract SQL if LLM produced a *** query, ignoring any hallucinated text around it
        sql_match = re.search(
            r'\*\*\*\s*((?:SELECT|INSERT|UPDATE|DELETE)\b.*?;)',
            reply,
            re.IGNORECASE | re.DOTALL
        )

        if sql_match:
            sql = sql_match.group(1).strip()
            try:
                kind, result = run_sql(sql)
                if kind == 'select':
                    reply = format_select_results(result)
                else:
                    print(repr(reply))
                    reply = "Your request was completed successfully."
            except mysql.connector.Error as db_err:
                reply = "There was an issue accessing the student database. Please try again or contact support."

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"Error connecting to Ollama: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
