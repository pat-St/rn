import getpass
import http.client
import urllib.parse
import gzip
from html.parser import HTMLParser
from threading import Thread
import time

pdf_file_uri = "https://moodle.htwg-konstanz.de/moodle/pluginfile.php/188750/mod_assign/introattachment/0/AIN%20RN%20-%20Laboraufgabe%20-%20HTTP.pdf?forcedownload=1"
chat_url = "https://moodle.htwg-konstanz.de/moodle/mod/chat/gui_basic/index.php"
chat_message_url = chat_url + "?id=183"

conn = http.client.HTTPSConnection("moodle.htwg-konstanz.de", timeout=10)
conn.set_debuglevel(0)

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


def get_message_payload(message, sessionkey, refresh=False):
    payload = {
        'message': message,
        'id': '183',
        'groupid': '0',
        'last': '1544723605',
        'sesskey': sessionkey,
    }
    if refresh:
        payload["refresh"] = 'Aktualisieren'
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


def unzip_payload(data):
    return gzip.decompress(data)


def find_sesskey(data):
    data = str(data)
    index = data.index("\"sesskey\":")
    extract_sesskey = data[index:index + 40].replace("\"sesskey\":", "").split(",")[0].replace("\"", "")
    return extract_sesskey


def extract_chat_timeline(data):
    data = str(data)
    start_index = data.index("<section")
    end_index = data.index("</section>")
    data = (data[start_index:end_index] + "</section>")
    # end_index = data.index("Zeit</th>")
    # data = data[end_index:]
    parse_message(data)


def parse_message(messages):
    # print(messages)

    class TableParser(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.in_td = False

        def handle_starttag(self, tag, attrs):
            if tag == 'td' or tag == 'th':
                self.in_td = True

        def handle_data(self, data):
            if self.in_td:
                print(data)

        def handle_endtag(self, tag):
            self.in_td = False

    parser = TableParser()
    parser.feed(messages)


def fetch_chat_key(moodle_cookie):
    login_header = standard_header.copy()
    login_header["Cookie"] = moodle_cookie
    res = send_request_without_body("GET", chat_message_url,
                                    login_header)
    data = res.read()
    return find_sesskey(unzip_payload(data))


def send_chat_message(moodle_cookie, sesskey, message):
    message = get_message_payload(message, sesskey)
    login_header = standard_header.copy()
    login_header["Cookie"] = moodle_cookie
    login_header["Content-Length"] = str(len(message))
    login_header["Referer"] = chat_url
    login_header["Content-Type"] = "application/x-www-form-urlencoded"
    res = send_request("POST", chat_message_url, message, login_header)
    data = res.read()


def start_refresh_chat_thread(moodle_cookie, session_key):
    t = Thread(target=refresh_chat_message, args=(moodle_cookie, session_key,))
    t.daemon = True
    t.start()
    return t


def refresh_chat_message(moodle_cookie, sesskey):
    while True:
        message = get_message_payload("", sesskey, True)
        login_header = standard_header.copy()
        login_header["Cookie"] = moodle_cookie
        login_header["Content-Length"] = str(len(message))
        login_header["Referer"] = chat_url
        login_header["Content-Type"] = "application/x-www-form-urlencoded"
        res = send_request("POST", chat_message_url, message, login_header)
        if res.status > 303:
            print("unable to get chat")
            break
        data = res.read()
        extract_chat_timeline(unzip_payload(data))
        time.sleep(2)


def load_pdf(moodle_cookie):
    login_header = standard_header.copy()
    login_header["Cookie"] = moodle_cookie
    res = send_request_without_body("GET", pdf_file_uri, login_header)
    data = res.read()
    save_payload_response(data)


def start_request():
    text_file = get_login_payload()
    first_header = standard_header.copy()
    login_url = "https://moodle.htwg-konstanz.de/moodle/login/index.php"
    first_header["Content-Type"] = "application/x-www-form-urlencoded"
    first_header["Content-Length"] = "49"
    res = send_request("POST", login_url, text_file, first_header)
    data = res.read()

    first_header.pop("Content-Length")
    login_cookie = get_session_cookie(res)[-1]
    first_header["Cookie"] = login_cookie
    first_header["Content-Type"] = "application/x-www-form-urlencoded"

    while res.status == 303:
        redirect_url = get_location(res)
        res = send_request_without_body("GET", redirect_url, first_header)
        data = res.read()

    return login_cookie


moodle_cookie = start_request()
sesskey = fetch_chat_key(moodle_cookie)
t = start_refresh_chat_thread(moodle_cookie, sesskey)

while True:
    chat_message = input()
    if chat_message == ':q' or chat_message == '':
        t.join(4)
        break
    if chat_message == 'pdf':
        load_pdf(moodle_cookie)
        print("downloaded pdf")
        pass
    if len(chat_message) > 2:
        send_chat_message(moodle_cookie, sesskey, str(chat_message))
    else:
        print("Invalide message")

conn.close()
