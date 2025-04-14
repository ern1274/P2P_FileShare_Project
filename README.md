
P2P FILE SHARING SYSTEM
=======================

**Authors:**
- Joshua Talbot
- Ethan Nunez

PROJECT OVERVIEW
------------------------------------
This project implements a basic Peer-to-Peer (P2P) file sharing system in Python. 
It allows multiple users (peers) to register with a central tracker and 
discover each other in order to exchange files directly, without a centralized server.

It mimics basic BitTorrent-like functionality with:
- Peer discovery via a tracker server
- Command-line interface
- Threaded architecture (extendable)
- Foundation for file indexing and chunked file transfers
- Support for multiple consecutive file transfers  

------------------------------------
HOW TO RUN
------------------------------------
1. Start the tracker (only needs to be run once):
```bash 
python p2p_command.py --tracker
```
2. Start each peer in a separate terminal:
```bash 
python p2p_command.py
```

3. Commence file transfers using the command-line interface.

------------------------------------
COMMAND-LINE USAGE
------------------------------------
Once inside the P2P interface, you can use the following commands:
```bash
i -peer_name
```
Display the index of files shared by the specified peer.
```bash
c -peer_name -id
```
Connect to a peer and request the file with the given ID (not implemented yet).
```bash
r
```
Refresh the peer list by querying the tracker again.

```bash
q
```
Quit the program.
<br>
<br>

------------------------------------
Example Session:
------------------------------------

```bash
> i Alice
> c Alice 001
```
This will attempt to download the file at file index 001 from peer "Alice".
<br>

------------------------------------
FILES AND STRUCTURE
------------------------------------
`p2p_command.py`
Unified script for running both the tracker and the peer interface.

`receiver_rdt.py`
Handles inbound requests. Implements a multi-file approach so multiple inbound 
file transfers can occur. Automatically saves each completed file 
(e.g. 001_torrent.txt).

`sender_rdt.py`
Handles outbound file requests. Splits files into chunks, sends them with basic 
reliability and “Selective Repeat” logic, and completes with a FIN handshake.

`README.md`
You're reading it!

`requirements.txt`
Will list dependencies.

`revisions.txt`
Contains git log history (to be generated using git log > revisions.txt).

`report.pdf`
Project report with system overview, design, and authorship.
<br>
<br>

------------------------------------
DEPENDENCIES
------------------------------------
`Python 3.7` or newer. No extra libraries required for basic functionality; 
just standard Python modules like socket, threading, queue, etc.