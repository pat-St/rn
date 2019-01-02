import time
from collections import deque
from plist import Dict
from threading import Thread, Lock, Timer

from lossy_udp_socket import lossy_udp_socket
from lossy_packet_handler import lossy_packet_handler


class go_back_n_socket:
    # connection config
    __des_ip: str
    __loc_port: int
    __rem_port: int

    # udp socket
    connection = None
    # udp packet handler
    __go_back_handler = lossy_packet_handler()

    # sending config
    __segment_size: int = 1468
    __window_size: int = 4
    __send_timeout: int = 4

    __send_packets: dict = {}
    __send_packets_lock: Lock = Lock()

    __timeout_seq_nr: int = None
    __send_packets_timer: dict = {}
    __send_packets_timer_lock: Lock = Lock()

    __receive_queue_msg: dict = {}
    __queue_write_lock: Lock = Lock()

    __receive_queue_response: [] = []
    __receive_queue_response_lock: Lock = Lock()

    __pull_payload_worker: Thread
    __receiver_payload_worker: Thread
    __response_payload_worker: Thread
    __send_packets_worker: Thread
    __timeout_worker_queue: deque = deque()
    __stop_thread: bool = False

    __final_rev_msg: bytes = b""
    __finale_recv_lock: Lock = Lock()

    # received packets getter setter
    def __write_in_receive_msg_buffer(self, seq_nr: int, payload_msg: bytes):
        with self.__queue_write_lock:
            self.__receive_queue_msg[seq_nr] = payload_msg

    def __read_from_receive_buffer(self):
        with self.__queue_write_lock:
            return self.__receive_queue_msg.copy()

    def __drop_key_from_receive_buffer(self, seq_nr: int):
        with self.__queue_write_lock:
            del self.__receive_queue_msg[seq_nr]

    # response getter setter
    def __write_in_response_msg_buffer(self, ack_nr: int):
        with self.__receive_queue_response_lock:
            self.__receive_queue_response.append(ack_nr)

    def __read_from_response_buffer(self):
        with self.__receive_queue_response_lock:
            return self.__receive_queue_response

    def __drop_item_from_response_buffer(self, ack_nr: int):
        with self.__receive_queue_response_lock:
            self.__receive_queue_response.remove(ack_nr)

    # send queue getter setter
    def __set_send_packets_to_queue(self, key: int, value: bytes):
        with self.__send_packets_lock:
            self.__send_packets[key] = value

    def __get_send_packets_from_queue(self):
        with self.__send_packets_lock:
            return self.__send_packets.copy()

    def __drop_send_packets_from_queue(self, seq_nr):
        with self.__send_packets_lock:
            del self.__send_packets[seq_nr]

    # timer getter setter
    def __set_packets_timer(self, seq_nr: int, enable_timer=True):
        with self.__send_packets_timer_lock:
            self.__send_packets_timer[seq_nr] = enable_timer

    def __get_packets_timer(self):
        with self.__send_packets_timer_lock:
            return self.__send_packets_timer.copy()

    def __drop_packets_timer(self, seq_nr):
        with self.__send_packets_timer_lock:
            del self.__send_packets_timer.pop[seq_nr]

    def __init__(self, ip_address: str, local_port: int, remote_port: int):
        self.__loc_port = local_port
        self.__rem_port = remote_port
        self.__des_ip = ip_address
        self.__send_packets = {}
        self.__receive_queue_msg = {}
        self.connection = lossy_udp_socket(self.__go_back_handler, local_port, (ip_address, remote_port), 0)
        self.__start_worker_thread()

    def send(self, msg: bytes):
        # send window size packets parts in a loop
        self.__prepare_msg_for_send(msg)

    def recv(self, bytecount: int):
        with self.__queue_write_lock:
            return self.__final_rev_msg

    def stop(self):
        self.__stop_thread = True
        self.__send_packets_worker.join(1)
        self.__pull_payload_worker.join(1)
        self.__receiver_payload_worker.join(1)
        self.__response_payload_worker.join(1)
        self.connection.stop()

    def __start_worker_thread(self):
        t = Thread(target=self.__recv_packets_worker)
        t.daemon = True
        t.start()
        self.__pull_payload_worker = t
        t2 = Thread(target=self.__receiver_payload_handler)
        t2.daemon = True
        t2.start()
        self.__receiver_payload_worker = t2
        t3 = Thread(target=self.__response_payload_handler)
        t3.daemon = True
        t3.start()
        self.__response_payload_worker = t3
        t4 = Thread(target=self.__send_msg_to_receiver_handler)
        t4.daemon = True
        t4.start()
        self.__send_packets_worker = t4


    def __recv_packets_worker(self):
        sleep_time = 0.2
        while not self.__stop_thread:
            if self.__go_back_handler.stored_buffer_size() > 0:
                tmp_payload = self.__go_back_handler.get_packet()
                self.__store_received_msg_in_buffer(tmp_payload)
                sleep_time = 0.2
            else:
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.3

    def __store_received_msg_in_buffer(self, payload: bytes):
        tmp_header = payload[:32].decode("utf-8").split()
        try:
            tmp_seq_nr = tmp_header[0]
            tmp_ack_nr = tmp_header[1]
            if int(tmp_ack_nr) == 0:
                tmp_msg = payload[32:]
                self.__write_in_receive_msg_buffer(int(tmp_seq_nr), tmp_msg)
            else:
                self.__write_in_response_msg_buffer(ack_nr=int(tmp_ack_nr))
        except IndexError:
            print("error header: ", tmp_header)

    def __generate_next_seg_nr(self, current_seg: int):
        if current_seg == 0:
            return 0
        return current_seg * self.__segment_size

    def __split_payload_in_seg(self, payload: bytes):
        if len(payload) > self.__segment_size:
            return payload[:self.__segment_size], payload[self.__segment_size:]
        return payload, b""

    def __prepare_msg_for_send(self, payload: bytes):
        count_packets: int = len(payload) // self.__segment_size
        if len(payload) % self.__segment_size > 0:
            count_packets += 1
        print("send ", count_packets, "x packets")
        payload_res: (bytes, bytes) = self.__split_payload_in_seg(payload)
        for i in range(0, count_packets):
            current_seg_nr: int = self.__generate_next_seg_nr(i)
            value: bytes = payload_res[0]
            self.__set_send_packets_to_queue(current_seg_nr, value)
            payload_res = self.__split_payload_in_seg(payload_res[1])

    def __create_msg_header_filler(self, size: int):
        if size <= 0:
            return b''
        tmp = b' '
        while len(tmp) != size:
            tmp = b'0' + tmp
        return tmp

    # header max size of 32byte
    def __create_msg_for_send(self, seq_nr: int, ack_nr: int, data: bytes):
        sequence_number: bytes = str(seq_nr).encode("utf-8")
        acknowledge_number: bytes = str(ack_nr).encode("utf-8")
        header: bytes = sequence_number + " ".encode("utf-8") + acknowledge_number + " ".encode("utf-8")
        len_header = len(header)
        header += self.__create_msg_header_filler(32 - len_header)
        return header + data

    def __send_msg_to_receiver_handler(self):
        sleep_time = 0.2
        current_send_window: dict = None
        while not self.__stop_thread:
            packets_to_send = self.__get_send_packets_from_queue()
            if packets_to_send:
                if self.__timeout_seq_nr is not None:
                    current_send_window = self.__get_send_packet_bundle_from_seq_nr(self.__timeout_seq_nr)
                    self.__send_window(current_send_window)
                    self.__timeout_seq_nr = None
                elif current_send_window is None or self.__has_ack_from_window_packets_arrived(current_send_window):
                    tmp_bundle: dict = {}
                    for key, value in packets_to_send.items():
                            if len(tmp_bundle) != 4:
                                tmp_bundle[key] = value
                    current_send_window = tmp_bundle.copy()
                    self.__send_window(current_send_window)

                sleep_time = 0.2
            else:
                current_send_window = None
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.3

    def __has_ack_from_window_packets_arrived(self, current_send_window: dict):
        response = self.__get_packets_timer()
        for key, value in current_send_window.items():
            if response[key] is False:
                return True
        return False

    def __get_send_packet_bundle_from_seq_nr(self, seq_nr):
        tmp_packets = self.__get_send_packets_from_queue()
        bundle_packets: dict = {}
        next_seq = 4
        for key, value in tmp_packets.items():
            if tmp_packets[seq_nr] == seq_nr or (next_seq > 0 and next_seq < 4):
                next_seq -= 1
                bundle_packets[seq_nr] = value
        return bundle_packets

    def __send_window(self, packets_to_send: dict):
        for key, value in packets_to_send.items():
            if self.__timeout_seq_nr is not None:
                break
            packet_to_send: bytes = self.__create_msg_for_send(key, 0, value)
            self.__push_timeout_worker_in_queue(key)
            self.connection.send(packet_to_send)
            print("send ", str(packet_to_send))

    def __push_timeout_worker_in_queue(self, seq_nr: int):
        self.__set_packets_timer(seq_nr=seq_nr, enable_timer=True)
        t = Timer(self.__send_timeout, self.__timeout_send_worker, args=[seq_nr])
        t.daemon = True
        self.__timeout_worker_queue.append(t)
        t.start()

    def __timeout_send_worker(self, seq_nr: int):
        if not self.__stop_thread:
            wait_for_response = self.__get_packets_timer()
            if wait_for_response[seq_nr]:
                self.__timeout_seq_nr = seq_nr
                # time.sleep(time)
        # check response or timeout

    def __response_payload_handler(self):
        sleep_time = 0.2
        while not self.__stop_thread:
            response_buffer: list = self.__read_from_response_buffer()
            if len(response_buffer) > 0:
                wait_for_response: dict = self.__get_packets_timer()
                for seq_nr in response_buffer:
                    if wait_for_response[seq_nr] and self.__timeout_seq_nr is not seq_nr:
                        self.__set_packets_timer(seq_nr, False)
                        if seq_nr == self.__get_lowest_seq_nr_send_packets():
                            self.__drop_send_packets_from_queue(seq_nr)
                sleep_time = 0.2
            else:
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.3

    def __get_lowest_seq_nr_send_packets(self):
        list_of_packets: list = list(self.__get_send_packets_from_queue())
        if len(list_of_packets) == 0:
            return None
        return min(list_of_packets)

    def __receiver_payload_handler(self):
        sleep_time = 0.2
        while not self.__stop_thread:
            # response to sender
            current_recv_packets = self.__read_from_receive_buffer()
            if len(current_recv_packets) > 0:
                while self.__get_lowest_seq_nr_recv_packets() is not None:
                    next_expected_seq_nr = self.__get_lowest_seq_nr_recv_packets()
                    payload = current_recv_packets[next_expected_seq_nr]
                    self.__send_ack_nr_response(next_expected_seq_nr)
                    self.__drop_key_from_receive_buffer(next_expected_seq_nr)
                    self.__append_final_msg(payload)
                sleep_time = 0.2
            else:
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.3

    def __get_lowest_seq_nr_recv_packets(self):
        list_of_packets: list = list(self.__read_from_receive_buffer())
        if len(list_of_packets) == 0:
            return None
        return min(list_of_packets)

    def __append_final_msg(self, msg: bytes):
        with self.__finale_recv_lock:
            self.__final_rev_msg += msg

    def __send_ack_nr_response(self, ack_nr):
        response_payload = self.__create_msg_for_send(ack_nr, ack_nr, "0".encode("utf-8"))
        self.connection.send(response_payload)
