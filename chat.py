import time
import socket
import threading

HOST = '192.168.2.'  # '141.37.168.'
PORT = 50000
server_activity_period = 30
ADDR = (HOST, PORT)
pool_size = 5

LowestIP = 1
HighestIP = 63

username = ""
activeUser = dict()
print_lock = threading.Lock()
user_list_lock = threading.Lock()

threadPool = []

thread_run_lock = threading.Lock()
threadRunning = True


def returnNickName(input):
    return input.split()[2]


def receiveMessageThread(conn):
    while True:
        with thread_run_lock:
            if not threadRunning:
                break
        try:
            data = conn.recv(1024)
            if not data:
                print('Connection closed from other side' + "\n")
                print('Closing ...' + "\n")
                break
            with print_lock:
                print(activeUser.get(conn) + " : " + data.decode('utf-8') + "\n")
        except (ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError):
            with user_list_lock:
                activeUser.pop(conn)
            conn.close()
            pass
        except socket.timeout:
            with print_lock:
                print('Socket timed out at', time.asctime() + "\n")


def addSocketToList(sock, nickname):
    with user_list_lock:
        activeUser[sock] = nickname
    t = threading.Thread(target=receiveMessageThread, args=(sock,))
    #t.daemon = True
    threadPool.append(t)
    t.start()


def receiveClients():
    sendNickname = 'S ' + username
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', PORT))
    sock.listen(4)
    while True:
        with thread_run_lock:
            if not threadRunning:
                break
        try:
            conn, addr = sock.accept()
            othernickname = conn.recv(1024).decode("utf-8")
            sock.send(sendNickname.encode("utf-8"))
            otheraddress = socket.gethostbyname(sock.getpeername())
            othernickname = str(othernickname).split()[1]
            with print_lock:
                print("otheraddress: " + otheraddress + " other nickname " + othernickname + "\n")
            addSocketToList(conn, othernickname)
        except (ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError, OSError, IndexError, socket.timeout) as err:
            print(err)
            sock.close()
            pass


def scanNetwork():
    sendNickname = 'S ' + username
    for i in 12, 63:#LowestIP, HighestIP:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        newHostIP = HOST + str(i)
        try:
            sock.connect_ex((newHostIP, PORT))
            sock.send(sendNickname.encode("utf-8"))
            othernickname = sock.recv(1024).decode("utf-8")
            otheraddress = sock.getpeername()
            print("otheraddress: " + str(otheraddress) + "\n")
            othernickname = str(othernickname).split()[1]
            addSocketToList(sock, othernickname)
        except (ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError, IndexError, OSError, socket.timeout) as err:
            print(err)
            sock.close()
            pass


def sendMessage(nickname, message):
    for key, value in activeUser:
        if value == nickname:
            try:
                key.send(message.encode("utf-8"))
            except key.timeout:
                key.close()
                pass


def listClients():
    for key, value in activeUser:
        print("found user" + value + "from adress " + str(key))


def quitThread(conn):
    while True:
        try:
            conn.send('Q'.encode("utf-8"))
            print('Closing ...' + "\n")
        except socket.timeout:
            with print_lock:
                print('Socket timed out at', time.asctime() + "\n")
        conn.close()


while True:
    username = input("Set a username:")
    userinput = input("is ${username} right? [Y/n] ")
    if userinput == "Y" or userinput == "":
        break

receiveThread = threading.Thread(target=receiveClients)
#receiveThread.daemon = True
receiveThread.start()
scanNetwork()

while True:
    inputMessage = input(">")
    if inputMessage == 'Q':
        with thread_run_lock:
            threadRunning = False
        for key, value in activeUser.items():
            quitThread(key)
        receiveThread.join(1)
        break
    if inputMessage.startswith('C'):
        inputList = inputMessage.split()
        print(len(inputList))
        sendMessage(inputList[1], inputList[2])
    if inputMessage == 'L':
        listClients()
