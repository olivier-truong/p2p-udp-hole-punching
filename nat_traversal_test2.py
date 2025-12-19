import socket
import threading
import time
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
        self.mtu = 1472 - 50  # taille max UDP pour éviter fragmentation

        self.peer: Optional[Tuple[str, int]] = None
        self.sock: Optional[socket.socket] = None
        self.timeStampPeer: Optional[float] = time.time() + 20

        self.running = False

        # Buffer réception
        self.recv_buffer = []
        self.buffer_lock = threading.Lock()

    # -------------------- SOCKET --------------------

    def _init_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))
        self.sock.settimeout(self.timeout)

    # -------------------- RECEIVE LOOP --------------------

    def _recv_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(self.mtu)
                msg = data.decode(errors="ignore").strip()

                print(f"[{self.cid}] ← {msg} de {addr}")

                if msg.startswith("PEER"):
                    _, ip, port, timeStamp = msg.split()
                    self.peer = (ip, int(port))
                    
                    print(f"[{self.cid}] ✅ PEER défini → {self.peer}")

                else:
                    with self.buffer_lock:
                        self.recv_buffer.append((data, addr))

            except socket.timeout:
                pass

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
        
        for i in range(0, len(data), self.mtu):
            chunk = data[i:i + self.mtu]
            self.sock.sendto(chunk, self.peer)
        

    def recv(self, timeout: float | None = None) -> bytes:
        start = time.time()

        while True:
            with self.buffer_lock:
                if self.recv_buffer:
                    data, _ = self.recv_buffer.pop(0)
                    return data

            if timeout is not None and time.time() - start > timeout:
                raise TimeoutError("recv timeout")

            time.sleep(0.01)

    @staticmethod
    def crc64Bytes(data: bytes) -> int:
        POLY = 0x42F0E1EBA9EA3693
        table = []
        for byte in range(256):
            crc = byte << 56
            for _ in range(8):
                if (crc & (1 << 63)) != 0:
                    crc = (crc << 1) ^ POLY
                else:
                    crc <<= 1
                crc &= 0xFFFFFFFFFFFFFFFF
            table.append(crc)

        crc = 0xFFFFFFFFFFFFFFFF
        for byte in data:
            index = ((crc >> 56) ^ byte) & 0xFF
            crc = table[index] ^ (crc << 8)
            crc &= 0xFFFFFFFFFFFFFFFF

        return crc ^ 0xFFFFFFFFFFFFFFFF


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

    if cid == "1":
        # Envoi de messages toutes les 2 secondes
        try:
            count = 0
            while True:
                message = f"Message {count} de {cid}"
                print(f"[{cid}] → {message} vers {client.peer}")
                message = input("Entrez le message à envoyer: ")
                client.send(message)
                count += 1
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
    else:
        # Réception de messages
        try:
            while True:
                data = client.recv(timeout=120)
                print(f"[{cid}] reçu : {data.decode(errors='ignore')}")
        except TimeoutError:
            print(f"[{cid}] ⏳ Timeout de réception, arrêt.")
        
    try:
        while True:
            time.sleep(1)   
    except KeyboardInterrupt:
        client.stop()
        print(f"[{cid}] 🔴 arrêté")
