import socket
import threading
import json


HEADER = 64
PORT = 5050
SERVER = "192.168.0.12"
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "!DISCONNECT"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(ADDR)

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



def start():
    server.listen()
    print(f"Listenting on {SERVER}")
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"Active connections: {threading.active_count() - 1}")


print("Server is starting...")
if __name__ == "__main__":
    start()