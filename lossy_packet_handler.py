from threading import Lock
from collections import deque

class lossy_packet_handler:
    __packet_payload: deque = deque()
    __read_write_mutex = Lock()

    def __init__(self):
        self.data = []

    def receive(self, packet):
        with self.__read_write_mutex:
            self.__packet_payload.append(packet)

    def get_packet(self):
        with self.__read_write_mutex:
            return self.__packet_payload.popleft()

    def stored_buffer_size(self):
        with self.__read_write_mutex:
            return self.__packet_payload.__len__()
