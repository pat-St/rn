import time
from threading import Thread, Lock
from lossy_udp_socket import lossy_udp_socket
from lossy_packet_handler import lossy_packet_handler
from datetime import datetime, timedelta


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
    __window_size: int
    __send_timeout: int = 0.5

    # buffer for sender
    __send_packets: dict = {}
    __send_packets_lock: Lock = Lock()

    __send_packets_timer: dict = {}
    __send_packets_timer_lock: Lock = Lock()

    __response_from_receiver: set = set()
    __response_from_receiver_lock: Lock = Lock()
    __wait_for_response = False

    # buffer for receiver
    __receive_queue_msg: dict = {}
    __queue_write_lock: Lock = Lock()

    __stored_received_msg_for_read: dict = {}
    __stored_received_msg_for_read_lock: Lock = Lock()

    # worker threads
    __pull_payload_worker: Thread
    __receiver_payload_worker: Thread
    __response_payload_worker: Thread
    __send_packets_worker: Thread
    __send_timeout_worker: Thread
    # __timeout_worker_queue: deque = deque()
    __stop_thread: bool = False

    # received packets getter setter
    def __write_in_receive_msg_buffer(self, seq_nr: int, payload_msg: bytes):
        self.__queue_write_lock.acquire()
        self.__receive_queue_msg[seq_nr] = payload_msg
        self.__queue_write_lock.release()

    def __read_from_receive_buffer(self):
        self.__queue_write_lock.acquire()
        tmp = self.__receive_queue_msg.copy()
        self.__queue_write_lock.release()
        return tmp

    def __drop_key_from_receive_buffer(self, seq_nr: int):
        self.__queue_write_lock.acquire()
        if seq_nr in self.__receive_queue_msg:
            self.__receive_queue_msg.pop(seq_nr)
        self.__queue_write_lock.release()

    # received and response packtes getter setter
    def __set_stored_received_msg(self, seq_nr: int, payload: bytes):
        self.__stored_received_msg_for_read_lock.acquire()
        self.__stored_received_msg_for_read[seq_nr] = payload
        self.__stored_received_msg_for_read_lock.release()

    def __get_stored_received_msg(self):
        self.__stored_received_msg_for_read_lock.acquire()
        tmp = self.__stored_received_msg_for_read.copy()
        self.__stored_received_msg_for_read_lock.release()
        return tmp

    def __drop_stored_received_msg(self, seq_nr):
        self.__stored_received_msg_for_read_lock.acquire()
        self.__stored_received_msg_for_read.pop(seq_nr)
        self.__stored_received_msg_for_read_lock.release()

    # response getter setter
    def __write_in_response_msg_buffer(self, ack_nr: int):
        self.__response_from_receiver_lock.acquire()
        self.__response_from_receiver.add(ack_nr)
        self.__response_from_receiver_lock.release()

    def __read_from_response_buffer(self):
        self.__response_from_receiver_lock.acquire()
        tmp = self.__response_from_receiver.copy()
        self.__response_from_receiver_lock.release()
        return tmp

    def __drop_item_from_response_buffer(self, ack_nr: int):
        self.__response_from_receiver_lock.acquire()
        self.__response_from_receiver.remove(ack_nr)
        self.__response_from_receiver_lock.release()

    # send queue getter setter
    def __set_send_packets_to_queue(self, key: int, value: bytes):
        self.__send_packets_lock.acquire()
        self.__send_packets[key] = value
        self.__send_packets_lock.release()

    def __get_send_packets_from_queue(self):
        self.__send_packets_lock.acquire()
        tmp = self.__send_packets.copy()
        self.__send_packets_lock.release()
        return tmp

    def __drop_send_packets_from_queue(self, seq_nr):
        self.__send_packets_lock.acquire()
        self.__send_packets.pop(seq_nr)
        self.__send_packets_lock.release()

    # timer getter setter
    def __set_packets_timer(self, seq_nr: int, is_timeout, timestamp: datetime):
        self.__send_packets_timer_lock.acquire()
        self.__send_packets_timer[seq_nr] = (is_timeout, timestamp)
        self.__send_packets_timer_lock.release()

    def __get_packets_timer(self):
        self.__send_packets_timer_lock.acquire()
        tmp = self.__send_packets_timer.copy()
        self.__send_packets_timer_lock.release()
        return tmp

    def __drop_packets_timer(self, seq_nr):
        self.__send_packets_timer_lock.acquire()
        if seq_nr in self.__send_packets_timer:
            self.__send_packets_timer.pop(seq_nr)
        self.__send_packets_timer_lock.release()

    def __init__(self, ip_address: str, local_port: int, remote_port: int, drop_percent=0, window_size=4):
        self.__loc_port = local_port
        self.__rem_port = remote_port
        self.__des_ip = ip_address
        self.__window_size = window_size
        self.__send_packets = {}
        self.__receive_queue_msg = {}
        self.connection = lossy_udp_socket(self.__go_back_handler, local_port, (ip_address, remote_port), drop_percent)
        self.__start_worker_thread()

    def send(self, msg: bytes):
        # send window size packets parts in a loop
        self.__reset_buffer()
        self.__prepare_msg_for_send(msg)

    def recv(self, bytecount: int):
        while len(self.__read_from_receive_buffer()) != 0:
            time.sleep(0.5)
        received_msg_buffer = self.__get_stored_received_msg()
        return_msg = b""
        for key, value in received_msg_buffer.items():
            if key >= len(return_msg) or key == 0:
                return_msg += value
            self.__drop_stored_received_msg(key)
        bytecount = min(bytecount, len(return_msg))
        self.__reset_buffer()
        return return_msg[:bytecount]

    def stop(self):
        self.__stop_thread = True
        self.__send_packets_worker.join()
        self.__pull_payload_worker.join()
        self.__receiver_payload_worker.join()
        self.__send_timeout_worker.join()
        self.connection.stop()
        print("*************************************************")
        print("send buffer " + str(self.__send_packets))
        print("receive buffer " + str(self.__receive_queue_msg))
        print("timer " + str(self.__send_packets_timer))
        print("response buffer " + str(self.__response_from_receiver))
        print("stored buffer " + str(self.__stored_received_msg_for_read))
        print("*************************************************")

    def has_recv(self, bytescount: int):
        current_bytes: int = 0
        for key, value in self.__get_stored_received_msg().items():
            current_bytes += len(value)
        return current_bytes == bytescount

    def __start_worker_thread(self):
        t = Thread(target=self.__recv_packets_worker)
        t.daemon = True
        t.start()
        self.__pull_payload_worker = t
        t2 = Thread(target=self.__receiver_payload_handler)
        t2.daemon = True
        t2.start()
        self.__receiver_payload_worker = t2
        t4 = Thread(target=self.__send_msg_handler)
        t4.daemon = True
        t4.start()
        self.__send_packets_worker = t4
        t5 = Thread(target=self.__timeout_handler)
        t5.daemon = True
        self.__send_timeout_worker = t5
        t5.start()

    def __reset_buffer(self):
        self.__send_packets = {}
        self.__receive_queue_msg = {}
        self.__send_packets_timer = {}
        self.__response_from_receiver = set()
        self.__receive_queue_msg = {}
        self.__stored_received_msg_for_read = {}

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
                    sleep_time += 0.1

    def __store_received_msg_in_buffer(self, payload: bytes):
        tmp_header = payload[:32].decode("utf-8").split()
        try:
            tmp_seq_nr = tmp_header[0]
            tmp_ack_nr = tmp_header[1]
            tmp_msg: bytes = payload[32:]
            if len(tmp_msg) != 0:
                self.__write_in_receive_msg_buffer(int(tmp_seq_nr), tmp_msg)
                # print("receive buffer: " + str(tmp_seq_nr) + " payload: " + str(len(tmp_msg.decode("utf-8"))))
            else:
                self.__write_in_response_msg_buffer(ack_nr=int(tmp_ack_nr))
                # print("response buffer: " + str(tmp_ack_nr))
        except IndexError:
            print("error header: " + str(tmp_header))

    def __generate_next_seg_nr(self, current_seg: int):
        if current_seg == 0:
            return 0
        return current_seg * self.__segment_size

    def __split_payload_in_seg(self, payload: bytes):
        if len(payload) > self.__segment_size:
            assert len(payload) == len(payload[:self.__segment_size]) + len(payload[self.__segment_size:])
            return payload[:self.__segment_size], payload[self.__segment_size:]
        return payload, b""

    def __count_segment_packets(self, payload: bytes):
        count_packets: int = len(payload) // self.__segment_size
        if len(payload) % self.__segment_size > 0:
            count_packets += 1
        return count_packets

    def __prepare_msg_for_send(self, payload: bytes):
        payload_res: (bytes, bytes) = (b"", payload)
        current_seg_nr: int = 0
        while len(payload_res[1]) != 0:
            payload_res = self.__split_payload_in_seg(payload_res[1])
            value: bytes = payload_res[0]
            self.__set_send_packets_to_queue(current_seg_nr, value)
            if current_seg_nr == 0:
                current_seg_nr += 1
            current_seg_nr += len(value)

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

    def __send_msg_handler(self):
        sleep_time = 0.2
        current_send_window: dict = None
        while not self.__stop_thread:
            packets_to_send = self.__get_send_packets_from_queue()
            if len(packets_to_send) > 0:
                sleep_time = 0.2
                if current_send_window is not None:
                    if self.__check_packets_time_out():
                        current_send_window = self.__create_time_out_window_bundle()
                        # print("send :", str(list(current_send_window)))
                        self.__send_window(current_send_window)
                    else:
                        ack_for_current_window = self.__window_ack_response(current_send_window)
                        if len(ack_for_current_window) > 0:
                            self.__removed_ack_packets(
                                delete_full_window=(ack_for_current_window == current_send_window),
                                optional_windows=ack_for_current_window.copy())
                            if self.__get_lowest_seq_nr_send_packets() is not None:
                                current_send_window = self.__create_packet_bundle_from_seq_nr(
                                    self.__get_lowest_seq_nr_send_packets())
                                assert len(current_send_window) <= self.__window_size
                                # print("send :", str(list(current_send_window)))
                                self.__send_window(current_send_window)

                        # else:
                        #     time.sleep(0.1)
                else:
                    first_seq_nr = self.__get_lowest_seq_nr_send_packets()
                    current_send_window = self.__create_packet_bundle_from_seq_nr(first_seq_nr)
                    # assert len(current_send_window) <= self.__window_size
                    # print("send :", str(list(current_send_window)))
                    self.__send_window(current_send_window)
                    # time.sleep(sleep_time)
            else:
                current_send_window = None
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.1

    def __check_packets_time_out(self):
        for seq_nr, (time_out, _) in self.__get_packets_timer().items():
            if time_out:
                return True
        return False

    def __create_time_out_window_bundle(self):
        for seq_nr, (time_out, _) in self.__get_packets_timer().items():
            if time_out:
                return self.__create_packet_bundle_from_seq_nr(seq_nr)
        return {}

    def __window_ack_response(self, current_window: dict):
        tmp_response: dict = {}
        for seq_nr, value in current_window.items():
            if seq_nr in self.__read_from_response_buffer():
                tmp_response[seq_nr] = value
        return tmp_response

    def __removed_ack_packets(self, delete_full_window=False, optional_windows: dict = {}):
        if delete_full_window:
            for key in list(optional_windows):
                self.__drop_send_packets_from_queue(key)
                self.__drop_item_from_response_buffer(key)
                self.__drop_packets_timer(key)

        # delete already ack response
        tmp_response_set = self.__read_from_response_buffer()
        for seq_nr in tmp_response_set:
            if self not in self.__get_send_packets_from_queue():
                self.__drop_item_from_response_buffer(seq_nr)
        response_is_time_out = self.__get_packets_timer()
        tmp_response_set = self.__read_from_response_buffer()

        # clean timeout for ack packets
        for seq_nr in tmp_response_set:
            self.__drop_item_from_response_buffer(seq_nr)
            if seq_nr in response_is_time_out:
                if response_is_time_out[seq_nr][0] is False:
                    self.__drop_packets_timer(seq_nr)
            if seq_nr == self.__get_lowest_seq_nr_send_packets():
                self.__drop_send_packets_from_queue(seq_nr)

    def __create_packet_bundle_from_seq_nr(self, seq_nr):
        tmp_bundle: dict = {}
        count_at_this_point = False
        for key, value in self.__get_send_packets_from_queue().items():
            if count_at_this_point and len(tmp_bundle) < self.__window_size:
                tmp_bundle[key] = value
            if key == seq_nr:
                tmp_bundle[key] = value
                count_at_this_point = True
        return tmp_bundle

    def __send_window(self, packets_to_send: dict):
        for key, value in packets_to_send.items():
            packet_to_send: bytes = self.__create_msg_for_send(key, 0, value)
            self.__push_timeout_worker_in_queue(key)
            self.connection.send(packet_to_send)
            # print("send: " + str(key) + ": " + str(len(value)))

    def __push_timeout_worker_in_queue(self, seq_nr: int):
        self.__set_packets_timer(seq_nr=seq_nr, is_timeout=False, timestamp=datetime.utcnow())

    def __get_lowest_seq_nr_send_packets(self):
        list_of_packets: list = list(self.__get_send_packets_from_queue())
        if len(list_of_packets) == 0:
            return None
        return min(list_of_packets)

    def __timeout_handler(self):
        sleep_time = 0.2
        while not self.__stop_thread:
            wait_for_response: dict = self.__get_packets_timer()
            if len(wait_for_response) > 0:
                sleep_time = 0.2
                for seq_nr, (already_time_out, timestamp) in wait_for_response.items():
                    current_timestamp = datetime.utcnow()
                    if already_time_out is False:
                        if (current_timestamp - timestamp).seconds > self.__send_timeout:
                            self.__set_packets_timer(seq_nr=seq_nr, is_timeout=True, timestamp=timestamp)
            else:
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.1

    def __receiver_payload_handler(self):
        sleep_time = 0.2
        while not self.__stop_thread:
            sleep_time = 0.2
            # response to sender
            if len(self.__read_from_receive_buffer()) > 0:
                current_response = self.__read_from_receive_buffer()
                for seq_nr, value in current_response.items():
                    # if seq_nr is not None:
                    self.__send_ack_nr_response(seq_nr)
                    self.__set_stored_received_msg(seq_nr, value)
                    self.__drop_key_from_receive_buffer(seq_nr)
                    # print("response: " + str(seq_nr))
            else:
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.1

    def __get_lowest_seq_nr_recv_packets(self):
        list_of_packets: list = list(self.__read_from_receive_buffer())
        if len(list_of_packets) == 0:
            return None
        return min(list_of_packets)

    def __send_ack_nr_response(self, ack_nr):
        response_payload = self.__create_msg_for_send(ack_nr, ack_nr, b"")
        self.connection.send(response_payload)
        # print("response", str(response_payload.split()[:3]))
