# Note: This code requires Flask and Flask-SQLAlchemy to be installed in your environment.
# You can install them with: pip install flask flask-sqlalchemy
# Run this script with Python 3.12 (as 3.13.12 might be a typo; Python versions are like 3.12.3).
# Save this as app.py and run: python app.py
# Access the site at http://127.0.0.1:5000/
# For production, use a proper WSGI server like Gunicorn.

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this to a secure random key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    quote_request = db.Column(db.Boolean, default=False)

# Create DB if not exists
with app.app_context():
    db.create_all()
    # Add default admin if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('adminpass'), is_admin=True)
        db.session.add(admin)
        db.session.commit()

# Helper to check if user is logged in and admin
def is_admin():
    return session.get('user_id') and User.query.get(session['user_id']).is_admin

# Common template context for hero logo (assume you have a logo.jpg in static folder)
# Create folders: templates/ and static/
# In templates, create base.html with hero logo header

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/fields')
def fields():
    return render_template('fields.html')

@app.route('/cases')
def cases():
    return render_template('cases.html')

@app.route('/inquiries')
def inquiries():
    if not session.get('user_id'):
        flash('Please login to view inquiries.')
        return redirect(url_for('login'))
    inquiries = Inquiry.query.all()
    return render_template('inquiries.html', inquiries=inquiries)

@app.route('/quote', methods=['GET', 'POST'])
def quote():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        inquiry = Inquiry(name=name, email=email, message=message, quote_request=True)
        db.session.add(inquiry)
        db.session.commit()
        flash('Quote request submitted successfully!')
        return redirect(url_for('home'))
    return render_template('quote.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            flash('Login successful!')
            return redirect(url_for('home'))
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out.')
    return redirect(url_for('home'))

@app.route('/admin')
def admin():
    if not is_admin():
        flash('Access denied. Admins only.')
        return redirect(url_for('login'))
    users = User.query.all()
    inquiries = Inquiry.query.all()
    return render_template('admin.html', users=users, inquiries=inquiries)

@app.route('/admin/delete_inquiry/<int:id>')
def delete_inquiry(id):
    if not is_admin():
        return redirect(url_for('login'))
    inquiry = Inquiry.query.get_or_404(id)
    db.session.delete(inquiry)
    db.session.commit()
    flash('Inquiry deleted.')
    return redirect(url_for('admin'))

@app.route('/admin/delete_user/<int:id>')
def delete_user(id):
    if not is_admin():
        return redirect(url_for('login'))
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted.')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)