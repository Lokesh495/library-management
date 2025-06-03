from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
import numpy as np
import cv2
import base64
import io
from PIL import Image
import uuid
import os
from datetime import date, datetime, timedelta

app = Flask(__name__)

# Connect to database helper
def get_db():
    conn = sqlite3.connect("database/library.db")
    conn.row_factory = sqlite3.Row  # Dictionary-like cursor
    return conn

def get_issued_books_from_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ib.id, ib.issue_date, ib.return_date, ib.is_returned,
        b.title, s.name
        FROM issued_books ib
        LEFT JOIN books b ON CAST(ib.book_id AS INTEGER) = CAST(b.book_id AS INTEGER)
        LEFT JOIN students s ON CAST(ib.user_id AS INTEGER) =CAST(s.student_id AS INTEGER)
    """)
    rows = cursor.fetchall()
    return rows
# ====================== ROUTES =======================

# Render login page
@app.route("/")
def login_page():
    return render_template("login.html")

# Render admin dashboard
@app.route("/admin/dashboard")
def admin_page():
    return render_template("admin_dashboard.html")

# Render student dashboard
@app.route("/student/dashboard")
def student_page():
    return render_template("student_dashboard.html")

# Login Logic
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user_type = data.get("user_type")

    conn = get_db()
    cursor = conn.cursor()

    if user_type == "admin":
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400

        cursor.execute("SELECT * FROM admin WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and user["password"] == password:
            cursor.close()
            conn.close()
            return jsonify({"redirect": "/admin/dashboard"})
        else:
            cursor.close()
            conn.close()
            return jsonify({"error": "Invalid username or password"}), 401

    elif user_type == "student":
        student_name = data.get("student_name")
        student_email = data.get("student_email")

        if not student_name or not student_email:
            return jsonify({"error": "Student name and email required"}), 400

        cursor.execute("SELECT * FROM students WHERE name = ? AND email = ?", (student_name, student_email))
        student = cursor.fetchone()

        if student:
            student_id = student['student_id']
            cursor.close()
            conn.close()
            return jsonify({"redirect": f"/student/dashboard/{student_id}"})
        else:
            cursor.close()
            conn.close()
            return jsonify({"error": "Invalid student name or email"}), 401

    else:
        cursor.close()
        conn.close()
        return jsonify({"error": "Invalid user type"}), 400


# ==================== API ENDPOINTS =====================

# Add a new student
@app.route("/api/add-student", methods=["POST"])
def add_student():
    name = request.form.get("name")
    email = request.form.get("email")
    image_file = request.files.get("image")

    if not all([name, email, image_file]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        image_data = image_file.read()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (name, email, image) VALUES (?, ?, ?)",
            (name, email, image_data)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Student added successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Student with this email already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add a new book
@app.route("/api/add-book", methods=["POST"])
def add_book():
    data = request.get_json()
    title = data.get("title")
    author = data.get("author")
    isbn = data.get("isbn")
    category = data.get("category", "")
    total_copies = data.get("total_copies")

    if not all([title, author, isbn, total_copies]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        total_copies = int(total_copies)
        if total_copies < 1:
            return jsonify({"error": "Total copies must be at least 1"}), 400
    except ValueError:
        return jsonify({"error": "Invalid value for total copies"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO books (title, author, isbn, category, total_copies, available_copies)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, author, isbn, category, total_copies, total_copies))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Book added successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Book with this ISBN already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/students")
def student_list():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, name, email FROM students")
        students = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("student_list.html", students=students)
    except Exception as e:
        return f"Error fetching student list: {e}", 500

@app.route("/students/update/<int:student_id>")
def update_student_form(student_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    cursor.close()
    conn.close()

    if student:
        return render_template("update_student.html", student=student)
    else:
        return "Student not found", 404

@app.route("/student/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("student_list"))

#===================BOOKS=======================
@app.route("/books")
def book_list():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books")
    books = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("book_list.html", books=books)

@app.route("/book/update/<int:book_id>", methods=["GET", "POST"])
def update_book_form(book_id):
    conn = get_db()
    cursor = conn.cursor()
    if request.method == "POST":
        # Handle update logic here (get form data, update DB)
        title = request.form.get("title")
        author = request.form.get("author")
        isbn = request.form.get("isbn")
        category = request.form.get("category")
        total_copies = request.form.get("total_copies")
        try:
            cursor.execute("""
                UPDATE books SET title=?, author=?, isbn=?, category=?, total_copies=?
                WHERE id=?
            """, (title, author, isbn, category, total_copies, book_id))
            conn.commit()
            return redirect(url_for("book_list"))
        except sqlite3.IntegrityError:
            return "ISBN already exists", 400
    else:
        cursor.execute("SELECT * FROM books WHERE book_id=?", (book_id,))
        book = cursor.fetchone()
        cursor.close()
        conn.close()
        if book is None:
            return "Book not found", 404
        return render_template("update_book.html", book=book)

@app.route("/book/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books WHERE book_id=?", (book_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("book_list"))


# Route to render issue requests page for admin dashboard
@app.route("/admin/issue-requests")
def show_issue_requests():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.request_id, r.request_date, r.status, r.pickup_time,
        s.name AS student_name, b.title AS book_title
        FROM issue_requests r
        JOIN students s ON r.student_id = s.student_id
        JOIN books b ON r.book_id = b.book_id
        ORDER BY r.request_date DESC
    """)
    requests = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("issue_requests.html", requests=requests)

@app.route("/admin/approve-request/<int:request_id>", methods=["POST"])
def approve_request(request_id):
    from datetime import datetime, timedelta
    pickup_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE issue_requests
            SET status = ?, pickup_time = ?
            WHERE request_id = ?
        """, ("Approved", pickup_time, request_id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": f"Request {request_id} approved with pickup time {pickup_time}."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/reject-request/<int:request_id>", methods=["POST"])
def reject_request(request_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE issue_requests
            SET status = ?, pickup_time = NULL
            WHERE request_id = ?
        """, ("Rejected", request_id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": f"Request {request_id} rejected."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/student/dashboard/<int:student_id>')
def student_dashboard(student_id):
    conn = get_db()
    cursor = conn.cursor()

    # Get all books and available copies
    cursor.execute("""
        SELECT book_id, title, available_copies
        FROM books
        ORDER BY title
    """)
    books = cursor.fetchall()

    # Get all issue requests by this student (book_id -> status)
    cursor.execute("""
        SELECT book_id, status
        FROM issue_requests
        WHERE student_id = ?
    """, (student_id,))
    requests = cursor.fetchall()

    # Map book_id to status for quick lookup
    req_status_map = {r['book_id']: r['status'] for r in requests}

    conn.close()
    return render_template('student_dashboard.html', books=books, req_status_map=req_status_map, student_id=student_id)


@app.route('/student/send-issue-request', methods=['POST'])
def send_issue_request():
    data = request.get_json()
    book_id = data.get('book_id')
    student_id = data.get('student_id')

    conn = get_db()
    cursor = conn.cursor()

    # Check if copies available
    cursor.execute("SELECT available_copies FROM books WHERE book_id = ?", (book_id,))
    book = cursor.fetchone()
    if not book or book['available_copies'] <= 0:
        conn.close()
        return jsonify({"success": False, "message": "No copies available for this book."})

    # Check if student already has a pending or approved request for this book
    cursor.execute("""
        SELECT status FROM issue_requests
        WHERE student_id = ? AND book_id = ? AND status IN ('Pending', 'Approved')
    """, (student_id, book_id))
    existing_request = cursor.fetchone()

    if existing_request:
        conn.close()
        return jsonify({"success": False, "message": f"You already have a {existing_request['status']} request for this book."})

    # Insert new request with status Pending
    cursor.execute("""
        INSERT INTO issue_requests (student_id, book_id, status)
        VALUES (?, ?, 'Pending')
    """, (student_id, book_id))
    conn.commit()
    conn.close()

@app.route('/admin/complete-request', methods=['POST'])
def complete_request():
    data = request.get_json()
    request_id = data.get('request_id')

    if not request_id:
        return jsonify({"success": False, "message": "Missing request ID"}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Fetch request info
        cursor.execute("""
            SELECT * FROM issue_requests WHERE request_id = ?
        """, (request_id,))
        request_info = cursor.fetchone()

        if not request_info:
            return jsonify({"success": False, "message": "Request not found"}), 404

        book_id = request_info['book_id']
        student_id = request_info['student_id']

        # Check available copies
        cursor.execute("""
            SELECT available_copies FROM books WHERE book_id = ?
        """, (book_id,))
        book = cursor.fetchone()

        if not book or book['available_copies'] <= 0:
            return jsonify({"success": False, "message": "No available copies"}), 400

        # Insert into issued_books
        cursor.execute("""
            INSERT INTO issued_books (request_id,user_id, book_id, issue_date)
            VALUES (?, ?, datetime('now'))
        """, (request_id,student_id, book_id))

        # Decrease book count
        cursor.execute("""
            UPDATE books SET available_copies = available_copies - 1
            WHERE book_id = ?
        """, (book_id,))

        # Remove from issue_requests
        cursor.execute("""
            DELETE FROM issue_requests WHERE request_id = ?
        """, (request_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Request completed successfully"})

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"success": False, "message": str(e)}), 500
    


@app.route('/admin/issued_books')
def show_issued_books():
    rows = get_issued_books_from_db()
    print("Raw rows from DB:", rows)

    books = []
    for row in rows:
        issue_id, issue_date_str, return_date_str, is_returned, book_title, student_name = row

        # Defensive check
        if not issue_id:
            print("⚠️ Warning: Found a row with NULL issue_id. Skipping.")
            continue

        # Parse issue_date
        try:
            issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d %H:%M:%S').date()
        except Exception as e:
            print(f"❌ Error parsing issue_date: {issue_date_str} → {e}")
            continue

        # Calculate due date
        due_date = issue_date + timedelta(days=7)

        # Determine if overdue
        is_overdue = (date.today() > due_date) and (not is_returned)

        # Calculate penalty
        penalty = 0
        if is_overdue:
            days_late = (date.today() - due_date).days
            penalty = days_late * 5

        books.append({
            'id': issue_id,
            'title': book_title,
            'user': student_name,
            'issue_date': issue_date.strftime('%Y-%m-%d'),
            'return_date': due_date.strftime('%Y-%m-%d'),
            'penalty': penalty,
            'is_returned': is_returned,
            'is_overdue': is_overdue,
        })

    print("Processed books:", books)
    return render_template('issued_books.html', books=books, current_date=date.today().strftime('%Y-%m-%d'))

@app.route('/admin/confirm_return/<int:book_id>', methods=['POST'])
def confirm_return(book_id):
    from datetime import date
    today = date.today()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE issued_books
        SET is_returned = 1, return_date = ?
        WHERE id = ?
    """, (today, book_id))

    # Increase available copies in books table
    cur.execute("""
        UPDATE books
        SET available_copies = available_copies + 1
        WHERE book_id = ?
    """, (book_id,))

    conn.commit()
    conn.close()
    return redirect(url_for('show_issued_books'))


# ==================== MAIN =====================
if __name__ == "__main__":
    app.run(debug=True)
