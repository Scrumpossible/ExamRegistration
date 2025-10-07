from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('Login.html')
        

@app.route('/info')
def info():
    return render_template('Info.html')


@app.route('/faculty')
def faculty():
    return render_template('Faculty.html')



if __name__ == '__main__':
    app.run(host='localhost', port = 5000, debug = True)
    print('The flask server is running')
