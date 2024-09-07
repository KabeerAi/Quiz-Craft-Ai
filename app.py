from flask import Flask, render_template, request, redirect, url_for, session
import google.generativeai as genai
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import base64
import json
import re

app = Flask(__name__)

load_dotenv()

secret_key = os.getenv('SECRET_KEY')  # Use a default for development if needed
if secret_key is None:
    raise ValueError("SECRET_KEY environment variable not set")

app.secret_key = secret_key
# Configure Google Generative AI
genai.configure(api_key='AIzaSyCWpBU8kC1kf9lslOl421x298R-aNZ0ueg')  # Replace with your actual API key
model = genai.GenerativeModel('gemini-1.5-flash')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_mcqs(image_path, num_mcqs):
    try:
        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()
        image_parts = [
            {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(image_data).decode('utf-8')
            }
        ]
        prompt = f"Generate {num_mcqs} multiple-choice questions based on this image. For each question, provide 4 options and indicate the correct answer. Format each question as a JSON object with keys 'question', 'options' (an array of 4 strings), and 'correct_answer' (the index of the correct option, 0-based). Please make sure that the answers you provide are correct."
        response = model.generate_content([prompt, image_parts[0]])
        
        # Extract JSON objects from the response
        json_objects = re.findall(r'\{[^{}]*\}', response.text)
        
        mcqs = []
        for json_str in json_objects:
            try:
                mcq = json.loads(json_str)
                if all(key in mcq for key in ['question', 'options', 'correct_answer']):
                    mcqs.append(mcq)
            except json.JSONDecodeError:
                continue
        
        return mcqs[:num_mcqs]  # Ensure we return only the requested number of MCQs
    except Exception as e:
        print(f"Error generating MCQs: {str(e)}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                num_mcqs = int(request.form['num_mcqs'])
                
                # Generate MCQs using Gemini
                mcqs = generate_mcqs(filepath, num_mcqs)
                
                if mcqs is None:
                    return redirect(url_for('error'))
                
                session['mcqs'] = mcqs
                return redirect(url_for('quiz'))
        except Exception as e:
            print(f"Error in index route: {str(e)}")
            return redirect(url_for('error'))
    return render_template('index.html')

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    try:
        mcqs = session.get('mcqs', [])
        if request.method == 'POST':
            user_answers = {}
            for i in range(len(mcqs)):
                user_answers[i] = int(request.form.get(f'q{i}'))
            session['user_answers'] = user_answers
            return redirect(url_for('result'))
        return render_template('quiz.html', mcqs=mcqs, enumerate=enumerate)
    except Exception as e:
        print(f"Error in quiz route: {str(e)}")
        return redirect(url_for('error'))

@app.route('/result')
def result():
    try:
        mcqs = session.get('mcqs', [])
        user_answers = session.get('user_answers', {})
        total_questions = len(mcqs)
        correct_answers = sum(1 for i, mcq in enumerate(mcqs) if user_answers.get(str(i)) == mcq['correct_answer'])
        wrong_answers = total_questions - correct_answers
        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        grade = calculate_grade(score)
        
        return render_template('result.html', total_questions=total_questions, correct_answers=correct_answers,
                               wrong_answers=wrong_answers, score=score, grade=grade)
    except Exception as e:
        print(f"Error in result route: {str(e)}")
        return redirect(url_for('error'))

@app.route('/review')
def review():
    try:
        mcqs = session.get('mcqs', [])
        user_answers = session.get('user_answers', {})
        return render_template('review.html', mcqs=mcqs, user_answers=user_answers, enumerate=enumerate)
    except Exception as e:
        print(f"Error in review route: {str(e)}")
        return redirect(url_for('error'))

@app.route('/error')
def error():
    return render_template('error.html')

def calculate_grade(score):
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
