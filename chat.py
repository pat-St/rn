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


def returnTargetAdress(key):
    (i1, i2) = key.getpeername()
    return str(i1)


def returnNickName(input):
    return input.split()[2]


def receiveMessageThread(conn):
    while True:
        with thread_run_lock:
            if not threadRunning:
                break
        try:
            data = conn.recv(1024)
            with print_lock:
                print(activeUser.get(conn) + " : " + data.decode('utf-8') + "\n")
        except (ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError):
            pass
        except socket.timeout:
            with print_lock:
                print('retreive Message timed out at', time.asctime() + " from " + str(activeUser.get(conn)) + "\n")


def addSocketToList(sock, nickname):
    with user_list_lock:
        activeUser[sock] = nickname
    t = threading.Thread(target=receiveMessageThread, args=(sock,))
    t.daemon = True
    threadPool.append(t)
    t.start()


def receiveClientThread(conn):
    sendNickname = 'S ' + username
    try:
        othernickname = conn.recv(1024).decode("utf-8")
        conn.send(sendNickname.encode("utf-8"))
        (otheraddress, tmp) = conn.getpeername()
        othernickname = str(othernickname).split()[1]
        with print_lock:
            print("otheraddress: " + otheraddress + " other nickname " + othernickname + "\n")
        addSocketToList(conn, othernickname)
    except (
    ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError, OSError, IndexError, socket.timeout) as err:
        with print_lock:
            print("Recieve from Client " + str(err))
        pass


def receiveClients():
    sendNickname = 'S ' + username
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', PORT))
    sock.listen()
    while True:
        with thread_run_lock:
            if not threadRunning:
                break
        conn, addr = sock.accept()
        t = threading.Thread(target=receiveClientThread, args=(conn,))
        t.daemon = True
        threadPool.append(t)
        t.start()


def scanNetwork():
    sendNickname = 'S ' + username
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(20)
    for i in 12, 63:  # LowestIP, HighestIP:
        newHostIP = HOST + str(i)
        try:
            sock.connect((newHostIP, PORT))
            try:
                sock.send(sendNickname.encode("utf-8"))
                othernickname = sock.recv(1024).decode("utf-8")
                print("receive: " + str(othernickname) + "\n")
                (otheraddress, tmp) = sock.getpeername()
                print("otheraddress: " + str(otheraddress) + "\n")
                othernickname = str(othernickname).split()[1]
                addSocketToList(sock, othernickname)
            except socket.timeout as err:
                print("scan send and retreive: " + str(err))
        except (
        ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError, IndexError, OSError, socket.timeout) as err:
            print("scan Network: " + str(err))
            sock.close()
            pass


def sendMessage(nickname, message):
    for key, value in activeUser:
        if value == nickname:
            try:
                key.send(message.encode("utf-8"))
            except (ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError, IndexError, OSError,
                    socket.timeout) as err:
                print("send Message: " + str(err))
                pass


def listClients():
    for key, value in activeUser.items():
        print("found user" + str(value) + "from address " + returnTargetAdress(key) + "\n")


def quitThread():
    for key, value in activeUser.items():
        try:
            print('Closing ...' + returnTargetAdress(key) + "from " + str(value) + "\n")
            key.send('Q'.encode("utf-8"))

            activeUser.pop(key)
            key.close()
        except (socket.timeout, OSError) as err:
            with print_lock:
                print('quit timed out at ', str(err) + "\n")
            key.close()


while True:
    username = input("Set a username:")
    userinput = input("is ${username} right? [Y/n] ")
    if userinput == "Y" or userinput == "":
        break

receiveThread = threading.Thread(target=receiveClients)
receiveThread.daemon = True
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
