import getpass
import http.client
import urllib.parse

pdf_file_uri = "https://moodle.htwg-konstanz.de/moodle/pluginfile.php/188750/mod_assign/introattachment/0/AIN%20RN%20-%20Laboraufgabe%20-%20HTTP.pdf?forcedownload=1"
conn = http.client.HTTPSConnection("moodle.htwg-konstanz.de", timeout=10)

standard_header = {
        "Host": "moodle.htwg-konstanz.de",
        "Accept": "text/html,application/json",
        "Accept-Language": "de-DE",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

def get_session_cookie(header_response):
    tmp = []
    for (key, value) in header_response.getheaders():
        if key == 'Set-Cookie' and value.startswith('MoodleSession='):
            tmp.append(str(value.split(';')[0]).strip())
    return tmp

def get_location(header_response):
    tmp = ""
    for (key, value) in header_response.getheaders():
        if key == 'Location':
            tmp = value.strip()
    if tmp == "":
        exit(0)
    return tmp

def get_login_payload():
    user_name = input("Insert id: ")
    login_passwd = getpass.getpass("Insert password: ")
    payload = {
        'username': user_name,
        'password': login_passwd,
        'anchor': ''
    }
    return urllib.parse.urlencode(payload)

def printHeader(req_header, res_header):
    print("*************** login header ***************")
    for key, value in req_header.items():
        print(key + ": " + value)
    print("*************** login header ***************")
    print("*************** login response header ***************")
    for key, value in res_header.getheaders():
        print(key + ": " + value)
    print("*************** login response header ***************")

def printStatus(res):
    print("RETURN STAT:", res.status, res.reason)

def send_request(type, url, body, header):
    conn.request(method=type, url=url, body=body,
                 headers=header)
    return conn.getresponse()

def send_request_without_body(type, url, header):
    conn.request(method=type, url=url, headers=header)
    return conn.getresponse()

def save_payload_response(data):
    f = open("test.pdf", "wb")
    f.write(data)
    f.close()

def start_request():
    text_file = get_login_payload()
    first_header = standard_header.copy()
    login_url = "https://moodle.htwg-konstanz.de/moodle/login/index.php"
    first_header["Content-Type"] = "application/x-www-form-urlencoded"
    first_header["Content-Length"] = "49"
    res = send_request("POST", login_url, text_file, first_header)
    data = res.read()
    print("RESPONSE: ", res.status, res.reason)

    redirect_url = get_location(res)
    login_cookie = get_session_cookie(res)[1]
    login_header = standard_header.copy()
    login_header["Cookie"] = login_cookie
    login_header["Content-Type"] = "application/x-www-form-urlencoded"
    res = send_request_without_body("GET", redirect_url, login_header)
    data = res.read()
    print("RESPONSE: ", res.status, res.reason)

    redirect_url = get_location(res)
    res = send_request_without_body("GET", redirect_url, login_header)
    print("RESPONSE: ", res.status, res.reason)
    printHeader(login_header, res)
    data = res.read()

    login_header.pop("Content-Type")

    res = send_request_without_body("GET", pdf_file_uri, login_header)
    print("RESPONSE: ", res.status, res.reason)
    printHeader(login_header, res)
    data = res.read()
    save_payload_response(data)

    


    conn.close()

start_request()
