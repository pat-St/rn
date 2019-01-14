import time
from go_back_n_socket import go_back_n_socket
from datetime import datetime, timedelta


def create_msg_payload(size: int):
    tmp = b'0'
    for i in range(0, size - 1):
        if i % 2 is 0:
            tmp += b'0'
        else:
            tmp += b'1'
    return tmp


def get_pdf_to_data():
    f = open("test.pdf", "rb")
    return f.read()


def save_payload_response(data):
    f = open("test1.pdf", "wb")
    f.write(data)
    f.close()


def repeat_send_and_receiving():
    fist_socket = go_back_n_socket("127.0.0.1", 4300, 4303, 0, 5)
    second_socket = go_back_n_socket("127.0.0.1", 4303, 4300, 0)

    for i in (1500, 3000, 70000):
        send_msg = create_msg_payload(i)
        len_msg = len(send_msg)
        print("len of payload: ", len_msg)
        fist_socket.send(send_msg)
        while second_socket.has_recv(len_msg) is False:
            print("received: " + str(second_socket.get_recv_bytes()))
            time.sleep(0.5)
        receive_msg = second_socket.recv(len_msg)
        assert receive_msg == send_msg
        print("len of received ", len(receive_msg))
        time.sleep(2)

    fist_socket.stop()
    second_socket.stop()
    time.sleep(2)
    first_socket = None
    second_socket = None


def big_data_send():
    fist_socket = go_back_n_socket("127.0.0.1", 4300, 4303, 0.2, 20)
    second_socket = go_back_n_socket("127.0.0.1", 4303, 4300, 0.2, 20)

    send_msg = create_msg_payload(270000)
    len_msg = len(send_msg)
    print("len of payload: ", len_msg)
    fist_socket.send(send_msg)
    while second_socket.has_recv(len_msg) is False:
        print("received: " + str(second_socket.get_recv_bytes()))
        time.sleep(1)
    receive_msg = second_socket.recv(len_msg)
    assert receive_msg == send_msg
    print("len of received ", len(receive_msg))

    fist_socket.stop()
    second_socket.stop()
    time.sleep(2)
    first_socket = None
    second_socket = None


def send_pdf():
    fist_socket = go_back_n_socket("127.0.0.1", 4300, 4303, 0, 40)
    second_socket = go_back_n_socket("127.0.0.1", 4303, 4300, 0)

    send_msg = get_pdf_to_data()
    len_msg = len(send_msg)
    print("len of payload: ", len_msg)
    fist_socket.send(send_msg)
    while second_socket.has_recv(len_msg) is False:
        print("received: " + str(second_socket.get_recv_bytes()))
        time.sleep(2)
    receive_msg = second_socket.recv(len_msg)
    assert receive_msg == send_msg
    save_payload_response(receive_msg)
    print("len of received ", len(receive_msg))

    fist_socket.stop()
    second_socket.stop()
    time.sleep(2)
    first_socket = None
    second_socket = None


def send_with_stats(window_size: int = 10):
    fist_socket = go_back_n_socket("127.0.0.1", 4300, 4303, 0, window_size, send_packet_size=1000)
    second_socket = go_back_n_socket("127.0.0.1", 4303, 4300, 0.1)
    start_time = datetime.utcnow()
    send_msg = create_msg_payload(257500)
    len_msg = len(send_msg)
    fist_socket.send(send_msg)
    while second_socket.has_recv(len_msg) is False:
        time.sleep(0.2)
    receive_msg = second_socket.recv(len_msg)
    end_time = datetime.utcnow()
    #print("total time ", str((end_time - start_time).seconds))

    fist_socket.stop()
    second_socket.stop()
    time.sleep(2)
    first_socket = None
    second_socket = None
    return (end_time - start_time).seconds


first_socket = None
second_socket = None

while True:
    s = input("start>")
    if first_socket is not None:
        first_socket.stop()
        first_socket = None
    if s == "send":
        if first_socket is None:
            first_socket = go_back_n_socket("127.0.0.1", 4300, 4303, 0.1, 10)
        n = input("send size>")
        if n == "pdf":
            create_payload = get_pdf_to_data()
            print("send: " + str(len(create_payload)))
            first_socket.send(create_payload)
        else:
            n_size: int = 0
            try:
                n_size = int(n)
            except Exception:
                print(n + " not a number")
                pass
            create_payload = create_msg_payload(n_size)
            first_socket.send(create_payload)
    elif s == "recv":
        if second_socket is None:
            second_socket = go_back_n_socket("127.0.0.1", 4303, 4300, 0.1, 10)
        n = input("receive size>")
        if n == "pdf":
            n_size: int = len(get_pdf_to_data())
            print("receive: " + str(n_size))
            while second_socket.get_recv_bytes() != n_size:
                time.sleep(0.5)
            rev_msg = second_socket.recv(n_size)
            print("receive: " + str(len(rev_msg)))
            save_payload_response(rev_msg)
        else:
            n_size: int = 0
            try:
                n_size = int(n)
            except Exception:
                print(n + " not a number")
                pass
            while second_socket.get_recv_bytes() != n_size:
                time.sleep(0.5)
            rev_msg = second_socket.recv(n_size)
            print("receive: " + str(len(rev_msg)))
        if second_socket is not None:
            second_socket.stop()
            second_socket = None
    elif s == "test":
        if first_socket is None and second_socket is None:
            print("test repeat send and receive")
            repeat_send_and_receiving()
            print("test send big data with drop")
            big_data_send()
            print("test send pdf")
            send_pdf()
            print("all tests done")
    elif s == "stats":
        if first_socket is None and second_socket is None:
            n = input("window size>")
            try:
                n_size = int(n)
                time_lap = send_with_stats(n_size)
                print("time: " + str(time_lap))
            except Exception:
                print(n + " not a number")
                pass

    elif s == "stop":
        print("stopped")
        break
    else:
        print("use send | recv | test | stats | stop")
