import socket
import time
from datetime import datetime, timezone

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 34780))

clients = {}
last_seen = {}

print("[SERVER] prêt")

while True:
    data, addr = sock.recvfrom(2048)
    msg = data.decode(errors="ignore")
    parts = msg.split()

    if len(parts) < 2:
        continue

    cmd, cid = parts[0], parts[1]
    clients[cid] = addr
    last_seen[cid] = time.time()

    # envoyer l'info peer quand on a 2 clients
    if len(clients) == 2:
        ids = list(clients.keys())
        for a in ids:
            b = ids[1] if a == ids[0] else ids[0]
            ip, port = clients[b]
            sock.sendto(
                f"PEER {ip} {port} {datetime.now(tz=timezone.utc).timestamp()}".encode(),
                clients[a]
            )
            print(f"PEER {ip} {port} {datetime.now(tz=timezone.utc).timestamp()}".encode(),
                clients[a])
"""
    # relais fallback
    if cmd == "RELAY" and len(parts) >= 3:
        payload = " ".join(parts[2:])
        for other, oaddr in clients.items():
            if other != cid:
                sock.sendto(
                    f"FROM {cid} {payload}".encode(),
                    oaddr
                )
"""