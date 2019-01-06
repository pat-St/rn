import time
from go_back_n_socket import go_back_n_socket


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
    fist_socket = go_back_n_socket("127.0.0.1", 4300, 4303, 0, 20)
    second_socket = go_back_n_socket("127.0.0.1", 4303, 4300, 0.1)

    for i in (1500, 3000, 7000):
        send_msg = create_msg_payload(i)
        len_msg = len(send_msg)
        print("len of payload: ", len_msg)
        fist_socket.send(send_msg)
        while second_socket.has_recv(len_msg) is False:
            print("received: " + str(second_socket.get_recv_bytes()))
            time.sleep(5)
        receive_msg = second_socket.recv(len_msg)
        assert len(receive_msg) == len(send_msg)
        assert receive_msg == send_msg
        print("len of received ", len(receive_msg))
        time.sleep(2)

    fist_socket.stop()
    second_socket.stop()


def big_data_send():
    fist_socket = go_back_n_socket("127.0.0.1", 4300, 4303, 0, 20)
    second_socket = go_back_n_socket("127.0.0.1", 4303, 4300, 0)

    send_msg = create_msg_payload(27000)
    len_msg = len(send_msg)
    print("len of payload: ", len_msg)
    fist_socket.send(send_msg)
    while second_socket.has_recv(len_msg) is False:
        print("received: " + str(second_socket.get_recv_bytes()))
        time.sleep(5)
    receive_msg = second_socket.recv(len_msg)
    assert len(receive_msg) == len(send_msg)
    assert receive_msg == send_msg
    print("len of received ", len(receive_msg))

    fist_socket.stop()
    second_socket.stop()


def send_pdf():
    fist_socket = go_back_n_socket("127.0.0.1", 4300, 4303, 0, 40)
    second_socket = go_back_n_socket("127.0.0.1", 4303, 4300, 0)

    send_msg = get_pdf_to_data()
    len_msg = len(send_msg)
    print("len of payload: ", len_msg)
    fist_socket.send(send_msg)
    while second_socket.has_recv(len_msg) is False:
        print("received: " + str(second_socket.get_recv_bytes()))
        time.sleep(5)
    receive_msg = second_socket.recv(len_msg)
    assert len(receive_msg) == len(send_msg)
    assert receive_msg == send_msg
    save_payload_response(receive_msg)
    print("len of received ", len(receive_msg))

    fist_socket.stop()
    second_socket.stop()


#repeat_send_and_receiving()
big_data_send()
#send_pdf()
