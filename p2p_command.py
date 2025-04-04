
def peer_index():
    return (None,None)


def peer_discovery():
    # Dictionary of peer_name as key and set of peer_id and index as value
    # value will be provided by peer_index() need to figure out method of getting index
    return {}

def print_menu():
    print('i -peer_name: Display data available from peer')
    print('c -peer_name -id: Connect to peer and request exchange for data with id')
    print('r : Refresh peer discovery')
    print('q : Quit')
    return

def print_index(index):
    # May need to modify based on index structure
    print(index)
    return

def exchange_data(peers, peer, id):
    # Get (peer_id, peer_index) when given peer as key to peers
    # check if id is valid in the peer_index prior to contact
    # else print id is not valid
    # set up a thread with method and parameters
    # to contact and exchange with peer using index id
    return


def p2p_command_line(name):
    print('Initiating P2P File Sharing System')
    print('Hello ', name)
    peers = peer_discovery()
    while True:
        print('Peers in the network:')
        for peer in peers.keys():
            print(peer)
        print_menu()
        ans = input('Choose: ')
        ans = ans.split(' ')
        command = ans[0]
        if command == 'i':
            peer = ans[1]
            #index = peers[peer][1]
            print_index(None)
        elif command == 'c':
            peer = ans[1]
            id = ans[2]
            exchange_data(peers, peer, id)
        elif command == 'r':
            peers = peer_discovery()
            continue
        elif command == 'q':
            print('Leaving system. Bye')
            break
        else:
            print('Command was not valid, please try again')


def main():
    p2p_command_line('Tempest')

if __name__ == "__main__":
    main()


