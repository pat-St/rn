from _ctypes import Array
import time
from go_back_n_socket import go_back_n_socket


def create_msg_payload(size: int):
    tmp = b'0'
    for i in range(0, size - 1):
        tmp += b'0'
    return tmp


fist_socket = go_back_n_socket("127.0.0.1", 4300, 4303)
second_socket = go_back_n_socket("127.0.0.1", 4303, 4300)

send_msg = create_msg_payload(1500)
len_msg = len(send_msg)
print("len of payload: ", len_msg)
fist_socket.send(send_msg)
receive_msg = b""
while len(receive_msg) != len_msg:
    time.sleep(20)
    receive_msg = second_socket.recv(5000)
print("len of received ", len(receive_msg))
#assert receive_msg == send_msg

fist_socket.stop()
second_socket.stop()
