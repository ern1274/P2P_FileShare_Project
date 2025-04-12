
P2P FILE SHARING SYSTEM
=======================

**Authors:**
- Joshua Talbot
- Ethan Nunez

PROJECT OVERVIEW
------------------------------------
This project implements a basic Peer-to-Peer (P2P) file sharing system in Python. It allows multiple users (peers) to register with a central tracker and discover each other in order to exchange files directly, without a centralized server.

It mimics basic BitTorrent-like functionality with:
- Peer discovery via a tracker server
- Command-line interface
- Threaded architecture (extendable)
- Foundation for file indexing and chunked file transfers

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
Example:
------------------------------------

```bash
> i -127.0.0.1:10000
> c -127.0.0.1:10000 -001
```
<br>

------------------------------------
FILES AND STRUCTURE
------------------------------------
`p2p_command.py`
Unified script for running both the tracker and the peer interface.

`receiver_rdt.py`
Handles peer requests when a peer receives a request.

`sender_rdt.py`
Handles peer requests by sending out requests.

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
`Python 3.7` or newer. No external libraries are required for basic functionality.