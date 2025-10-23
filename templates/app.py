import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
from datetime import date
from dateutil.relativedelta import relativedelta

app = Flask(__name__)

DATA_FILE = 'tasks.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            loaded = json.load(f)
            # Handle old list format: Upgrade to dict
            if isinstance(loaded, list):
                tasks = loaded
                for task in tasks:
                    if isinstance(task, str):
                        task = {'text': task, 'done': False, 'due': None, 'priority': 'low', 'category': 'Personal'}
                    elif 'due' not in task:
                        task['due'] = None
                    if 'priority' not in task:
                        task['priority'] = 'low'
                    if 'category' not in task:
                        task['category'] = 'Personal'
                loaded = {'tasks': tasks}
            else:
                tasks = loaded.get('tasks', [])
                for task in tasks:
                    if isinstance(task, str):
                        task = {'text': task, 'done': False, 'due': None, 'priority': 'low', 'category': 'Personal'}
                    elif 'due' not in task:
                        task['due'] = None
                    if 'priority' not in task:
                        task['priority'] = 'low'
                    if 'category' not in task:
                        task['category'] = 'Personal'
                loaded['tasks'] = tasks
           
            # Gamify defaults
            loaded['streak'] = loaded.get('streak', 0)
            loaded['last_completed'] = loaded.get('last_completed', None)
            loaded['daily_goal'] = loaded.get('daily_goal', {'target': 2, 'completed': 0, 'active': True})
            loaded['xp'] = loaded.get('xp', 0)
            loaded['level'] = loaded.get('level', 1)
            return loaded
    return {'tasks': [], 'streak': 0, 'last_completed': None, 'daily_goal': {'target': 2, 'completed': 0, 'active': True}, 'xp': 0, 'level': 1}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

data = load_data()
todos = data['tasks']

def update_streak():
    today = date.today().isoformat()
    if data['last_completed'] == today:
        return
    completed_today = sum(1 for t in todos if t['done'] and t.get('completed_date') == today)
    if completed_today > 0:
        if data['last_completed']:
            last_date = date.fromisoformat(data['last_completed'])
            if date.today() == last_date + relativedelta(days=1):
                data['streak'] += 1
            else:
                data['streak'] = 1
        else:
            data['streak'] = 1
        data['last_completed'] = today
        # Daily goal progress
        data['daily_goal']['completed'] += completed_today
        if data['daily_goal']['completed'] >= data['daily_goal']['target']:
            data['streak'] += 1  # Bonus!
            data['daily_goal']['active'] = False  # Reset tomorrow
    else:
        data['streak'] = 0

def add_xp(amount):
    data['xp'] += amount
    new_level = data['xp'] // 100 + 1
    if new_level > data['level']:
        data['level'] = new_level

def freeze_streak():
    data['streak_freeze'] = data.get('streak_freeze', 0) + 1
    if data['streak_freeze'] > 1:
        return False
    return True

@app.route('/', methods=['GET'])
def index():
    edit_index = request.args.get('edit', type=int, default=-1)
    editing = edit_index >= 0
   
    # Reload data to fix display issue
    global data, todos
    data = load_data()
    todos = data['tasks']
   
    sort_by = request.args.get('sort', 'all')
    filter_category = request.args.get('filter_category', 'all')
    search = request.args.get('search', '')
   
    # Filter
    filtered_todos = [t for t in todos if (filter_category == 'all' or t.get('category') == filter_category) and search.lower() in t['text'].lower()]
   
    # Sort
    if sort_by == 'priority':
        filtered_todos.sort(key=lambda t: {'high': 0, 'med': 1, 'low': 2}[t.get('priority', 'low')])
    elif sort_by == 'due':
        filtered_todos.sort(key=lambda t: t.get('due') or '9999-12-31')
   
    # Overdue
    today = date.today().isoformat()
    for task in filtered_todos:
        task['is_overdue'] = task.get('due') and task['due'] < today and not task['done']
        if task['done'] and not task.get('completed_date'):
            task['completed_date'] = today
   
    # Stats
    total = len(filtered_todos)
    done_count = sum(1 for t in filtered_todos if t['done'])
    overdue_count = sum(1 for t in filtered_todos if t.get('is_overdue'))
    progress_pct = (done_count / total * 100) if total > 0 else 0
   
    save_data(data)
    return render_template('index.html', todos=filtered_todos, editing=editing, edit_index=edit_index, total=total, done_count=done_count, overdue_count=overdue_count, progress_pct=progress_pct, streak=data['streak'], daily_goal=data['daily_goal'], xp=data['xp'], level=data['level'])

@app.route('/add', methods=['POST'])
def add_task():
    task_text = request.form['task']
    due_date = request.form.get('due') or None
    priority = request.form.get('priority', 'low')
    category = request.form.get('category', 'Personal')
    todos.append({'text': task_text, 'done': False, 'due': due_date, 'priority': priority, 'category': category})
    save_data(data)
    return redirect(url_for('index'))

@app.route('/toggle/<int:index>', methods=['POST'])
def toggle_task(index):
    if 0 <= index < len(todos):
        todos[index]['done'] = not todos[index]['done']
        if todos[index]['done']:
            todos[index]['completed_date'] = date.today().isoformat()
            update_streak()
            add_xp(10)
    save_data(data)
    return redirect(url_for('index'))

@app.route('/edit/<int:index>', methods=['GET', 'POST'])
def edit_task(index):
    if 0 <= index < len(todos):
        if request.method == 'POST':
            todos[index]['text'] = request.form['task']
            todos[index]['due'] = request.form.get('due') or None
            todos[index]['priority'] = request.form.get('priority', 'low')
            todos[index]['category'] = request.form.get('category', 'Personal')
            save_data(data)
            return redirect(url_for('index'))
        else:  # GET method
            return redirect(url_for('index', edit=index))
    return redirect(url_for('index'))

@app.route('/clear', methods=['POST'])
def clear_all():
    global todos
    todos = []  # Clear the list
    data['tasks'] = todos  # Sync with data dict
    save_data(data)  # Save the cleared state
    return redirect(url_for('index'))

@app.route('/freeze', methods=['POST'])
def freeze():
    if freeze_streak():
        save_data(data)
        return jsonify({'success': True, 'message': 'Streak frozen! One free day.'})
    return jsonify({'success': False, 'message': 'No freezes left—keep the flame alive!'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

