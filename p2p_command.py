import argparse
from os import _exit
import os.path
import socket
import threading
import sys
import queue
from threading import Thread

from receiver_rdt import Receiver, verify_integrity
from sender_rdt import Sender, convert_receiver_payload, make_checksum
import time


#
# "BitTorrent trackers provide a list of files available for 
# transfer and allow the client to find peer users, 
# known as "seeds", who may transfer the files."
#
# To use you need two terminal Windows:
#   1. python p2p_command.py --tracker
#   2. python p2p_command.py
#


# -----------------------------
# Tracker logic
# -----------------------------


PEERS = set()  # This set stores all peer addresses as strings like "ip:port"

# Local index: file_id -> filepath
peer_files = {
    "001": "shared/file1.txt",
    "002": "shared/file2.txt",
    "003": "shared/file3.txt"
}



def start_tracker(host='0.0.0.0', port=9000):
    """
    Starts the tracker server that listens for incoming peer registrations.
    It adds peers to a global set and returns the list of known peers (excluding the caller).
    """
    def handle_client(conn, addr):
        """
        Handles an individual connection from a peer.
        Expects a message in the format "REGISTER:<ip>:<port>"
        Responds with a '|' separated list of all other peers.
        """
        data = conn.recv(1024).decode()
        if data.startswith("REGISTER:"):
            peer_info = data.split("REGISTER:")[1]
            ip_port, name = peer_info.rsplit(":", 1)
            peer_full = f"{ip_port}:{name}"
            PEERS.add((ip_port, name))
            print(f"[Tracker] Registered peer: {peer_info}")
            peer_list = "|".join(f"{ip}:{n}" for ip, n in PEERS if f"{ip}:{n}" != peer_full)
            conn.send(peer_list.encode())
        conn.close()

    # Set up TCP server socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, port))
    s.listen(5)
    print(f"[Tracker] Running on {host}:{port}")
    print("[Tracker] Waiting for peers to connect...")

    # Accept connections forever (each handled in a separate thread)
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()


# -----------------------------
# Peer logic
# -----------------------------


def register_with_tracker(tracker_host, tracker_port, peer_host, peer_port, peer_name):
    """
    Connects to the tracker and registers the current peer.
    Returns a list of other peers in the network.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((tracker_host, tracker_port))
        peer_info = f"{peer_host}:{peer_port}:{peer_name}"
        s.send(f"REGISTER:{peer_info}".encode())
        data = s.recv(1024).decode()
        peer_list = data.split('|') if data else []
        return peer_list
    except Exception as e:
        print(f"[Error] Could not connect to tracker: {e}")
        return []
    finally:
        s.close()


def peer_discovery(my_port, my_name):
    """
    Uses the tracker to discover other peers in the network.
    Returns a dictionary mapping 'peer_id' to (ip, port).
    """
    my_host = socket.gethostbyname(socket.gethostname())
    tracker_host, tracker_port = '127.0.0.1', 9000

    peer_list = register_with_tracker(tracker_host, tracker_port, my_host, my_port, my_name)
    
    # Create dictionary: {'Tempest': ('127.0.0.1', 10001),}
    peer_dict = {}
    for entry in peer_list:
        ip, port, name = entry.split(":")
        peer_dict[name] = (ip, int(port))
    return peer_dict


def get_index_path(exch_id):
    """
    Given a file ID, return the absolute file path.
    
    :param exch_peer: the peer requesting the file (not used currently)
    :param exch_id: the file ID being requested
    :return: the file path as a string, or empty string if not found
    """
    return os.path.abspath(peer_files.get(exch_id, ""))


def print_menu():
    """
    Prints the command menu for the user.
    """
    print('\nAvailable commands:')
    print('i -peer_name          : Display data available from peer')
    print('c -peer_name -id      : Connect to peer and request file with id')
    print('r                     : Refresh peer discovery')
    print('q                     : Quit')


def print_index(peer_addr=None, soc=None):
    """
    Displays the list of available files from this peer.
    Uses a separate socket to avoid interference with receiver.
    """
    if peer_addr:
        print(f"[Index] Requesting index from {peer_addr}...")

        # Create a fresh, temporary socket for this request
        temp_soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_soc.bind(('', 0))  # OS assigns an available port

        try:
            msg = "INDEX_REQ"
            chksum = make_checksum(msg.encode())
            temp_soc.sendto(chksum + msg.encode(), peer_addr)

            temp_soc.settimeout(3)
            data, _ = temp_soc.recvfrom(4096)
            chksum = data[:8]
            payload = data[8:]

            if verify_integrity(chksum, payload):
                _, index_msg = convert_receiver_payload(payload)
                print("[Remote Index]")
                for entry in index_msg.split("|"):
                    fid, name = entry.split(":")
                    print(f"ID: {fid} -> {name}")
            else:
                print("[Index] Corrupted response.")
        except socket.timeout:
            print("[Index] No response from peer.")
        finally:
            temp_soc.close()
    else:
        print("\n[Local File Index]")
        for fid, path in peer_files.items():
            print(f"ID: {fid} -> Path: {path}")


def exchange_data(peers, peer_name, file_id, receiver, address):
    """
    Sends an EXCH_REQ to the remote peer.
    The remote peer's receiver will queue a file-sending job in 'exch_req_queue'.
    """
    print(f"[Exchange] Attempting to download file ID {file_id} from {peer_name}...")

    if peer_name not in peers:
        print(f"[Exchange] Peer '{peer_name}' not found.")
        return

    peer_addr = peers[peer_name]
    peer_msg = f"EXCH_REQ:{file_id},{address}"

    # Use the same UDP socket the receiver is bound to
    s = receiver.soc
    payload = peer_msg.encode('utf-8')
    chksum = make_checksum(payload)
    s.sendto(chksum + payload, peer_addr)

    print("[Exchange] EXCH_REQ sent. Receiver will auto-save once the remote peer responds.")

        
def process_exchange_requests(exch_req_queue, address, soc):
    """
    Continuously monitors 'exch_req_queue' for (file_id, peer_address) tuples
    and starts a Sender to serve that file to 'peer_address'.
    """
    while True:
        if not exch_req_queue.empty():
            print("[System] Fulfilling Exchange Request")
            file_id, raw_peer_addr = exch_req_queue.get()

            try:
                peer_ip, peer_port_str = raw_peer_addr.split(":")
                exch_path = get_index_path(file_id)
                send_soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sender = Sender(send_soc, peer_ip, int(peer_port_str), file_id)
                sender_thread = Thread(target=sender.setup_exchange, args=[exch_path])
                sender_thread.start()
            except ValueError:
                print(f"[Error] Invalid peer address format: {raw_peer_addr}")
        time.sleep(1)


def p2p_command_line(name, port):
    """
    Main interface for the P2P system.
    Handles user input and executes commands.
    """
    ip = socket.gethostbyname(socket.gethostname())
    address = f"{ip}:{port}"
          
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind((ip, port))
    
    exch_req_queue = queue.SimpleQueue()
    receiver = Receiver(soc, peer_files)

    listener = Thread(target=receiver.listen_for_requests, args=[exch_req_queue])
    listener.start()
    print("[System] Receiver thread launched.")
    
    exchange_processor = Thread(target=process_exchange_requests, args=[exch_req_queue, address, soc])
    exchange_processor.start()
    print("[System] Exchange processor thread launched.")


    print('--- P2P File Sharing System ---')
    print(f'Hello, {name} (listening on port {port})')

    peers = peer_discovery(port, name)

    while True:
        print('\nCurrent Peers:')
        for peer in peers.keys():
            print(f" - {peer}")
        print_menu()

        # User input
        ans = input('\nChoose: ').strip().split(' ')
        if not ans:
            continue

        command = ans[0]

        if command == 'i' and len(ans) == 2:
            peer = ans[1]
            if peer in peers:
                print_index(peers[peer], soc)
            else:
                print("[Error] Unknown peer.")
        elif command == 'c' and len(ans) == 3:
            peer, file_id = ans[1], ans[2]
            exchange_data(peers, peer, file_id, receiver, address)
        elif command == 'r':
            peers = peer_discovery(port, name)
        elif command == 'q':
            print('Leaving system. Goodbye!')
            receiver.set_timeout()
            _exit(1)
        else:
            print('[Error] Invalid command. Please try again.')



# -----------------------------
# Entry point
# -----------------------------

if __name__ == "__main__":
    """
    Launches the program.
    If run with '--tracker', acts as the tracker.
    Otherwise, launches the peer command-line interface.
    """
    parser = argparse.ArgumentParser(description="P2P File Sharing App")
    parser.add_argument('--tracker', action='store_true', help='Run as tracker server')
    parser.add_argument('--port', type=int, help='Port number to use (default: 10000)')
    parser.add_argument('--name', type=str, help='Peer name (default: Tempest)')
    args = parser.parse_args()

    if args.tracker:
        start_tracker()
    else:
        port = args.port if args.port else int(input("Enter port number (e.g., 10001): "))
        name = args.name if args.name else input("Enter peer name: ")
        p2p_command_line(name, port)
