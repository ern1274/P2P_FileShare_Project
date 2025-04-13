import os
import socket
import threading
import time
import zlib


def make_checksum(data):
    """
    Forms checksum from data using crc32 function from zlib library

    :param data: sequence of Bytes to calculate checksum
    :type data: Bytes
    :return: checksum of data
    :rtype: Bytes
    """
    return zlib.crc32(data).to_bytes(8,'big',signed=True)

def make_sender_payload(seq_num, msg, file_id):
    """
    Forms packet payload by encoding sequence number and message of packet

    :param seq_num: int to convert to bytes
    :type seq_num: int
    :param msg: characters to encode
    :type msg: String
    :return: payload, sequence of bytes containing seq_num and msg
    :rtype: Bytes
    """

    id_bytes = file_id.encode()
    id_length = len(id_bytes).to_bytes(4, byteorder='big')
    seq_bytes = seq_num.to_bytes(4, byteorder='big', signed=True)
    msg_bytes = msg.encode()
    payload = id_length + id_bytes + seq_bytes + msg_bytes
    return payload

def convert_receiver_payload(data):
    """
    Decodes packet payload to retrieve sequence number and message of packet

    :param data: sequence of Bytes to decode
    :type data: Bytes
    :return: send_seq, sequence number of packet
    :rtype: Bytes
    :return: msg, data from packet
    :rtype: String
    """
    id_length = int.from_bytes(data[:4], byteorder='big', signed=True)
    file_id = data[4:4+id_length].decode()
    send_seq = int.from_bytes(data[4+id_length:8+id_length], byteorder='big', signed=True)
    msg = data[8+id_length:].decode()
    return send_seq, msg

def convert_ack_payload(data):
    """
    Parses a receiver ACK payload (just a sequence number + "ACK")

    :param data: sequence of bytes
    :return: seq_num, message
    """
    seq_num = int.from_bytes(data[:4], byteorder='big', signed=True)
    try:
        msg = data[4:].decode()
    except UnicodeDecodeError:
        print(f"[Error] Failed to decode ACK payload: {data[4:]}")
        msg = "<INVALID>"
    return seq_num, msg

def verify_integrity(sent_chksum, data):
    """
    Verifies checksum from received packet

    :param sent_chksum: received checksum with length of 8 bytes
    :type sent_chksum: Bytes
    :param data: sequence of bytes to calculate checksum with
    :type data: Bytes
    :return: if sent_chksum is the exact same as calculated checksum
    :rtype: Boolean
    """
    chksum = make_checksum(data)
    return sent_chksum == chksum

def make_packet(seq_num, msg, file_id):
    """
    Forms packet by combining calculated checksum and formed payload

    :param seq_num: int to convert to bytes
    :type seq_num: int
    :param msg: characters to encode
    :type msg: String
    :return: payload, sequence of bytes containing seq_num and msg
    :rtype: Bytes
    """
    payload = make_sender_payload(seq_num, msg, file_id)
    chksum = make_checksum(payload)
    return chksum+payload

class Sender:
    """
    Sender, a class with defined behavior to send data to a receiver

    Attributes:
        packets: Array of 3 object arrays containing:
        [formed byte packet, boolean ack, Timeout retransmission thread]

        soc: socket that sender uses to send data over
        ip: ip address to send data to
        port: port number to send data to
        base_seq: the lowest sequence number to index by
    """
    packets = None
    def __init__(self, soc, ip, port, file_id):
        self.soc = soc
        self.ip = ip
        self.port = port
        self.base_seq = 1
        self.file_id = file_id
        self.packets = []  # Each entry: [packet_bytes, acked (bool), timer]

    def send_pkt(self, seq_num):
        """
        Retransmits packet after timeout by thread.Timer and resets timeout

        :param seq_num: sequence number to retransmit
        :type seq_num: int
        """
        idx = seq_num - self.base_seq
        if idx < 0 or idx >= len(self.packets):
            return

        print(f"[Sender] Retransmitting {seq_num} to {self.ip}:{self.port}")
        pkt, acked, _ = self.packets[idx]
        self.soc.sendto(pkt, (self.ip, self.port))

        # Restart retransmission timer
        timer = threading.Timer(5.0, self.send_pkt, [seq_num])
        self.packets[idx][2] = timer
        timer.start()

    def arrange_pkts(self, data):
        """
        Given chunks of data, populate each entry of Sender packets with
        packet, False (for acknowledgement), thread.Timer for timeout and retransmit

        :param data: array of chunks of data
        :type data: Array of Strings
        """
        self.packets = []
        seq_num = self.base_seq
        for pkt in data:
            packet = make_packet(seq_num, pkt, self.file_id)
            self.packets.append([packet, False, None])  # No timer yet
            seq_num += 1


    def find_recv_base_window(self, window_size):
        """
        Given window size and Sender packets,
        find the closest unacknowledged packet and calculate the window

        :param window_size: size of window
        :type window_size: int
        """
        for i in range(len(self.packets)):
            if not self.packets[i][1]:  # Not ACKed
                end = min(i + window_size - 1, len(self.packets) - 1)
                return i, end
        return None, None

    def make_packets(self, exch_path, chunk_size):
        """
        Forms packets from file by splitting file into chunks

        :param file_name: String containing name of file to send
        :type file_name: String
        :param chunk_size: number of characters to fit in a chunk from file
        :type chunk_size: int
        :return: pkts, array of character chunks from file
        :rtype: Array
        """
        file = open(exch_path, 'r')
        content = file.read()
        file.close()
        pkts = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
        #print(pkts)
        return pkts

    def setup_exchange(self, exch_path):
        print(f"[Sender] Starting file exchange for {exch_path}")
        self.arrange_pkts(self.make_packets(exch_path, 24))
        # Add process to run sender to distinguish request number
        self.run_sender()


    def run_sender(self):
        """
        Sends packets using Selective Repeat. Only creates timers once per packet.
        """
        win_size = max(1, len(self.packets) // 4)
        sent = set()

        while True:
            #print("Still alive")
            recv_base, win_end = self.find_recv_base_window(win_size)
            if recv_base is None:
                break  # All packets acknowledged

            for i in range(recv_base, win_end + 1):
                if not self.packets[i][1] and i not in sent:
                    pkt = self.packets[i][0]
                    self.soc.sendto(pkt, (self.ip, self.port))

                    # Set and start retransmission timer
                    timer = threading.Timer(5.0, self.send_pkt, [self.base_seq + i])
                    self.packets[i][2] = timer
                    timer.start()
                    sent.add(i)
                    time.sleep(0.2)

            # Listen for ACKs
            self.soc.settimeout(4)
            try:
                while True:
                    data, _ = self.soc.recvfrom(4096)
                    chksum, payload = data[:8], data[8:]
                    
                    if verify_integrity(chksum, payload):
                        recv_seq, ack = convert_ack_payload(payload)
                        if ack.strip() != "ACK":
                            print(f"[Sender] Ignored non-ACK message: {ack}")
                            continue

                        print(f"[Sender] Received ACK for packet {recv_seq}")
                        idx = recv_seq - self.base_seq
                        if 0 <= idx < len(self.packets):
                            self.packets[idx][1] = True  # Mark packet as acked
                            # Cancel the timer if it's still running
                            timer = self.packets[idx][2]
                            if timer and timer.is_alive():
                                timer.cancel()
            except socket.timeout:
                # Instead of continue, we break out of the "while True" loop
                pass
            finally:
                self.soc.settimeout(None)

        # Send FIN and wait for ACK
        max_retries = 5
        retries = 0
        while retries < max_retries:
            fin_pkt = make_packet(-1, 'FIN', self.file_id)
            self.soc.sendto(fin_pkt, (self.ip, self.port))
            print("[Sender] Sent FIN, waiting for final ACK...")
            try:
                self.soc.settimeout(10)
                data, _ = self.soc.recvfrom(4096)
                chksum, payload = data[:8], data[8:]
                
                if verify_integrity(chksum, payload):
                    recv_seq, ack = convert_ack_payload(payload)
                    if ack.strip() == "ACK" and recv_seq == -1:
                        print("[Sender] Received final ACK. Transfer complete.")
                        break
            except socket.timeout:
                print(f"[Sender] FIN retry timed out ({retries+1}/{max_retries})")
                retries += 1
            finally:
                self.soc.settimeout(None)

        print("[Sender] Exiting FIN handshake sequence.")
