import sys
import random
import sqlite3
import socket
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit, QHBoxLayout, QVBoxLayout, QMainWindow, QPushButton, QMessageBox, QLabel, QScrollArea, QDialog
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from datetime import datetime

conn = sqlite3.connect("messages.db")
cursor = conn.cursor()

class ReceiverThread(QThread):
    message_received = Signal(str)

    def __init__(self, client_socket):
        super().__init__()

        self.client_socket = client_socket
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.client_socket.recv(2048)

                if not data:
                    break

                message = data.decode("utf-8")
                self.message_received.emit(message)

            except OSError:
                break

    def stop(self):
        self.running = False

        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

class Message:
    def __init__(self, text, sender, timestamp):
        self.text = text
        self.sender = sender
        self.timestamp = timestamp

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Private messenger")
        self.resize(700,500)

        container = QWidget()
        self.setCentralWidget(container)

        main_layout = QVBoxLayout(container)
        content_layout = QHBoxLayout()
        input_layout = QHBoxLayout()

        # text input
        self.text_input = QLineEdit()
        self.text_input.returnPressed.connect(self.send_message)

        # Send button
        send_button = QPushButton()
        send_button.setFixedWidth(50)
        send_button.setText("Send")
        send_button.pressed.connect(self.send_message)

        self.scroll_area = QScrollArea()
        messages_container = QWidget()
        self.messages_layout = QVBoxLayout(messages_container)
        self.messages_layout.setAlignment(Qt.AlignBottom)

        # Scroll area
        self.scroll_area.setWidget(messages_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_bar = self.scroll_area.verticalScrollBar()
        scroll_bar.rangeChanged.connect(self.scroll_to_bottom)

        # Sidebar
        self.side_area = QScrollArea()
        self.contact_container = QWidget()
        self.contacts_layout = QVBoxLayout(self.contact_container)

        self.side_area.setWidget(self.contact_container)
        self.side_area.setWidgetResizable(True)

        # Add contact button
        self.add_contact = QPushButton("Add Contact")
        self.contacts_layout.addWidget(self.add_contact)

        self.add_contact.pressed.connect(self.open_contact_window)

        # Main layout
        main_layout.addLayout(content_layout)
        main_layout.addLayout(input_layout)

        # Content layout
        content_layout.addWidget(self.side_area)
        content_layout.addWidget(self.scroll_area)

        content_layout.setStretch(0, 1)
        content_layout.setStretch(1, 4)

        # Input layout
        input_layout.addWidget(self.text_input)
        input_layout.addWidget(send_button)

        self.messages = []
        self.current_contacts = []
        self.current_chat_id = None

        self.create_message_database()
        self.create_chat_database()
        self.load_chats()
        self.check_button_click()

        self.HEADER = 64
        self.FORMAT = "utf-8"
        self.PORT = 5050
        self.SERVER = "192.168.0.12"
        self.ADDR = (self.SERVER, self.PORT)

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(self.ADDR)

        self.receiver_thread = ReceiverThread(self.client)

        self.receiver_thread.message_received.connect(
            self.receive_message
        )

        self.receiver_thread.start()

    def create_message_database(self):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                sender TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)
        conn.commit()

    def create_chat_database(self):
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        """)
        conn.commit()

    def save_messages(self, message, sender, chat_id, timestamp):
        cursor.execute( # add message to database
            "INSERT INTO messages (text, sender, chat_id, timestamp) VALUES (?, ?, ?, ?)",
            (message, sender, chat_id, timestamp)
        )
        conn.commit() # save the message

    def load_messages(self):
        cursor.execute("SELECT * FROM messages WHERE chat_id = ?", (self.current_chat_id,))
        rows = cursor.fetchall()
        for row in rows:
            text = row[1]
            sender = row[2]
            message_label = QLabel(sender + ": " + text)
            self.messages_layout.addWidget(message_label) # Adds the message to message_layout

    def send_message(self):
        
        message_text = self.text_input.text() # message text
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_message = Message(message_text, "me", timestamp)

        if new_message.text.isspace() or len(new_message.text) <= 0 or self.current_chat_id == None: # rejects any message that is only spaces or has nothing in it to be sent or theres no chat id
            return
        else:
            self.messages.append(new_message)
            self.text_input.clear()
            message_label = QLabel(new_message.sender + ": " + new_message.text)
            self.messages_layout.addWidget(message_label) # Adds the message to message_layout

            self.save_messages(
                new_message.text,
                new_message.sender,
                self.current_chat_id,
                timestamp
                )
            self.send_to_server(new_message.text)

    def load_chats(self):

        cursor.execute("SELECT * FROM chats")
        chats = cursor.fetchall()

        for chat_id, name in chats:
            button = QPushButton(name)
            self.contacts_layout.addWidget(button)
            self.current_contacts.append(button)

        self.contacts_layout.addStretch()

    def open_contact_window(self):
        self.second_window = QDialog()
        self.second_window.setWindowTitle("Add contact")

        layout = QVBoxLayout(self.second_window)


        layout.addStretch()
        layout.addWidget(QLabel("Who do you want to add?"))
        self.input_box = QLineEdit()
        layout.addWidget(self.input_box)

        self.second_window.show()
        self.input_box.returnPressed.connect(self.handle_input)


    def handle_input(self):
           text = self.input_box.text()
           if text.isspace() or len(text) <= 0:
               return
           self.create_contact(text)

    def create_contact(self, text):
        button = QPushButton(text)

        self.contacts_layout.insertWidget(
            self.contacts_layout.count() - 1,
            button
            )

        self.current_contacts.append(button)
        button.clicked.connect(self.contact_clicked)

        cursor.execute( # add contact to database
            "INSERT INTO chats (name) VALUES (?)",
            (text,)
        )

        conn.commit()
        
        self.second_window.close()

    def check_button_click(self):
        for button in self.current_contacts:
            button.clicked.connect(self.contact_clicked)

    def contact_clicked(self):
        button = self.sender()
        print(button.text())

        cursor.execute(
            "SELECT id FROM chats WHERE name = ?",
            (button.text(),)
        )
        row = cursor.fetchone()
        self.current_chat_id = row[0]

        self.clear_messages()
        self.load_messages()


    def clear_messages(self):
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()
           
    def scroll_to_bottom(self, minimum, maximum):
        self.scroll_area.verticalScrollBar().setValue(maximum)

    def send_to_server(self, message):
        encoded_message = message.encode(self.FORMAT)

        message_length = len(encoded_message)

        send_length = str(message_length).encode(self.FORMAT)

        send_length += b" " * (
            self.HEADER - len(send_length)
        )

        self.client.sendall(send_length)
        self.client.sendall(encoded_message)

    def receive_message(self, message):
        print("Received:", message)

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        received_message = Message(
            message,
            "other",
            timestamp
        )

        self.messages.append(received_message)

        message_label = QLabel(
            received_message.sender
            + ": "
            + received_message.text
        )

        self.messages_layout.addWidget(message_label)

        if self.current_chat_id is not None:
            self.save_messages(
                received_message.text,
                received_message.sender,
                self.current_chat_id,
                received_message.timestamp
            )
        

app = QApplication()
window = MainWindow()
window.show()

app.exec()