
from flask import Flask                    # Imports the Flask class from the flask package
# 'request' reads user input from the webpage (e.g., form data)
# 'redirect' sends the user to another page after form submission
# 'render_template' returns an HTML page with dynamic content             
from flask import request, redirect, render_template
import json                                # Load json module for read/writes to json file for persistant storage

import os                                  # Allows program interact with the operating system
from werkzeug.utils import secure_filename # Sanitize user-defined filenames (removes special characters)

from flask import send_file                # Allow Flask app to return downloadable files (like .ics)
from ics import Calendar, Event            # Components of .ics files
# Treat in-memory data (like strings or binary data) as a file objects to build .ics files without saving to disk
from io import BytesIO
from datetime import datetime, timedelta   # import functions for date and time calculations and changes


TASKS_FILE = 'tasks.json'                  # Define the name of the JSON file used for persistent task storage
app = Flask(__name__)                      # Create a Flask web server instance named 'app'

UPLOAD_FOLDER = 'static/uploads'           # Define folder to persistently store user selected images
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Create folder if missing 

# Define an empty global list variable (in memory) to hold tasks.
# All route handler and helper functions read/write this.
# Its contents are loaded from or saved to TASKS_FILE ('tasks.json') as needed.
tasks = []

##--HELPER FUNCTIONS--##
# A function to read contents of the json file 'tasks.json' 
def load_tasks():
    global tasks                         # Use tasks as a global list variable for list reassignment
    try:
        with open(TASKS_FILE, 'r') as f: # Open TASKS_FILE as variable f in read mode
            tasks.clear()                # Clear contents of tasks variable
            tasks.extend(json.load(f))   # Move contents of TASKS_FILE as f to tasks variable
    except FileNotFoundError:            # Exception handling if TASKS_FILE is missing
        tasks[:] = []                    # Create empty tasks variable for later transfer to 
                                         # TASKS_FILE created by def save_tasks(): function

# A function to save new entries to the json file 'tasks.json'
def save_tasks():
    with open(TASKS_FILE, 'w') as f:     # Open TASKS_FILE as variable f in write mode
        json.dump(tasks, f, indent=2)    # Move contents of tasks variable into TASKS_FILE


##--ROUTE HANDLER FUNCTIONS--##
# DASHBOARD TRIGGER BUTTON: 'SEARCH'
# HTML FORM: '<form action="/" method="get" ...'
# HTTP REQUEST METHOD: GET
# URL ACCEPTED/EXPECTED: '/' (http://127.0.0.1:5000/)
@app.route('/', methods=['GET'])
# A function to either DISPLAY ALL tasks or a USER SEARCH DEFINED task 
def home():
    # Use the Flask objects 'request' and 'args' with method 'get()' to retrieve the value from
    # the key (name="q"):value ("{query}") sent from the HTML form via the URL in lowercase.
    # Store the value in the variable query
    query = request.args.get('q', '').lower()
    # Create a new list "filtered_tasks" that includes only those tasks 
    # whose titles contain the user's search query (case-insensitive match)
    filtered_tasks = [task for task in tasks if query in task.get('title', '').lower()]
    # Sort and display "filtered _tasks" using task due dates
    # Exclude any tasks that don't have a due_date to ensure sort doesn't fail
    filtered_tasks = [task for task in filtered_tasks if 'due_date' in task]
    filtered_tasks.sort(key=lambda x: x['due_date'])
    # Render the home.html page, passing in the user's search query (query)
    # and the list of matching tasks (filtered_tasks) for display
    return render_template('home.html', tasks=filtered_tasks, query=query, task_to_edit=None)

# DASHBOARD TRIGGER BUTTON: 'EXPORT TASKS TO CALENDAR (.ICS)'
# HTML FORM: '<form action="/export_ics" method="get" ...'
# HTTP REQUEST METHOD: GET
# URL ACCEPTED/EXPECTED: '/export_ics' (http://127.0.0.1:5000/export_ics)
@app.route('/export_ics')
def export_ics():
    calendar = Calendar()                               # Create new empty calendar object.
    for task in tasks:                                  # Loop through all tasks, find only those  
        if task.get("due_date") and task.get("title"):  #   having both a due date and a title.
            event = Event()                             # Create new empty calendar event.
            event.name = task["title"]                  # Set event name to user defined title
            # Set event due date and due time to user defined values or default '00:00' for due time
            event.begin = f"{task['due_date']}T{task['due_time'] or '00:00'}" 
            # Adds a static description to each event for clarity in  calendar app
            event.description = "Exported from Task Tracker" 
            calendar.events.add(event)                  # Add new event to calendar
    ics_data = str(calendar)                            # Convert the Calendar object into a plain .ics text string
    ics_stream = BytesIO()                              # Create an in-memory (RAM based) file-like (ics stream) object using BytesIO
    ics_stream.write(ics_data.encode('utf-8'))          # # Write .ics data to memory as UTF-8 bytes
    # Move read/write pointer to the start of the ics stream so Flask can read it from the beginning
    ics_stream.seek(0)
    # Sends the in-memory file (ics_stream) to the user as a downloadable attachment 
    return send_file(
        ics_stream,
        as_attachment=True,
        download_name="tasks.ics",
        mimetype="text/calendar"
    )

# DASHBOARD TRIGGER BUTTON: 'ADD TASK'
# HTML FORM: '<form action="/add" method="POST" ...'
# HTTP REQUEST METHOD: POST
# URL ACCEPTED/EXPECTED: '/add' (http://127.0.0.1:5000/add)
@app.route('/add', methods=['POST'])
# Add new task(s) to the task list
def add_task():
    title = request.form['title']                     # Get task title from form
    due_date = request.form['due_date']               # Get due date from form
    due_time = request.form['due_time']               # Get due time from form
    repeat_daily = 'repeat_daily' in request.form     # Check if repeat daily is selected
    repeat_weekly = 'repeat_weekly' in request.form   # Check if repeat weekly is selected
    image_file = request.files.get('image')           # Get uploaded image file (if any)

    image_filename = ""
    if image_file and image_file.filename:            # If a file was uploaded
        filename = secure_filename(image_file.filename)                  # Sanitize filename
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename) # Create full path
        image_file.save(image_path)                   # Save image to disk
        image_filename = filename                     # Store filename for later use

    # Generate a unique ID for the new task
    new_id = max([task["id"] for task in tasks], default=0) + 1

    # Add the new task to the task list
    tasks.append({
        "id": new_id,
        "title": title,
        "due_date": due_date,
        "due_time": due_time,
        "image": image_filename,
        "done": False,
        "repeat": "daily" if repeat_daily else "weekly" if repeat_weekly else "none"
    })

    try:
        # Combine date and time into a datetime object
        base_dt = datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")

        if repeat_daily:
            for i in range(1, 6):  # Generate 5 daily tasks
                future_dt = base_dt + timedelta(days=i)
                new_id += 1
                tasks.append({
                    "id": new_id,
                    "title": f"{title} (Day {i+1})",
                    "due_date": future_dt.date().isoformat(),
                    "due_time": future_dt.time().strftime("%H:%M"),
                    "image": image_filename,
                    "done": False,
                    "repeat": "daily"
                })

        if repeat_weekly:
            for i in range(1, 5):  # Generate 4 weekly tasks
                future_dt = base_dt + timedelta(weeks=i)
                new_id += 1
                tasks.append({
                    "id": new_id,
                    "title": f"{title} (Week {i+1})",
                    "due_date": future_dt.date().isoformat(),
                    "due_time": future_dt.time().strftime("%H:%M"),
                    "image": image_filename,
                    "done": False,
                    "repeat": "weekly"
                })

    except ValueError:     # Catches a ValueError for empty or improper date format
        pass               # Skip recurrence if date/time is missing or invalid

    save_tasks()           # Save updated task list to file
    return redirect('/')   # Redirect to homepage

# DASHBOARD TRIGGER BUTTON: 'EDIT TASK'
# HTML FORM: N/A (uses a styled <a> link to avoid nested form violations)
# HTTP REQUEST METHOD: GET
# URL ACCEPTED/EXPECTED: '/edit/<task_id>' (e.g. http://127.0.0.1:5000/edit/X where X= task ID number)
@app.route('/edit/<int:task_id>', methods=['GET'])
# A function to load the task with matching ID and return home.html with that task preloaded in the edit form
def edit_task(task_id):
    for task in tasks:             # Loop through all the tasks in the tasks list
        if task["id"] == task_id:  # If the task with the matching ID is found,
            # render the home.html page, passing the variable "task_to_edit" corresponding
            # to the matching ID supplied as a parameter.
            return render_template(
                'home.html', 
                tasks=tasks, 
                query="", 
                task_to_edit=task  # send the task for pre-filling the form
            )
    return redirect('/')           # If task not found, redirect back to homepage

# DASHBOARD TRIGGER BUTTON: 'UPDATE TASK' 
# HTML FORM: '<form action="/update/{{ task_to_edit['id'] }}" method="POST" ...'
# HTTP REQUEST METHOD: POST
# URL ACCEPTED/EXPECTED: '/update/{{ task_to_edit['id'] }}' (http://127.0.0.1:5000/update/X where X= task ID number)
@app.route('/update/<int:task_id>', methods=['POST'])
# A function to update a task's title, due date, and due time in the tasks list
# This function receives input (task_id) indirectly from the edit_task() function through pre-filled home.html file
def update_task(task_id):
    new_title = request.form['title']                   # Get task title from form
    new_due_date = request.form['due_date']             # Get due date from form
    new_due_time = request.form['due_time']             # Get due time from form
    repeat_daily = 'repeat_daily' in request.form       # Check if repeat daily is selected
    repeat_weekly = 'repeat_weekly' in request.form     # Check if repeat weekly is selected
    image_file = request.files.get('image')             # Get uploaded image file (if any)

    for task in tasks:                      # Loop through all the tasks in the tasks list
        if task["id"] == task_id:           # If the task with the matching ID is found, then:
            task["title"] = new_title       # Update current task title to new task title
            task["due_date"] = new_due_date # Update current task due date to new task due date
            task["due_time"] = new_due_time # Update current task due time to new task due time
            task["repeat"] = "daily" if repeat_daily else "weekly" if repeat_weekly else "none"
            if image_file and image_file.filename:                               # If a file was uploaded
                filename = secure_filename(image_file.filename)                  # Sanitize filename
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename) # Create full path
                image_file.save(image_path) # Save image to disk
                task["image"] = filename    # overwrite or add the image key
            try:
                # Combine date and time into a datetime object
                base_dt = datetime.strptime(f"{new_due_date} {new_due_time}", "%Y-%m-%d %H:%M")
                # Find highest task ID number. If no tasks default to zero. 
                new_id = max([task["id"] for task in tasks], default=0)

                if repeat_daily:
                    for i in range(1, 6):  # Add 5 daily recurring tasks
                        future_dt = base_dt + timedelta(days=i)
                        new_id += 1
                        tasks.append({
                            "id": new_id,
                            "title": f"{new_title} (Day {i+1})",
                            "due_date": future_dt.date().isoformat(),
                            "due_time": future_dt.time().strftime("%H:%M"),
                            "image": task.get("image", ""),
                            "done": False,
                            "repeat": "daily"
                        })

                if repeat_weekly:
                    for i in range(1, 5):  # Add 4 weekly recurring tasks
                        future_dt = base_dt + timedelta(weeks=i)
                        new_id += 1
                        tasks.append({
                            "id": new_id,
                            "title": f"{new_title} (Week {i+1})",
                            "due_date": future_dt.date().isoformat(),
                            "due_time": future_dt.time().strftime("%H:%M"),
                            "image": task.get("image", ""),
                            "done": False,
                            "repeat": "weekly"
                        })
            except ValueError:
                pass
            save_tasks()                    # Save the updated task list to TASKS_FILE
            break                           # Exit loop since the task has been found and updated
    return redirect('/')                    # After task updated, redirect back to homepage


# DASHBOARD TRIGGER BUTTON: 'DELETE TASK', 'REMOVE TASK IMAGE', or 'TOGGLE COMPLETE/INCOMPLETE'
# HTML FORM: '<form action="/bulk_action" method="POST" id="bulkForm">'
# HTTP REQUEST METHOD: POST
# URL ACCEPTED/EXPECTED: '/bulk_action' (http://127.0.0.1:5000/bulk_action)
@app.route('/bulk_action', methods=['POST'])
def bulk_action():
    # Gets a list of task IDs checked under "DELETE TASK", "REMOVE TASK IMAGE", "TOGGLE COMPLETE/INCOMPLETE" columns
    delete_ids = request.form.getlist('delete_ids')             # IDs of tasks to be deleted
    remove_image_ids = request.form.getlist('remove_image_ids') # IDs of tasks to have image deleted
    toggle_ids = request.form.getlist('toggle_ids')             # IDs of tasks to have status changed
    action = request.form['action']
    # Loops through a copy of the task list to remove or modify tasks checked in columns above
    for task in tasks[:]:  
        task_id_str = str(task["id"])  # Converts each task’s numeric ID to a string for comparison with form values.
        # If "DELETE TASK" button pushed and task checked for deletion,
        if action == "DELETE TASK" and task_id_str in delete_ids:
            if task.get("image"):
                path = os.path.join(app.config['UPLOAD_FOLDER'], task["image"])
                if os.path.exists(path):
                    os.remove(path)         # Delete task's image file
            tasks.remove(task)              # Remove task from tasks list
        # If "REMOVE TASK IMAGE" button pushed and task checked for image deletion,
        elif action == "REMOVE TASK IMAGE" and task_id_str in remove_image_ids:
            if task.get("image"):
                path = os.path.join(app.config['UPLOAD_FOLDER'], task["image"])
                if os.path.exists(path):
                    os.remove(path)         # Delete task's image file
                task["image"] = ""          # Delete name of task's image 
        # If "TOGGLE COMPLETE/INCOMPLETE" button pushed and task checked for status change,
        elif action == "TOGGLE COMPLETE/INCOMPLETE" and task_id_str in toggle_ids:
            task["done"] = not task["done"]
    save_tasks()                            # Save the updated task list to TASKS_FILE
    return redirect('/')                    # After task updated, redirect back to homepage


# Run the app
if __name__ == '__main__':
    # load task data from the json file (tasks.json) into the global tasks list before the server starts.
    load_tasks()
    # Run the Flask application (app) on localhost (127.0.0.1), port 5000
    # Enable debug mode for auto reloads and detailed error messages 
    app.run(host="127.0.0.1", port=5000, debug=True)