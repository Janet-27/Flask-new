from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return "Welcome to Janet's Project"

@app.route('/about')
def about():
    return "This project is about learning Flask and Git repository."


if __name__ == '__main__':
    app.run(debug=True)


