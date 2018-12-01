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

thread_pool_lock = threading.Lock()
threadPool = []

thread_run_lock = threading.Lock()
threadRunning = True


def returnTargetAdress(key):
    (i1, i2) = key.getpeername()
    return str(i1)


def returnNickName(input):
    return input.split()[2]


def getMessage(input):
    i = input.split()
    if len(i) >= 2:
        return str(i[0]), "".join(map(str, i[1:]))
    return str(i[0]), ""


def addNewClientToList(sock, nickname):
    with user_list_lock:
        activeUser[sock] = nickname


def messageParse(message, conn):
    if message == ('Q', ""):
        with print_lock:
            print("User [ " + str(activeUser.get(conn)) + " ] quit")
        quitConnection(conn)
    if message == ('C', message[1]):
        with print_lock:
            print("[ " + str(activeUser.get(conn)) + " ]: " + str(message[1]))
    if message == ('S', message[1]):
        with print_lock:
            print("Add user ", str(message[1]))
        conn.send(('S ' + username).encode("utf-8"))
        addNewClientToList(conn, str(message[1]))


def receiveMessageThread(conn):
    while True:
        with thread_run_lock:
            if not threadRunning:
                break
        try:
            data = conn.recv(1024).decode('utf-8')
            message = getMessage(data)
            messageParse(message, conn)
        except (ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError, OSError) as err:
            # with user_list_lock:
            #     activeUser.pop(conn)
            # conn.close()
            with print_lock:
                print('retreive Message ', str(err))
                break
        except socket.timeout:
            with print_lock:
                pass


def appendNewThreadInPool(conn):
    t = threading.Thread(target=receiveMessageThread, args=(conn,))
    t.daemon = True
    with thread_pool_lock:
        threadPool.append(t)
    t.start()


def waitForNewClient():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', PORT))
    sock.listen()
    while True:
        with thread_run_lock:
            if not threadRunning:
                break
        conn, addr = sock.accept()
        appendNewThreadInPool(conn)


def scanNetwork():
    sendNickname = 'S ' + username
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(120)
    for i in 15, 62:  # range(LowestIP, HighestIP):
        newHostIP = HOST + str(i)
        try:
            sock.connect((newHostIP, PORT))
            try:
                sock.send(sendNickname.encode("utf-8"))
                othernickname = sock.recv(1024).decode("utf-8")
                othernickname = str(othernickname).split()[1]
                addNewClientToList(sock, othernickname)
                appendNewThreadInPool(sock)
            except socket.timeout as err:
                print("scan send and retreive: " + str(err))
        except (
                ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError, IndexError, OSError,
                socket.timeout) as err:
            print("scan Network: " + str(err))
            pass


def sendMessage(nickname, message):
    for key, value in activeUser.items():
        if value == nickname:
            try:
                key.send(('C ' + message).encode("utf-8"))
            except (ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError, IndexError, OSError,
                    socket.timeout) as err:
                print("send Message Error: " + str(err))
                pass


def listClients():
    for key, value in activeUser.items():
        print("found user " + str(value) + " from address " + returnTargetAdress(key) + "\n")


def quitConnection(conn):
    if activeUser.__contains__(conn):
        with user_list_lock:
            activeUser.pop(conn)
        conn.close()


def quitAllConnections():
    copy = ()
    with thread_run_lock:
        threadRunning = False
    for worker in threadPool:
        worker.join(2)
    with user_list_lock:
        copy = activeUser.copy()
    for key, value in copy.items():
        try:
            print('Closing retreive from address' + returnTargetAdress(key) + " : " + str(value) + "\n")
            key.send('Q'.encode("utf-8"))
            with user_list_lock:
                activeUser.pop(key)
            key.close()
        except (socket.timeout, OSError) as err:
            with print_lock:
                print('quit timed out at ', str(err) + "\n")
            key.close()


# start point
while True:
    username = input("Set a username:")
    userinput = input("is ${username} right? [Y/n] ")
    if userinput == "Y" or userinput == "":
        break
# scan all client in network
scanNetwork()
# listen on new message
receiveThread = threading.Thread(target=waitForNewClient)
receiveThread.daemon = True
receiveThread.start()

while True:
    inputMessage = input(">")
    if inputMessage == 'Q':
        #with thread_run_lock:
         #   threadRunning = False
        quitAllConnections()
        receiveThread.join(1)
        break
    if inputMessage.startswith('C'):
        inputList = inputMessage.split()
        sendMessage(inputList[1], inputList[2])
    if inputMessage == 'L':
        listClients()
