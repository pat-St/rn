import time
import copy
from threading import Thread, Lock
from lossy_udp_socket import lossy_udp_socket
from lossy_packet_handler import lossy_packet_handler
from datetime import datetime, timedelta


class go_back_n_socket:

    def __init__(self, ip_address: str, local_port: int, remote_port: int, drop_percent=0, window_size=4, send_packet_size: int=1500):
        # connection config
        self.__des_ip: str = ip_address
        self.__loc_port: int = local_port
        self.__rem_port: int = remote_port

        # udp socket
        # udp packet handler
        self.__go_back_handler = lossy_packet_handler()

        # sending config
        self.__segment_size: int = send_packet_size - 32
        self.__window_size: int = window_size
        self.__send_timeout: int = 2

        # buffer for sender
        self.__send_packets: dict = {}
        self.__send_packets_lock: Lock = Lock()

        self.__send_packets_timer: dict = {}
        self.__send_packets_timer_lock: Lock = Lock()

        self.__response_from_receiver: set = set()
        self.__response_from_receiver_lock: Lock = Lock()

        # buffer for receiver
        self.__receive_queue_msg: dict = {}
        self.__queue_write_lock: Lock = Lock()

        self.__stored_received_msg_for_read: dict = {}
        self.__stored_received_msg_for_read_lock: Lock = Lock()

        # worker threads
        self.__pull_payload_worker: Thread
        self.__receiver_payload_worker: Thread
        self.__response_payload_worker: Thread
        self.__send_packets_worker: Thread
        self.__send_timeout_worker: Thread
        self.__stop_thread: bool = False

        self.connection = lossy_udp_socket(self.__go_back_handler, local_port, (ip_address, remote_port), drop_percent, send_packet_size)
        self.__start_worker_thread()

    # received packets getter setter
    def __write_in_receive_msg_buffer(self, seq_nr: int, payload_msg: bytes):
        self.__queue_write_lock.acquire()
        self.__receive_queue_msg[seq_nr] = payload_msg
        self.__queue_write_lock.release()

    def __read_from_receive_buffer(self):
        self.__queue_write_lock.acquire()
        tmp = copy.deepcopy(self.__receive_queue_msg)
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
        tmp = copy.deepcopy(self.__stored_received_msg_for_read)
        self.__stored_received_msg_for_read_lock.release()
        return tmp

    def __drop_stored_received_msg(self, seq_nr):
        self.__stored_received_msg_for_read_lock.acquire()
        if seq_nr in self.__stored_received_msg_for_read:
            self.__stored_received_msg_for_read.pop(seq_nr)
        self.__stored_received_msg_for_read_lock.release()

    # response getter setter
    def __write_in_response_msg_buffer(self, ack_nr: int):
        self.__response_from_receiver_lock.acquire()
        self.__response_from_receiver.add(ack_nr)
        self.__response_from_receiver_lock.release()

    def __read_from_response_buffer(self):
        self.__response_from_receiver_lock.acquire()
        tmp = copy.deepcopy(self.__response_from_receiver)
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
        tmp = copy.deepcopy(self.__send_packets)
        self.__send_packets_lock.release()
        return tmp

    def __drop_send_packets_from_queue(self, seq_nr):
        self.__send_packets_lock.acquire()
        if seq_nr in self.__send_packets:
            self.__send_packets.pop(seq_nr)
        self.__send_packets_lock.release()

    # timer getter setter
    def __set_packets_timer(self, seq_nr: int, is_timeout, timestamp: datetime):
        self.__send_packets_timer_lock.acquire()
        self.__send_packets_timer[seq_nr] = (is_timeout, timestamp)
        self.__send_packets_timer_lock.release()

    def __get_packets_timer(self):
        self.__send_packets_timer_lock.acquire()
        tmp = copy.deepcopy(self.__send_packets_timer)
        self.__send_packets_timer_lock.release()
        return tmp

    def __drop_packets_timer(self, seq_nr):
        self.__send_packets_timer_lock.acquire()
        if seq_nr in self.__send_packets_timer:
            self.__send_packets_timer.pop(seq_nr)
        self.__send_packets_timer_lock.release()

    def send(self, msg: bytes):
        #self.__reset_buffer()
        self.__prepare_msg_for_send(msg)

    def recv(self, byte_count: int):
        while len(self.__read_from_receive_buffer()) != 0:
            time.sleep(0.5)
        received_msg_buffer = self.__get_stored_received_msg()
        return_msg = b""
        sorted_received_seq_nr = sorted(received_msg_buffer)
        for key in sorted_received_seq_nr:
            if key in self.__get_stored_received_msg():
                return_msg += self.__get_stored_received_msg()[key]
                self.__drop_stored_received_msg(key)
        byte_count = min(byte_count, len(return_msg))
        self.__reset_buffer()
        return return_msg[:byte_count]

    def stop(self):
        self.__stop_thread = True
        self.__send_packets_worker.join()
        self.__pull_payload_worker.join()
        self.__receiver_payload_worker.join()
        self.__send_timeout_worker.join()
        self.connection.stop()
        self.connection = None

    def has_recv(self, bytescount: int):
        current_bytes: int = 0
        for key, value in self.__get_stored_received_msg().items():
            current_bytes = current_bytes + len(value)
        return current_bytes == bytescount

    def get_recv_bytes(self):
        current_bytes: int = 0
        for key, value in self.__get_stored_received_msg().items():
            current_bytes = current_bytes + len(value)
        return current_bytes

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
        self.__send_packets.clear()
        self.__receive_queue_msg.clear()
        self.__send_packets_timer.clear()
        self.__response_from_receiver.clear()
        self.__receive_queue_msg.clear()
        self.__stored_received_msg_for_read.clear()

    def __recv_packets_worker(self):
        sleep_time: float = 0.2
        while not self.__stop_thread:
            if self.__go_back_handler.stored_buffer_size() > 0:
                tmp_payload = self.__go_back_handler.get_packet()
                self.__store_received_msg_in_buffer(tmp_payload)
                sleep_time = 0.2
            else:
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time = sleep_time + 0.1

    def __store_received_msg_in_buffer(self, payload: bytes):
        tmp_header: bytes = payload[:32].decode("utf-8").split()
        try:
            tmp_seq_nr = tmp_header[0]
            tmp_ack_nr = tmp_header[1]
            tmp_msg: bytes = payload[32:]
            if len(tmp_msg) != 0:
                self.__write_in_receive_msg_buffer(int(tmp_seq_nr), tmp_msg)
            else:
                self.__write_in_response_msg_buffer(ack_nr=int(tmp_ack_nr))
        except IndexError:
            print("error header: " + str(tmp_header))

    def __split_payload_in_seg(self, payload: bytes):
        if len(payload) > self.__segment_size:
            return payload[:self.__segment_size], payload[self.__segment_size:]
        return payload, b""

    def __count_segment_packets(self, payload: bytes):
        count_packets: int = len(payload) // self.__segment_size
        if len(payload) % self.__segment_size > 0:
            count_packets = count_packets + 1
        return count_packets

    def __prepare_msg_for_send(self, payload: bytes):
        payload_res: (bytes, bytes) = (b"", payload)
        current_seg_nr: int = 0
        while len(payload_res[1]) != 0:
            payload_res = self.__split_payload_in_seg(payload_res[1])
            value: bytes = payload_res[0]
            self.__set_send_packets_to_queue(current_seg_nr, value)
            current_seg_nr = current_seg_nr + self.__segment_size

    def __send_msg_header_filler(self, size: int):
        if size <= 0:
            return b''
        tmp: bytes = b' '
        while len(tmp) != size:
            tmp = b'0' + tmp
        return tmp

    # header max size of 32byte
    def __create_msg_for_send(self, seq_nr: int, ack_nr: int, data: bytes):
        sequence_number: bytes = str(seq_nr).encode("utf-8")
        acknowledge_number: bytes = str(ack_nr).encode("utf-8")
        header: bytes = sequence_number + " ".encode("utf-8") + acknowledge_number + " ".encode("utf-8")
        header += self.__send_msg_header_filler(32 - len(header))
        return header + data

    def __send_msg_handler(self):
        sleep_time: float = 0.2
        current_send_window: dict = None
        while not self.__stop_thread:
            packets_to_send = self.__get_send_packets_from_queue()
            if len(packets_to_send) > 0:
                sleep_time = 0.2
                if current_send_window is not None:
                    if self.__check_packets_time_out():
                        current_send_window = self.__create_time_out_window_bundle()
                        self.__send_window(current_send_window)
                    if len(self.__window_ack_response(current_send_window)) > 0:
                        self.__clean_response_before_remove()
                        self.__remove_ack_packets()
                        lowest_send_seq_nr = self.__get_lowest_seq_nr_send_packets()
                        if lowest_send_seq_nr is not None:
                            current_send_window = self.__create_packet_bundle_from_seq_nr(lowest_send_seq_nr)
                            self.__send_window(current_send_window)
                    else:
                        self.__clean_response_before_remove()
                        time.sleep(0.1)
                else:
                    first_seq_nr = self.__get_lowest_seq_nr_send_packets()
                    current_send_window = self.__create_packet_bundle_from_seq_nr(first_seq_nr)
                    self.__send_window(current_send_window)
                time.sleep(sleep_time)
            else:
                current_send_window = None
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time = sleep_time + 0.1

    def __check_packets_time_out(self):
        for seq_nr, (time_out, _) in self.__get_packets_timer().items():
            if time_out is True:
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

    def __clean_response_before_remove(self):
        tmp_response_set = self.__read_from_response_buffer()
        for seq_nr in tmp_response_set:
            send_queue_keys: list = sorted(self.__get_send_packets_from_queue())
            if seq_nr not in send_queue_keys:
                self.__drop_item_from_response_buffer(seq_nr)
                self.__drop_packets_timer(seq_nr)

    def __remove_ack_packets(self):
        response_is_time_out = self.__get_packets_timer()
        tmp_response_set = self.__read_from_response_buffer()
        for seq_nr in tmp_response_set:
            self.__drop_item_from_response_buffer(seq_nr)
            if seq_nr in response_is_time_out:
                self.__drop_packets_timer(seq_nr)
            if seq_nr in self.__get_send_packets_from_queue():
                self.__drop_send_packets_from_queue(seq_nr)

    def __create_packet_bundle_from_seq_nr(self, seq_nr):
        tmp_bundle: dict = {}
        count_at_this_point = False
        for key, value in self.__get_send_packets_from_queue().items():
            if count_at_this_point and len(tmp_bundle) <= self.__window_size:
                tmp_bundle[key] = value
            if key == seq_nr:
                tmp_bundle[key] = value
                count_at_this_point = True
        return tmp_bundle

    def __send_window(self, packets_to_send: dict):
        for key, value in packets_to_send.items():
            packet_to_send: bytes = self.__create_msg_for_send(key, 0, value)
            self.__add_send_packet_to_timeout_list(key)
            self.connection.send(packet_to_send)

    def __add_send_packet_to_timeout_list(self, seq_nr: int, is_time_out: bool = False, time_stamp=datetime.utcnow()):
        self.__set_packets_timer(seq_nr=seq_nr, is_timeout=is_time_out, timestamp=time_stamp)

    def __get_lowest_seq_nr_send_packets(self):
        if len(self.__get_send_packets_from_queue()) == 0:
            return None
        return min(sorted(self.__get_send_packets_from_queue()))

    def __timeout_handler(self):
        sleep_time: float = 0.2
        while not self.__stop_thread:
            wait_for_response: dict = self.__get_packets_timer()
            if len(wait_for_response) > 0:
                sleep_time = 0.2
                for seq_nr, (already_time_out, timestamp) in wait_for_response.items():
                    if already_time_out is False:
                        current_timestamp = datetime.utcnow()
                        if (current_timestamp - timestamp).seconds >= self.__send_timeout:
                            if seq_nr in self.__get_packets_timer():
                                self.__add_send_packet_to_timeout_list(seq_nr=seq_nr, is_time_out=True,
                                                                       time_stamp=timestamp)
                time.sleep(sleep_time)
            else:
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.1

    def __receiver_payload_handler(self):
        sleep_time: float = 0.2
        while not self.__stop_thread:
            sleep_time = 0.2
            if len(self.__read_from_receive_buffer()) > 0:
                buffer_received: dict = self.__read_from_receive_buffer()
                for seq_nr, value in buffer_received.items():
                    self.__drop_key_from_receive_buffer(seq_nr)
                    if seq_nr not in self.__get_stored_received_msg():
                        self.__set_stored_received_msg(seq_nr, value)
                    current_response = self.__get_order_stored_highest_bytes()
                    if current_response is not None:
                        if seq_nr <= current_response:
                            self.__send_ack_nr_response(seq_nr)
                        else:
                            self.__send_ack_nr_response(current_response)
                    else:
                        time.sleep(0.2)
            else:
                time.sleep(sleep_time)
                if sleep_time < 2.0:
                    sleep_time += 0.1

    def __get_lowest_seq_nr_recv_packets(self):
        list_of_packets: list = list(self.__read_from_receive_buffer())
        if len(list_of_packets) == 0:
            return None
        return min(list_of_packets)

    # highest stored seq_nr
    def __get_highest_stored_seq_nr(self):
        list_of_packets: list = list(self.__get_stored_received_msg())
        if len(list_of_packets) == 0:
            return None
        return max(list_of_packets)

    # does strange things
    def __get_order_stored_highest_bytes(self):
        list_of_packets: dict = self.__get_stored_received_msg()
        seq_sort: list = sorted(list_of_packets)
        if seq_sort == 0:
            return None
        if seq_sort[0] != 0:
            return None
        else:
            next_seq_nr = 0
            current_seq_nr = 0
            for seq_nr in seq_sort:
                if next_seq_nr == 0:
                    next_seq_nr = seq_nr + len(list_of_packets[seq_nr])
                else:
                    if seq_nr == next_seq_nr:
                        current_seq_nr = seq_nr
                        next_seq_nr = seq_nr + len(list_of_packets[seq_nr])
                    else:
                        return current_seq_nr
            return current_seq_nr

    def __send_ack_nr_response(self, ack_nr):
        response_payload = self.__create_msg_for_send(ack_nr, ack_nr, b"")
        self.connection.send(response_payload)
