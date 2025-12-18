import socket
import threading
import time, io
from typing import Optional, Tuple
from datetime import datetime, timezone


class NATClient:
    def __init__(
        self,
        cid: str,
        server: Tuple[str, int],
        timeout: float = 0.5
    ):
        self.cid = cid
        self.server = server
        self.timeout = timeout

        self.peer: Optional[Tuple[str, int]] = None
        self.sock: Optional[socket.socket] = None
        self.timeStampPeer: Optional[float] = time.time() + 20

        self.running = False

        # Buffer réception
        self.recv_buffer = []
        self.buffer = io.BytesIO()
        self.buffer_lock = threading.Lock()
        self.connected = False

    # -------------------- SOCKET --------------------

    def _init_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))
        self.sock.settimeout(self.timeout)

    # -------------------- RECEIVE LOOP --------------------

    def _recv_loop(self):
        _said = False
        i = 0
        while self.running:
            try:
                print(f"[{self.cid}] Waiting to recv...")
                data, addr = self.sock.recvfrom(2048)
                print("data length recv:", len(data), "connected:", self.connected)
                if not(self.connected):
                    msg = data.decode(errors="ignore").strip()

                    print(f"[{self.cid}] ← {msg} de {addr}")

                    if msg.startswith("PEER"):
                        _, ip, port, timeStamp = msg.split()
                        self.peer = (ip, int(port))
                        if not(_said):
                            _said = True
                            print(f"[{self.cid}] ✅ PEER défini → {self.peer}")

                    else:
                        with self.buffer_lock:
                            self.recv_buffer.append((data, addr))
                else:
                    self.buffer.write(data)
                    self.buffer.flush()
                    if i % 100 == 50:
                        print(f"[{self.cid}] ← {len(data)} octets de {addr}")
                i += 1

            except socket.timeout:
                print(f"[{self.cid}] ⏳ Timeout réception")

    # -------------------- SIGNALING --------------------

    def signal(self, count: int = 10):
        for _ in range(count):
            self.sock.sendto(f"HELLO {self.cid}".encode(), self.server)
            time.sleep(self.timeout / 10)

    # -------------------- HOLE PUNCH --------------------

    def punch(self, count: int = 5):
        if not self.peer:
            return

        print(f"[{self.cid}] 🔥 Hole punching vers {self.peer}")
        for i in range(count):
            self.sock.sendto(f"P2P {self.cid} {i}".encode(), self.peer)
            time.sleep(self.timeout)

    # -------------------- SEND / RECV --------------------

    def send(self, data: bytes | str):
        if not self.peer:
            raise RuntimeError("Peer non défini")

        if isinstance(data, str):
            data = data.encode()

        for i in range(len(data)//2048 + 1):
            chunk = data[i*2048:(i+1)*2048]
            self.sock.sendto(chunk, self.peer)
        

    def recv(self, timeout: float | None = 0.005) -> bytes:
        start = time.time()
        ret = self.buffer.getvalue()
        self.buffer = io.BytesIO()
        time.sleep(timeout)
        return ret

    # -------------------- START --------------------

    def start(self):
        self._init_socket()
        self.running = True

        threading.Thread(
            target=self._recv_loop,
            daemon=True
        ).start()

        print(f"[{self.cid}] 📡 Signalisation")
        self.signal()

        print(f"[{self.cid}] ⏳ Attente peer")
        start = time.time()
        while self.peer is None and time.time() - start < 20:
            time.sleep(self.timeout)

        if self.peer:
            self.punch()
        else:
            print(f"[{self.cid}] ❌ Aucun peer")

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()


# -------------------- MAIN --------------------

if __name__ == "__main__":
    import sys

    cid = sys.argv[1]
    SERVER = ("vps1.glz.ovh", 3478)

    client = NATClient(cid, SERVER)

    dt = datetime.now(tz=timezone.utc)
    
    
    client.start()

    print(f"[{cid}] 🟢 prêt à échanger")
    client.connected = True

    if cid == "1":
        # Envoi de messages toutes les 2 secondes
        try:
            while True:
                filename = input(f"[{cid}] Fichier à envoyer (entrée pour passer) : ")
                if filename:
                    with open(filename, "rb") as f:
                        data = f.read()
                        client.send(data)
                        print(f"[{cid}] envoyé : {len(data)} octets depuis {filename}")
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
    else:
        # Réception de messages
        try:
            while True:
                try:
                    data = client.recv(timeout=120)
                    print("data length:", len(data))
                    if data:
                        print(f"[{cid}] reçu : {len(data)} octets")
                        filename = f"recu_{int(time.time())}.bin"
                        with open(filename, "wb") as f:
                            f.write(data)
                        print(f"[{cid}] sauvegardé dans {filename}")
                except Exception as e:
                    print(e)
        except TimeoutError:
            print(f"[{cid}] ⏳ Timeout de réception, arrêt.")
        
    try:
        while True:
            time.sleep(1)   
    except KeyboardInterrupt:
        client.stop()
        print(f"[{cid}] 🔴 arrêté")
