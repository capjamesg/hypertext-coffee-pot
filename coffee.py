from config import *
import datetime
import logging
import socket
import json
import os

logging.basicConfig(filename="coffeepot.log", level=logging.DEBUG)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server.bind((HOST, PORT))

pouring_milk = None

last_request = None

# rewrite the currently brewing file every time the program starts up
# a coffee pot that has been stopped in the middle of operation should not pick up where it left off (!)
with open("currently_brewing.json", "w+") as f:
    f.write("{}")

if not os.path.isfile("past_coffees.json"):
    with open("past_coffees.json", "w+") as f:
        f.write("{}")

def ensure_request_is_valid(url, content_type, method, processing_request, connection):
    if "://" not in url:
        connection.send(b"HTCPCP/1.1 400 Bad Request\n\n")
        processing_request = False

    if url.split("://")[0].encode().decode("ascii") not in ACCEPTED_COFFEE_SCHEMES:
        connection.send(b"HTCPCP/1.1 404 Not Found\r\n\r\n")
        processing_request = False

    if url.split("://")[1] != "james":
        connection.send(b"HTCPCP/1.1 404 Not Found\r\n\r\n")
        processing_request = False

    if method not in ACCEPTED_METHODS:
        connection.send(b"HTCPCP/1.1 501 Not Implemented\r\n\r\n")
        processing_request = False

    if content_type and content_type[0] != "Content-Type: application/coffee-pot-command":
        connection.send(b"HTCPCP/1.1 415 Unsupported Media Type\r\n\r\n")
        processing_request = False

    return processing_request

def process_additions(headers, processing_request, pouring_milk, connection):
    accept_additions = [header for header in headers if header.startswith("Accept-Additions")]

    if len(accept_additions) > 0:
        additions = accept_additions[0].split(":")[1].strip().split(";")
        invalid_addition = False

        for item in additions:
            print(item.lower().strip())
            if ACCEPTED_ADDITIONS.get(item.lower().strip()) is None:
                response = "HTCPCP/1.1 406 Not Acceptable\r\n\r\n" + ", ".join(list(ACCEPTED_ADDITIONS.keys())).strip(", ")
                connection.send(bytes(response.encode()))
                invalid_addition = True
                processing_request = False
            elif item.lower() in MILKS:
                # pour milk in 5 mins, after brew
                pouring_milk = (datetime.datetime.now() + datetime.timedelta(minutes=5)).strftime("%a, %d %b %Y %H:%M:%S")

        if invalid_addition:
            processing_request = False
    else:
        additions = None

    return additions, processing_request, pouring_milk

def create_request_response(method, additions, pouring_milk):
    response = ""

    if method == "GET" or method == "PROPFIND":
        with open("currently_brewing.json", "r") as f:
            response = json.load(f)
            response = json.dumps(response)
        
    elif method == "BREW" or method == "POST":
        response_body = message.split("\n")[-1]

        if response_body == "stop":
            with open("currently_brewing.json", "w+") as f:
                f.write("{}")
        elif response_body == "start":
            now = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S")
            end_time = (datetime.datetime.now() + datetime.timedelta(minutes=5)).strftime("%a, %d %b %Y %H:%M:%S")

            if additions == None:
                additions = []

            if pouring_milk == None:
                milk_status = ""
            else:
                milk_status = pouring_milk

            record_to_save = json.dumps(
                    {
                        "date": now,
                        "beverage_type": "Coffee",
                        "additions": additions,
                        "brew_time_end": end_time,
                        "pouring_milk": milk_status
                }
            )

            with open("past_coffees.json", "a+") as coffee_records:
                coffee_records.write(record_to_save + "\n")

            with open("currently_brewing.json", "w+") as brewing_record:
                brewing_record.write(record_to_save)
        else:
            response = "HTCPCP/1.1 400 Bad Request\r\n\r\n"

    elif method == "WHEN":
        with open("currently_brewing.json", "r") as f:
            response = json.load(f)

        pouring_milk = datetime.datetime.strptime(pouring_milk, "%a, %d %b %Y %H:%M:%S")
        brew_time_end_object = datetime.datetime.strptime(response.get("brew_time_end"), "%a, %d %b %Y %H:%M:%S")

        if pouring_milk >= brew_time_end_object:
            response = "Milk has stopped pouring."
        else:
            response = "Milk is not pouring."

        pouring_milk = None

    return response

while True:
    # start listening for connections connections
    server.listen()

    print("Listening for connections on port " + str(PORT))

    connection, address = server.accept()

    # set timeout so requests cannot hang
    connection.settimeout(5)

    print("Connected to: ", address)

    processing_request = True

    while processing_request:
        # get message
        message = connection.recv(1024).decode()

        last_request = message

        if len(message.strip().replace("\n", "").replace("\r", "")) == 0:
            processing_request = False

        logging.info("Received message: " + message)

        # get last coffee
        with open("currently_brewing.json", "r") as f:
            last_coffee = json.load(f)

        method = message.split(" ")[0]

        if last_coffee and last_coffee["brew_time_end"] and (method == "BREW" or method == "POST"):
            # get last_coffee["brew_time_end"] as datetime object
            last_brewed = datetime.datetime.strptime(last_coffee["brew_time_end"], "%a, %d %b %Y %H:%M:%S")

            if last_brewed + datetime.timedelta(minutes=5) > datetime.datetime.now():
                response = "HTCPCP/1.1 406 Not Acceptable\r\n\r\n" + ", ".join(list(ACCEPTED_ADDITIONS.keys())).strip(", ")
                connection.send(bytes(response.encode()))
                processing_request = False
            else:
                with open("currently_brewing.json", "w+") as f:
                    f.write("{}")

        url = message.split(" ")[1]
        headers = message.split("\n")

        content_type = [header for header in headers if header.startswith("Content-Type")]

        safe = [header for header in headers if header.startswith("Safe:")]

        if safe and safe[0] == "Yes":
            message = last_request
            method = message.split(" ")[0]
            url = message.split(" ")[1]
            headers = message.split("\n")

        processing_request = ensure_request_is_valid(url, content_type, method, processing_request, connection)

        additions, processing_request, pouring_milk = process_additions(headers, processing_request, pouring_milk, connection)

        if method in ACCEPTED_METHODS:
            current_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S")

            # response body
            headers_to_send = [
                "HTCPCP/1.1 200 OK\r\n",
                "Server: CoffeePot\r\n",
                "Content-Type: message/coffeepot\r\n",
                "Date: " + current_date + "\r\n",
            ]

            response = create_request_response(method, additions, pouring_milk)

            final_response = "".join(headers_to_send) + response

            logging.info("Sending response: " + final_response)

            print(final_response)

            connection.send(bytes(final_response.encode("utf-8")))
        
        processing_request = False

    # close connection after request has been processed
    logging.info("Closing connection")
    connection.close()
    logging.info("Connection closed")