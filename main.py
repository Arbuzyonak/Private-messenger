import sys
import random
import sqlite3
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit, QHBoxLayout, QVBoxLayout, QMainWindow, QPushButton, QMessageBox, QLabel, QScrollArea
from PySide6.QtCore import Qt, QTimer

conn = sqlite3.connect("messages.db")
cursor = conn.cursor()

class Message:
    def __init__(self, text, sender):
        self.text = text
        self.sender = sender

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

        self.contacts_layout.addWidget(QLabel("Test"))

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

        self.create_database
        self.load_messages()

    def create_database():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                sender TEXT NOT NULL
            )
        """)


    def save_messages(self, message, sender):
        cursor.execute( # add message to database
            "INSERT INTO messages (text, sender) VALUES (?, ?)",
            (message, sender)
        )
        conn.commit() # save the message

    def load_messages(self):
        cursor.execute("SELECT * FROM messages")
        rows = cursor.fetchall()

        for row in rows:
            text = row[1]
            sender = row[2]
            message_label = QLabel(sender + ": " + text)
            self.messages_layout.addWidget(message_label) # Adds the message to message_layout

    def send_message(self):
        
        message_text = self.text_input.text() # message text

        new_message = Message(message_text, "me")

        if new_message.text.isspace() or len(new_message.text) <= 0: # rejects any message that is only spaces or has nothing in it to be sent
            return
        else:
            self.messages.append(new_message)
            self.text_input.clear()
            message_label = QLabel(new_message.sender + ": " + new_message.text)
            self.messages_layout.addWidget(message_label) # Adds the message to message_layout

            self.save_messages(new_message.text, new_message.sender)


    def scroll_to_bottom(self, minimum, maximum):
        self.scroll_area.verticalScrollBar().setValue(maximum)

app = QApplication()
window = MainWindow()
window.show()

app.exec()