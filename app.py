import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "app_key"

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://db_username:password@localhost/db_name'#replace with your own credentials.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True

# File upload folder
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
 
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")


# User model
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# Route: Root -> Login Redirect
@app.route('/')
def home():
    return redirect('/login')

# Route: Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        try:
            new_user = User(username=username, email=email, password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            flash('Signup successful! Please log in.', 'success')
            return redirect('/login')
        except Exception as e:
            flash('Error: Username or email already exists.', 'danger')
            print(e)

    return render_template('signup.html')

# Route: Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect('/dashboard')

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')

# Route: Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect('/login')

# Route: Dashboard
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    summary, stats, graph = None, None, None
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            summary, stats = generate_summary(filepath)
            graph = generate_graph(filepath)
        else:
            flash('Please upload a valid CSV file.', 'danger')

    return render_template('dashboard.html', summary=summary, stats=stats, graph=graph)

# Route: Financial Health Score
@app.route('/health', methods=['GET', 'POST'])
def health():
    health_score, advice, graph = None, None, None
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            health_score, advice, graph = generate_health_score_and_advice(filepath)
        else:
            flash('Please upload a valid CSV file.', 'danger')

    return render_template('health_score.html', health_score=health_score, advice=advice, graph=graph)


# Function: Generate Context from CSV
def generate_context(filepath):
    df = pd.read_csv(filepath)
    total_expenses = df['expenses'].sum()
    total_income = df['income'].sum()
    highest_expense = df.loc[df['expenses'].idxmax()]
    common_expenses = df['expenses description'].value_counts().head(3).index.tolist()

    context = f"""
    Here is a summary of the financial situation:
    - Total Expenses: {total_expenses}
    - Total Income: {total_income}
    - Highest Expense: {highest_expense['expenses description']} costing {highest_expense['expenses']}
    - Common Expense Categories: {', '.join(common_expenses)}
    """
    return context
# Initialize Gemini API client
def analyze_with_gemini(context):
    api_key = os.getenv("GOOGLE_API_KEY")  # Ensure your API key is correctly set

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": f"Provide financial advice based on the following data: {context}"
            }]
        }]
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    # Check if the request was successful
    if response.status_code == 200:
        result = response.json()
        
        # Extract the generated text from the API response
        advice_text = result['candidates'][0]['content']['parts'][0]['text']
        
        # Return the advice text
        return advice_text
    else:
        return f"Error: {response.status_code} - {response.text}"


# Function: Generate Advice Route
@app.route('/ask', methods=['GET', 'POST'])
def generate_advice():
    advice = None
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Generate context based on the CSV data
            context = generate_context(filepath)

            # Use Gemini AI to analyze and generate advice
            advice = analyze_with_gemini(context)
        else:
            flash('Please upload a valid CSV file.', 'danger')

    return render_template('ask.html', advice=advice)



# Function: Generate Summary
def generate_summary(filepath):
    df = pd.read_csv(filepath)
    total_expenses = df['expenses'].sum()
    total_income = df['income'].sum()
    avg_expense = df['expenses'].mean()
    avg_income = df['income'].mean()

    summary = {
        "Total Expenses": f"${total_expenses:.2f}",
        "Total Income": f"${total_income:.2f}",
        "Average Expense": f"${avg_expense:.2f}",
        "Average Income": f"${avg_income:.2f}"
    }

    stats = df.describe(include='all').to_dict()
    return summary, stats

# Function: Generate Graph
def generate_graph(filepath):
    df = pd.read_csv(filepath)
    plt.figure(figsize=(10, 6))
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date', 'expenses', 'income'])
    df.sort_values('date', inplace=True)

    plt.plot(df['date'], df['expenses'], label='Expenses', color='red')
    plt.plot(df['date'], df['income'], label='Income', color='green')
    plt.xlabel('Date')
    plt.ylabel('Amount')
    plt.title('Expenses vs Income Over Time')
    plt.legend()
    plt.grid()

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    graph = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()
    return graph

# Function: Generate Health Score and Advice
def generate_health_score_and_advice(filepath):
    df = pd.read_csv(filepath)
    total_expenses = df['expenses'].sum()
    total_income = df['income'].sum()

    health_score = (total_income - total_expenses) / total_income * 100 if total_income else 0
    graph = generate_donut_chart(health_score)

    if health_score < 40:
        advice = ["Cut down high expenses.", "Look for ways to increase income.", "Track spending more closely."]
    elif 40 <= health_score <= 75:
        advice = ["Focus on income growth.", "Review utility costs.", "Plan savings for investment."]
    else:
        advice = ["Great job maintaining finances!", "Consider increasing savings."]

    return health_score, advice, graph

# Function: Generate Donut Chart
def generate_donut_chart(health_score):
    sizes = [health_score, 100 - health_score]
    colors = ['#0b8a2b', '#d3d3d3']
    plt.figure(figsize=(6, 6))
    plt.pie(sizes, labels=[f'{health_score:.1f}%', ''], startangle=90, counterclock=False,
            wedgeprops=dict(width=0.3), colors=colors)
    plt.title("Financial Health Score")
    
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    chart = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()
    return chart

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
