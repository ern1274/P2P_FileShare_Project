import threading
import time
import zlib
from sender_rdt import make_packet as make_data_packet, convert_ack_payload


def make_checksum(data):
    """
    Forms checksum from data using crc32 function from zlib library

    :param data: sequence of Bytes to calculate checksum
    :type data: Bytes
    :return: checksum of data
    :rtype: Bytes
    """
    return zlib.crc32(data).to_bytes(8,'big',signed=True)

def make_receiver_payload(seq_num, msg):
    """
    Forms packet payload by encoding sequence number and message of packet

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
    """
    Decodes packet payload to retrieve sequence number and message of packet

    :param data: sequence of Bytes to decode
    :type data: Bytes
    :return: send_seq, sequence number of packet
    :rtype: Bytes
    :return: msg, data from packet
    :rtype: String
    """
    id_length = int.from_bytes(data[:4], byteorder='big')
    file_id = data[4:4+id_length].decode()
    send_seq = int.from_bytes(data[4+id_length:8+id_length], byteorder='big', signed=True)
    msg = data[8+id_length:].decode()
    return file_id, send_seq, msg

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

def make_packet(seq_num, msg):
    """
    Forms packet by combining calculated checksum and formed payload

    :param seq_num: int to convert to bytes
    :type seq_num: int
    :param msg: characters to encode
    :type msg: String
    :return: payload, sequence of bytes containing seq_num and msg
    :return type: Bytes
    """
    payload = make_receiver_payload(seq_num, msg)
    chksum = make_checksum(payload)
    return chksum + payload

class Receiver:
    """
    Receiver class that can handle multiple files simultaneously.

    For each inbound file, we store its 'base_seq', 'max_seq', and 'packets'
    inside self.active_files[file_id], for example:

        self.active_files[file_id] = {
            'base_seq': -1,
            'max_seq':  -1,
            'packets':  []
        }

    When a new chunk arrives for 'file_id', we place it at index [seq - base_seq].
    Once we see seq == -1, we know the sender is done sending that file, and we
    call finalize_file(file_id) to write out the chunks and remove the entry.

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

    def __init__(self, soc, peer_files=None):
        """
        :param soc: the UDP socket that this receiver will use for inbound data
        :param peer_files: an optional dictionary of local files (file_id -> path)
        """
        self.soc = soc
        self.peer_files = peer_files if peer_files else {}

        # Multi-file storage: file_id -> { base_seq, max_seq, packets[] }
        self.active_files = {}

        self.timeout = None

    # Rebase and add packet functions will change base_seq and max_seq
    def add_packet(self, file_id, seq_num, data_str, expand_pkts):
        """
        Given file_id, seq_num, data_str, place the data into the correct spot
        in 'info["packets"]'. If expand_pkts is True, we enlarge 'info["packets"]'
        up to seq_num.

        :param file_id: the identifier of the inbound file
        :type file_id: String
        :param seq_num: sequence number of this chunk
        :type seq_num: int
        :param data_str: the chunk contents
        :type data_str: String
        :param expand_pkts: True if seq_num >= info['max_seq'], meaning we may need
                            to extend the packets array
        :type expand_pkts: bool
        """
        info = self.active_files[file_id]

        if expand_pkts:
            needed = seq_num - info['max_seq']
            # If needed == 0, it means seq_num is exactly info['max_seq'],
            # we still need to create one new slot for that chunk. So you may do:
            # needed = (seq_num - info['max_seq']) + 1
            # if you want the new chunk to expand properly. 
            # But let's keep it as is if you have consistent indexing.
            for _ in range(needed):
                info['packets'].append(None)
            info['max_seq'] = seq_num

        idx = seq_num - info['base_seq']
        info['packets'][idx] = data_str

    def rebase_packets(self, file_id, seq_num, data_str):
        """
        Given file_id and a chunk's sequence number is smaller than base_seq,
        rebase so that 'seq_num' becomes the new base_seq and put 'data_str'
        at index 0.

        :param file_id: the identifier of the inbound file
        :type file_id: String
        :param seq_num: the inbound packet's sequence number
        :type seq_num: int
        :param data_str: the actual file data chunk
        :type data_str: String
        """
        info = self.active_files[file_id]
        old_base = info['base_seq']
        shift_count = old_base - seq_num

        # Insert shift_count new 'None' at the front
        for _ in range(shift_count):
            info['packets'].insert(0, None)

        info['base_seq'] = seq_num
        # Now index 0 matches this chunk
        info['packets'][0] = data_str
        
    def finalize_file(self, file_id):
        """
        Writes out the collected packets for 'file_id' to <file_id>_torrent.txt,
        then clears them from self.active_files.

        :param file_id: the unique identifier for the file being transferred
        :type file_id: String
        """
        if file_id not in self.active_files:
            print(f"[Receiver] finalize_file called, but no record found for {file_id}.")
            return

        info = self.active_files[file_id]
        packets = info['packets']
        outname = f"{file_id}_torrent.txt"

        with open(outname, "w") as f:
            for chunk in packets:
                if chunk:
                    f.write(chunk)

        print(f"[Receiver] Saved file {outname} successfully.")
        # Remove from active_files
        del self.active_files[file_id]

    def set_timeout(self):
        """
        Optional method to signal that this receiver should time out.
        """
        self.soc.settimeout(1)
        
    #
    # ------------------ MAIN LISTENER ------------------
    #

    def listen_for_requests(self,exch_req_queue):
        """
        Waits for request from other peers from self.soc, verifies data and verifies requests
        Runs as long as the p2p_command is running
        """
        while True:
            try:
                data, address = self.soc.recvfrom(4096)

                # Separate checksum from payload
                chksum = data[:8]
                payload = data[8:]

                if not verify_integrity(chksum, payload):
                    print("Corrupted packet, discarding")
                    continue

                # See what kind of message this is
                text_msg = payload.decode(errors='ignore')

                if text_msg.startswith("EXCH_REQ"):
                    # Example: "EXCH_REQ:001,127.0.0.1:9999"
                    # We'll push it to the queue to let the 'sender logic' handle it
                    # (i.e. we are the "server" side for that file).
                    string = text_msg.split(":")[1]
                    try:
                        file_id, raw_ip = string.split(",", 1)
                        ip, port = address  # actual sender's address from recvfrom()
                        peer_addr = f"{ip}:{port}"
                        print("[Receiver] Inserting EXCH_REQ with file id:", file_id, "and peer_addr:", peer_addr)
                        exch_req_queue.put((file_id, peer_addr))
                    except ValueError:
                        print(f"[Error] Invalid EXCH_REQ format: {string}")

                elif text_msg.startswith("INDEX_REQ"):
                    # Peer is asking for our local file index
                    print("[Receiver] Received INDEX_REQ")
                    file_index = "|".join(f"{fid}:{fname}" for fid, fname in self.peer_files.items())
                    resp_pkt = make_data_packet(0, file_index, "index")  # from sender_rdt
                    self.soc.sendto(resp_pkt, address)
                    print("[Receiver] Sent index response")

                else:
                    #
                    # Otherwise, assume it's a chunk of file data from a sender.
                    #
                    file_id, send_seq, msg = convert_sender_payload(payload)
                    # Send ACK immediately
                    #print('sequence number ' + str(send_seq) + " : " + str(msg))
                    ack_pkt = make_packet(send_seq, "ACK")
                    self.soc.sendto(ack_pkt, address)

                    # If we haven't started tracking this file yet, init an entry
                    if file_id not in self.active_files:
                        self.active_files[file_id] = {
                            'base_seq': -1,
                            'max_seq': -1,
                            'packets': []
                        }

                    # Shortcut reference
                    info = self.active_files[file_id]

                    # If this is the "FIN" marker
                    if send_seq == -1:
                        print(f"[Receiver] Received final chunk (-1) for file {file_id} -- writing to disk.")
                        self.finalize_file(file_id)
                        continue

                    #
                    # If first chunk for this file, set up base_seq / max_seq
                    #
                    if info['base_seq'] == -1:
                        info['base_seq'] = send_seq
                        info['max_seq'] = send_seq
                        info['packets'] = [None]  # index 0

                    if send_seq < info['base_seq']:
                        # We rebase
                        self.rebase_packets(file_id, send_seq, msg)
                    elif send_seq >= info['max_seq']:
                        # Expand
                        self.add_packet(file_id, send_seq, msg, True)
                    else:
                        # It's in the existing range, fill if not present
                        idx = send_seq - info['base_seq']
                        if info['packets'][idx] is None:
                            self.add_packet(file_id, send_seq, msg, False)

            except Exception as e:
                print("[Receiver] Unexpected error:", e)
                #continue
                break

