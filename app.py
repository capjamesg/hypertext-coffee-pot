from flask import Flask, jsonify, request, render_template, session, redirect, send_from_directory, abort
from config import *
import datetime
import socket
import json

print("This project has not been tested on a real coffee pot.")
print("This project is designed to work with digital (not real) coffee pots.")

app = Flask(__name__)

app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

# load config from config.py
app.config.from_pyfile('config.py')

@app.route("/")
def index():
    additions = request.args.getlist("additions")
    method = request.args.get("method")
    message_for_server = request.args.get("message")

    if method:
        method = method.lower()

        if not message_for_server:
            message = ""

    if message_for_server:
        message = message_for_server.lower()

    if (method == "brew" or method == "post") and (message_for_server == "start" or message_for_server == "stop"):
        message = "BREW coffee://james HTTP/1.1\nContent-Type: application/coffee-pot-command\n"
        if additions:
            message = message + "\nAccept-Additions: " + "; ".join(additions)
        message = message + "\n" + message_for_server
    elif method == "when":
        message = "WHEN coffee://james HTTP/1.1\nContent-Type: application/coffee-pot-command\n"
    elif method == "propfind":
        message = "PROPFIND coffee://james HTTP/1.1\nContent-Type: application/coffee-pot-command\n"
    else:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.connect((HOST, PORT))

        message = "GET coffee://james HTTP/1.1\nContent-Type: application/coffee-pot-command\n"

        server.send(bytes(message.encode()))

        data = server.recv(1024).decode()

        brewing = False
        additions = ""
        contains_milk = False
        brew_time = ""
        brew_time_end = ""
        pouring_milk = None
        finish_brewing_unix = 0

        if data and data.strip():
            response = data.split("\r\n")
            if response[-1].strip() != "{}" and response[-1].strip() != "":
                brewing = True

                brewing_description = json.loads(response[-1].strip().replace("'", '"'))

                additions = brewing_description["additions"]
            
                for addition in brewing_description["additions"]:
                    if addition.lower() in MILKS:
                        contains_milk = True

                brew_time = brewing_description["date"]
                brew_time_end = brewing_description["brew_time_end"]
                pouring_milk = brewing_description["pouring_milk"]

                finish_brewing_unix = datetime.datetime.strptime(pouring_milk, "%a, %d %b %Y %H:%M:%S").timestamp()

                # convert pouring_milk to datetime
                if pouring_milk != "":
                    pouring_milk = datetime.datetime.strptime(pouring_milk, "%a, %d %b %Y %H:%M:%S")
                    brew_time_end_object = datetime.datetime.strptime(brew_time_end, "%a, %d %b %Y %H:%M:%S")

                    if pouring_milk <= brew_time_end_object:
                        pouring_milk = ""

        return render_template("index.html",
            header="Welcome to CoffeePot",
            accepted_additions=ACCEPTED_ADDITIONS,
            available_pots=COFFEE_POTS,
            additions=additions,
            brew_time=brew_time,
            brew_time_end=brew_time_end,
            contains_milk=contains_milk,
            pouring_milk=pouring_milk,
            brewing=brewing,
            finish_brewing_unix=finish_brewing_unix
        )

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.connect((HOST, PORT))

    server.send(bytes(message.encode()))

    data = server.recv(1024).decode()

    return redirect("/")

@app.route("/log")
def coffeepot_log():
    past_coffees = []
    coffees_brewed_count = 0
    
    with open("past_coffees.json", "r") as f:
        for line in f:
            past_coffees.append(json.loads(line))
            coffees_brewed_count += 1

    past_coffees.reverse()

    return render_template("history.html",
        header="CoffeePot Log",
        past_coffees=past_coffees,
        coffees_brewed_count=coffees_brewed_count
    )

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html", title="Page not found", error=404), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return render_template("404.html", title="Method not allowed", error=405), 405

@app.errorhandler(500)
def server_error(e):
    return render_template("404.html", title="Server error", error=500), 500

@app.route("/robots.txt")
def robots():
    return send_from_directory(app.static_folder, "robots.txt")

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico")

@app.route("/assets/<path:path>")
def assets(path):
    return send_from_directory("assets", path)

if __name__ == "__main__":
    app.run(debug=True)