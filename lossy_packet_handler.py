from threading import Lock
from collections import deque


class lossy_packet_handler:

    def __init__(self):
        self.__packet_payload: deque = deque()
        self.__read_write_mutex: Lock = Lock()

    def receive(self, packet):
        self.__read_write_mutex.acquire()
        self.__packet_payload.append(packet)
        self.__read_write_mutex.release()

    def get_packet(self):
        self.__read_write_mutex.acquire()
        tmp = self.__packet_payload.popleft()
        self.__read_write_mutex.release()
        return tmp

    def stored_buffer_size(self):
        self.__read_write_mutex.acquire()
        tmp = len(self.__packet_payload)
        self.__read_write_mutex.release()
        return tmp
