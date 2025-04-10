
import threading
import zlib

def make_checksum(data):
    """Forms checksum from data using crc32 function from zlib library

    :param data: sequence of Bytes to calculate checksum
    :type data: Bytes
    :return: checksum of data
    :rtype: Bytes
    """
    return zlib.crc32(data).to_bytes(8,'big',signed=True)

def make_receiver_payload(seq_num, msg):
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

def convert_sender_payload(data):
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
    payload = make_receiver_payload(seq_num, msg)
    chksum = make_checksum(payload)
    return chksum+payload

class Receiver:
    """Receiver, a class with defined behavior to receive data from a sender

    Attributes:
        packets: Array of received decoded data

        soc: socket that receiver uses to bind and receive data over
        ip: ip address to receive data from
        port: port number to receive data from
        base_seq: the lowest sequence number to index by
        max_seq: the highest sequence number known to the receiver
    """
    packets = []
    base_seq = -1
    max_seq = -1


    timeout = None

    def __init__(self, soc):
        self.soc = soc

    # Rebase and add pkt function will change base_seq and max_seq
    def add_packet(self, seq_num,data, expand_pkts):
        """Given seq_num, data add data to Receiver packets,
        if expand_pkts is True, seq_num is bigger than self.max_seq.
        In this event, add entries until seq_num is reached and input data

        :param seq_num: sequence number of data packet
        :type seq_num: int
        :param data: decoded data
        :type data: String
        :param expand_pkts: true if seq_num >= self.max_seq
        :type expand_pkts: Boolean
        """
        if expand_pkts:
            until_seq = seq_num - self.max_seq
            for i in range(until_seq):
                self.packets.append(None)
            self.max_seq = seq_num
        self.packets[seq_num - self.base_seq] = data
        return

    def rebase_packets(self, seq_num, data):
        """Given seq_num, data add data to Receiver packets,
        this function is called if seq_num is smaller than self.base_seq
        where self.packets is modified to make seq_num the new self.base_seq
        and populate decoded data in self.packets

        :param seq_num: sequence number of data packet
        :type seq_num: int
        :param data: decoded data
        :type data: String
        """
        until_base = self.base_seq - seq_num
        for i in range(until_base):
            self.packets.insert(0, None)
        self.base_seq = seq_num
        self.packets[self.base_seq - self.base_seq] = data
        return

    def get_packets(self):
        """Retrieves Receiver object packets

        :return: self.packets
        """
        return self.packets

    def clear_packets(self):
        """Clears Receiver object packets to emptiness

        """
        self.packets.clear()
        return


    def set_timeout(self):
        self.timeout = 1
        print("Timeout was changed")


    def execute_request(self, peer_addr, peer_msg, file_name,exch_data_queue):
        payload = peer_msg.encode()
        chksum = make_checksum(payload)
        self.soc.sendto(chksum + payload, peer_addr)
        self.run_receiver(exch_data_queue)
        print(self.packets)
        # add save to file


    def listen_for_requests(self,exch_req_queue,exch_data_queue):
        """Waits for request from other peers from self.soc, verifies data and verifies requests
        Runs as long as the p2p_command is running
        """
        try:
            while True:
                #print('Listening')
                data, address = self.soc.recvfrom(4096)
                chksum = data[:8]
                data = data[8:]
                if verify_integrity(chksum, data):
                    exch = data.decode(errors='ignore')
                    if exch.startswith("EXCH_REQ"):
                        string =  exch.split(":")[1]
                        file_id, peer_addr = string.split(",")[0], string.split(",")[1]
                        print("inserting EXCH_REQ with file id: ", str(file_id), " into queue")
                        exch_req_queue.put((file_id, peer_addr))
                    else:
                        send_seq, msg = convert_sender_payload(data)
                        print("inserting data into queue")
                        exch_data_queue.put((data, address))
                        self.soc.sendto(make_packet(send_seq, "ACK"), address)
                else:
                    print("Corrupted packet, discarding")
        except Exception as e:
            print(e)
            print("Getting no more messages, exiting listener")

    def run_receiver(self, exch_data_queue):
        """Waits for data from self.soc, verifies data and populates data in
        self.packets using class methods.
        Exits 15 seconds of no activity
        after sender/client sends a sequence number of -1 is sent

        """

        try:
            while True:
                data, address = exch_data_queue.get(timeout=35)
                send_seq, msg = convert_sender_payload(data)
                print("Server Received seq: " + str(send_seq))
                #print("The message is: " + msg)
                if send_seq == -1:
                    print("Client is done, sending ack")
                    # sending ACK here might be redundant due to listener function acking for us
                    # This function shouldn't end abruptly in event of failed ack
                    # socket timeout avoided this but socket is not used here anymore
                    # Might need to set up an actual timer
                    return

                if self.base_seq == -1:
                    #print("Server Establishing base and max seq as " + str(send_seq))
                    self.base_seq = send_seq
                    self.max_seq = send_seq
                    self.packets = [None]

                if send_seq < self.base_seq:
                    #print("Server rebasing packets where base_seq: " + str(self.base_seq) + " to " + str(send_seq))
                    self.rebase_packets(send_seq, msg)
                elif send_seq >= self.max_seq:
                    #print("Server expanding packets from max_seq: " + str(self.max_seq) + " to " + str(send_seq))
                    self.add_packet(send_seq, msg, True)
                elif send_seq < self.max_seq and self.packets[send_seq - self.base_seq] is None:
                    self.add_packet(send_seq, msg, False)

                # sending ACK here might be redundant due to listener function acking for us
                #self.soc.sendto(make_packet(send_seq, "ACK"), address)
        except:
            print("Getting no more messages, exiting receiver")
        return


