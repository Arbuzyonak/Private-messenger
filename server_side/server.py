import socket
import threading
import json
import sys

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


HEADER = 64
PORT = 5050
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "!DISCONNECT"


def get_local_ips():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return [ip]
    except OSError:
        return []


def ask_bind_address():
    while True:
        detected = get_local_ips()

        if detected:
            print(f"Your IP: {', '.join(detected)}")
        else:
            print("Could not detect your IP")

        ip = input("IP to listen on [Enter = 0.0.0.0, all interfaces]: ").strip() or "0.0.0.0"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind((ip, PORT))
        except OSError as e:
            print(f"Can't listen on {ip}: {e}\n")
            sock.close()
            continue

        return sock


server = ask_bind_address()

clients = {}
clients_lock = threading.Lock()


def recv_exact(conn, size):
    data = b""

    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            return None
        data += chunk

    return data


def send_packet(conn, packet):
    message = json.dumps(packet).encode(FORMAT)
    send_length = str(len(message)).encode(FORMAT)
    send_length += b" " * (HEADER - len(send_length))

    conn.sendall(send_length)
    conn.sendall(message)


def receive_packet(conn):
    msg_length = recv_exact(conn, HEADER)

    if not msg_length:
        return None

    msg_length = int(msg_length.decode(FORMAT).strip())
    message = recv_exact(conn, msg_length)

    if not message:
        return None

    return json.loads(message.decode(FORMAT))


def find_client_by_username(username):
    with clients_lock:
        for user_id, client in clients.items():
            if client["username"] == username:
                return user_id, client

    return None, None


def handle_client(conn, addr):
    print(f"New connection: {addr} connected.")

    current_user_id = None
    current_username = None
    send_lock = threading.Lock()

    connected = True

    try:
        while connected:
            packet = receive_packet(conn)

            if packet is None:
                break

            if packet["type"] == "register":
                user_id = packet["user_id"]
                username = packet["username"]

                current_user_id = user_id
                current_username = username

                with clients_lock:
                    clients[user_id] = {
                        "username": username,
                        "socket": conn,
                        "send_lock": send_lock
                    }

                print(f"{username} connected")
                print(clients)

            elif packet["type"] == "add_contact":
                username = packet["username"]
                contact_user_id, contact = find_client_by_username(username)

                if contact is None:
                    with send_lock:
                        send_packet(conn, {
                            "type": "contact_error",
                            "error": "User is not online"
                        })
                    continue

                if contact_user_id == current_user_id:
                    with send_lock:
                        send_packet(conn, {
                            "type": "contact_error",
                            "error": "You cannot add yourself"
                        })
                    continue

                with send_lock:
                    send_packet(conn, {
                        "type": "contact_added",
                        "username": contact["username"],
                        "user_id": contact_user_id
                    })

                with contact["send_lock"]:
                    send_packet(contact["socket"], {
                        "type": "contact_added",
                        "username": current_username,
                        "user_id": current_user_id
                    })

            elif packet["type"] == "message":
                recipient_id = packet["recipient_id"]
                text = packet["text"]

                with clients_lock:
                    recipient = clients.get(recipient_id)

                if recipient:
                    print(f"Sending {text} to {recipient_id}")

                    with recipient["send_lock"]:
                        send_packet(recipient["socket"], {
                            "type": "message",
                            "sender_username": current_username,
                            "sender_user_id": current_user_id,
                            "text": text
                        })
                else:
                    with send_lock:
                        send_packet(conn, {
                            "type": "message_error",
                            "error": "Recipient is offline"
                        })

            elif packet["type"] == "disconnect":
                connected = False

            print(f"{addr}: {packet}")

    except (OSError, ValueError, json.JSONDecodeError, KeyError):
        pass

    finally:
        if current_user_id is not None:
            with clients_lock:
                current_client = clients.get(current_user_id)
                if current_client and current_client["socket"] is conn:
                    del clients[current_user_id]

        conn.close()



def accept_loop():
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"Active connections: {threading.active_count() - 2}")


def show_server_window(display_ip):
    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("Messenger Server")
    window.resize(350, 200)

    layout = QVBoxLayout(window)
    layout.addStretch()

    title = QLabel("Server running!")
    title.setFont(QFont("", 16))
    title.setAlignment(Qt.AlignCenter)
    layout.addWidget(title)

    tell = QLabel("Tell clients to connect to:")
    tell.setAlignment(Qt.AlignCenter)
    layout.addWidget(tell)

    ip_label = QLabel(f"{display_ip}:{PORT}")
    ip_label.setFont(QFont("", 22))
    ip_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(ip_label)

    status = QLabel("Connected: nobody yet")
    status.setAlignment(Qt.AlignCenter)
    layout.addWidget(status)

    def update_status():
        with clients_lock:
            names = ", ".join(c["username"] for c in clients.values())

        if names:
            status.setText(f"Connected: {names}")
        else:
            status.setText("Connected: nobody yet")

    timer = QTimer()
    timer.timeout.connect(update_status)
    timer.start(1000)

    layout.addStretch()
    window.show()
    app.exec()
    print("Server window closed - shutting down.")


def start():
    server.listen()

    bound_ip = server.getsockname()[0]
    detected = get_local_ips()
    display_ip = bound_ip if bound_ip != "0.0.0.0" else (detected[0] if detected else "0.0.0.0")

    print(f"Listening on {display_ip}:{PORT} (give this IP to clients)")

    accept_thread = threading.Thread(target=accept_loop, daemon=True)
    accept_thread.start()

    try:
        show_server_window(display_ip)
    except (OSError, RuntimeError):
        print("No display available - running in console only. Ctrl+C to stop.")
        accept_thread.join()


print("Server is starting...")
if __name__ == "__main__":
    start()