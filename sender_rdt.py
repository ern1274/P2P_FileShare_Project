import threading
import time
import zlib



def make_checksum(data):
    """Forms checksum from data using crc32 function from zlib library

    :param data: sequence of Bytes to calculate checksum
    :type data: Bytes
    :return: checksum of data
    :rtype: Bytes
    """
    return zlib.crc32(data).to_bytes(8,'big',signed=True)

def make_sender_payload(seq_num, msg):
    """Forms packet payload by encoding sequence number and message of packet

    :param seq_num: int to convert to bytes
    :type seq_num: int
    :param msg: characters to encode
    :type msg: String
    :return: payload, sequence of bytes containing seq_num and msg
    :rtype: Bytes
    """
    seq_bytes = seq_num.to_bytes(4, byteorder='big', signed=True)
    msg_bytes = msg.encode()
    payload = seq_bytes + msg_bytes
    return payload

def convert_receiver_payload(data):
    """Decodes packet payload to retrieve sequence number and message of packet

    :param data: sequence of Bytes to decode
    :type data: Bytes
    :return: send_seq, sequence number of packet
    :rtype: Bytes
    :return: msg, data from packet
    :rtype: String
    """
    send_seq = int.from_bytes(data[:4], byteorder='big', signed=True)
    msg = data[4:].decode()
    return send_seq, msg

def verify_integrity(sent_chksum, data):
    """Verifies checksum from received packet

    :param sent_chksum: received checksum with length of 8 bytes
    :type sent_chksum: Bytes
    :param data: sequence of bytes to calculate checksum with
    :type data: Bytes
    :return: if sent_chksum is the exact same as calculated checksum
    :rtype: Boolean
    """
    chksum = make_checksum(data)
    return sent_chksum == chksum

def make_packet(seq_num, msg):
    """Forms packet by combining calculated checksum and formed payload

    :param seq_num: int to convert to bytes
    :type seq_num: int
    :param msg: characters to encode
    :type msg: String
    :return: payload, sequence of bytes containing seq_num and msg
    :rtype: Bytes
    """
    payload = make_sender_payload(seq_num, msg)
    chksum = make_checksum(payload)
    return chksum+payload

class Sender:
    """Sender, a class with defined behavior to send data to a receiver

    Attributes:
        packets: Array of 3 object arrays containing:
        [formed byte packet, boolean ack, Timeout retransmission thread]

        soc: socket that sender uses to send data over
        ip: ip address to send data to
        port: port number to send data to
        base_seq: the lowest sequence number to index by
    """
    packets = None
    def __init__(self, soc, ip, port):
        self.soc = soc
        self.ip = ip
        self.port = port
        self.base_seq = 1

    def send_pkt(self, seq_num):
        """Retransmits packet after timeout by thread.Timer and resets timeout

        :param seq_num: sequence number to retransmit
        :type seq_num: int
        """
        print("Retransmitting " + str(seq_num) + " to " + str(self.ip) + " : "+ str(self.port))
        self.soc.sendto(self.packets[seq_num - self.base_seq][0], (self.ip, self.port))
        self.packets[seq_num- self.base_seq][2] = threading.Timer(5.0, self.send_pkt, [seq_num])
        self.packets[seq_num- self.base_seq][2].start()

    def arrange_pkts(self, data):
        """Given chunks of data, populate each entry of Sender packets with
        packet, False (for acknowledgement), thread.Timer for timeout and retransmit

        :param data: array of chunks of data
        :type data: Array of Strings
        """
        self.packets = []
        seq_num = self.base_seq
        for pkt in data:
            #print(pkt)
            packet = make_packet(seq_num, pkt)
            self.packets.append([packet, False,
                                 threading.Timer(5.0, self.send_pkt, [seq_num])])
            seq_num += 1


    def find_recv_base_window(self, window_size):
        """Given window size and Sender packets,
        find the closest unacknowledged packet and calculate the window

        :param window_size: size of window
        :type window_size: int
        """
        for i in range(len(self.packets)):
            if not self.packets[i][1]:
                if i + window_size >= len(self.packets):
                    #print("returning: " + str(i) + " and " + str(len(self.packets)-1))
                    return i, len(self.packets)-1
                else:
                    #print("returning: " + str(i) + " and " + str(i + window_size))
                    return i, i + window_size
        return None, None

    def make_packets(self, exch_path, chunk_size):
        """Forms packets from file by splitting file into chunks

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
        self.arrange_pkts(self.make_packets(exch_path, 24))
        self.run_sender()


    def run_sender(self):
        """This function assumes Sender packets to be populated,
        through arrange_packets. Sends packets in a Selective Repeat fashion

        """
        win_size = int(len(self.packets) / 4)
        recv_base, win_end = self.find_recv_base_window(win_size)
        while recv_base is not None:
            for i in range(recv_base, win_end+1):
                if not (self.packets[i][2].finished.is_set() or self.packets[i][2].is_alive()):
                    print("Transmitting " + str(self.base_seq + i))
                    payload = self.packets[i][0]
                    self.soc.sendto(payload, (self.ip, self.port))
                    self.packets[i][2].start()
                    time.sleep(0.2)

            self.soc.settimeout(1)
            try:
                while True:
                    data, address = self.soc.recvfrom(4096)
                    chksum = data[:8]
                    data = data[8:]
                    if verify_integrity(chksum, data):
                        recv_seq, ack = convert_receiver_payload(data)
                        print('Client confirming packet ' + str(recv_seq))
                        if not self.packets[recv_seq - self.base_seq][1]:
                            self.packets[recv_seq - self.base_seq][1] = True
                        self.packets[recv_seq - self.base_seq][2].cancel()
                        #self.packets[recv_seq - self.base_seq][2].join()
            except:
                self.soc.settimeout(None)
                recv_base, win_end = self.find_recv_base_window(win_size)
                continue

        while True:
            payload = make_packet(-1,'FIN')
            self.soc.sendto(payload, (self.ip, self.port))
            self.soc.settimeout(10)
            try:
                data, address = self.soc.recvfrom(4096)
                chksum = data[:8]
                data = data[8:]
                if verify_integrity(chksum, data):
                    recv_seq, ack = convert_receiver_payload(data)
                    if recv_seq == -1:
                        break
            except:
                continue


        print("ACKed end of data, now exiting")
        return
