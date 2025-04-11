import os.path
import socket
import threading
import sys
import queue
from threading import Thread

from P2P_File_Share_Proj.receiver_rdt import Receiver
from P2P_File_Share_Proj.sender_rdt import Sender, make_checksum
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
            PEERS.add(peer_info)
            print(f"[Tracker] Registered peer: {peer_info}")
            peer_list = "|".join(p for p in PEERS if p != peer_info)
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


def register_with_tracker(tracker_host, tracker_port, peer_host, peer_port):
    """
    Connects to the tracker and registers the current peer.
    Returns a list of other peers in the network.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((tracker_host, tracker_port))
        peer_info = f"{peer_host}:{peer_port}"
        s.send(f"REGISTER:{peer_info}".encode())
        data = s.recv(1024).decode()
        peer_list = data.split('|') if data else []
        return peer_list
    except Exception as e:
        print(f"[Error] Could not connect to tracker: {e}")
        return []
    finally:
        s.close()


def peer_discovery(my_port):
    """
    Uses the tracker to discover other peers in the network.
    Returns a dictionary mapping 'peer_id' to (ip, port).
    """
    my_host = socket.gethostbyname(socket.gethostname())
    tracker_host, tracker_port = '127.0.0.1', 9000

    peer_list = register_with_tracker(tracker_host, tracker_port, my_host, my_port)
    
    # Create dictionary: {'127.0.0.1:10001': ('127.0.0.1', 10001)}
    return {p: (p.split(':')[0], int(p.split(':')[1])) for p in peer_list if ':' in p}

def get_index_path(exch_peer, exch_id):
    """
    Given a peer and a file ID, return the path to the file.
    For now, only local lookups are supported.
    
    :param exch_peer: the peer requesting the file (not used currently)
    :param exch_id: the file ID being requested
    :return: the file path as a string, or empty string if not found
    """

    path = os.path.abspath(__file__)
    file_path = peer_files.get(exch_id, "")
    path = path.replace('p2p_command.py',file_path)
    return path


def print_menu():
    """
    Prints the command menu for the user.
    """
    print('\nAvailable commands:')
    print('i -peer_name          : Display data available from peer')
    print('c -peer_name -id      : Connect to peer and request file with id')
    print('r                     : Refresh peer discovery')
    print('q                     : Quit')


def print_index(index=None):
    """
    Displays the list of available files from this peer.
    """
    print("\n[Local File Index]")
    for file_id, path in peer_files.items():
        print(f"ID: {file_id} -> Path: {path}")


def exchange_data(peers, peer_name, file_id, soc, address,exch_data_queue):
    """
    Stub function to exchange data with a peer.
    This is where the file transfer mechanism will go.
    """
    # Temporarily commented out until tracker is working
    #if peer_name not in peers:
    #    print(f"[Exchange] Peer '{peer_name}' not found.")
    #    return

    print(f"[Exchange] Attempting to download file ID {file_id} from {peer_name}...")
    # Peer_addr will be peer_name. Peer name needs to be a tuple of ip, port
    #peer_addr = peers[peer_name]
    peer_addr = peer_name
    peer_msg = "EXCH_REQ:" + str(file_id)+"."+str(address)
    sep_receiver = Receiver(soc)
    exchange_req = Thread(target=sep_receiver.execute_request, args=[peer_addr,peer_msg,file_id,exch_data_queue])
    exchange_req.start()


def sender_loop(addr, port,exch_data_queue, soc):
    for key in peer_files.keys():
        exchange_data([],(addr, port),key,soc,str((addr, port)), exch_data_queue)
        #time.sleep(60)


def p2p_command_line(name, port):
    """
    Main interface for the P2P system.
    Handles user input and executes commands.
    """
    address = socket.gethostbyname(socket.gethostname())
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind((address, port))
    exch_req_queue = queue.SimpleQueue()
    exch_data_queue = queue.SimpleQueue()
    receiver = Receiver(soc)

    listener = Thread(target=receiver.listen_for_requests, args=[exch_req_queue,exch_data_queue])
    listener.start()
    #looper = Thread(target=sender_loop, args=[address,port, exch_data_queue, soc])
    #looper.start()
    # uncomment above two lines to imitate exchange requests for file ids: 001, 002, 003

    print('--- P2P File Sharing System ---')
    print(f'Hello, {name} (listening on port {port})')

    peers = peer_discovery(port)

    while True:
        #print("P2P EXCH status: " + str(exch_req_queue.empty()))
        if not exch_req_queue.empty():
            print("Fulfilling Exchange Request")
            while not exch_req_queue.empty():
                entry = exch_req_queue.get()
                exch_id, exch_peer = entry[0], entry[1]
                #exch_addr = peers[exch_peer]
                exch_path = get_index_path(exch_peer,exch_id)
                send_soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sender = Sender(send_soc, address, port, exch_id)
                sender_thread = Thread(target=sender.setup_exchange, args=[exch_path])
                sender_thread.start()
        else:
            #time.sleep(2)
            #continue
            # uncomment the two above lines to monitor the listener, request and p2p sender threads
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
                print_index(None)  # Replace with real index data later
            elif command == 'c' and len(ans) == 3:
                peer, file_id = ans[1], ans[2]
                exchange_data(peers, peer, file_id, receiver, address,exch_data_queue)
            elif command == 'r':
                peers = peer_discovery(port)
            elif command == 'q':
                print('Leaving system. Goodbye!')
                receiver.set_timeout()
                break
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
    if '--tracker' in sys.argv:
        # Run as tracker
        start_tracker()
    else:
        # Run as peer
        port = 10000  # You can prompt or randomize this per instance if needed
        name = "Tempest"  # Can be input() or fixed for now
        p2p_command_line(name, port)
