import lossy_udp_socket
from gobacknsocket import GoBackNSocket

tar_port = 4300
des_port = 4303
address = "127.0.0.1"

go_back_handler = GoBackNSocket()

lossy_one = lossy_udp_socket.lossy_udp_socket(go_back_handler, tar_port, (address, des_port), 0)

lossy_two = lossy_udp_socket.lossy_udp_socket(go_back_handler, des_port, (address, tar_port), 0)

lossy_two.send("hallo welt eins".encode("utf-8"))

lossy_one.send("hallo welt zwei".encode("utf-8"))

lossy_one.stop()
lossy_two.stop()
