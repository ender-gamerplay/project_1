import sys
import os
import sqlite3
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QComboBox, QLineEdit, QPushButton, 
                             QListWidget, QListWidgetItem, QLabel, QDialog)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

DB_NAME = 'library.db'
DEFAULT_COVER = 'default_cover.png'

def init_database():
    if os.path.exists(DB_NAME):
        return
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        year INTEGER,
        genre TEXT,
        cover_path TEXT
    )
    """)

    test_books = [
        ("Трое с площади Карронад", "Крапивин Владислав", 1979, "Проза", "krapivin_troe.png"),
        ("Чоки-чок, или Рыцарь Прозрачного Кота", "Крапивин Владислав", 1992, "Сказка", "krapivin_choki.png"),
        ("Книга без обложки", "Неизвестный Автор", 2026, "Фантастика", "")
    ]
    
    cursor.executemany("""
    INSERT INTO books (title, author, year, genre, cover_path) 
    VALUES (?, ?, ?, ?, ?)
    """, test_books)
    
    conn.commit()
    conn.close()

    if not os.path.exists(DEFAULT_COVER):
        from PyQt6.QtGui import QImage, QPainter, QColor
        img = QImage(200, 260, QImage.Format.Format_RGB32)
        img.fill(QColor("lightgray"))
        img.save(DEFAULT_COVER)


class BookDetailDialog(QDialog):
    def __init__(self, book_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Информация о книге")
        self.setFixedSize(400, 550)
        self.initUI(book_data)
        
    def initUI(self, book_data):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        _, title, author, year, genre, cover_path = book_data

        lbl_cover = QLabel(self)
        pixmap = QPixmap(cover_path) if cover_path and os.path.exists(cover_path) else QPixmap(DEFAULT_COVER)

        lbl_cover.setPixmap(pixmap.scaled(200, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_cover)
        
        def create_centered_label(title_text, value_text):
            title_lbl = QLabel(title_text, self)
            title_lbl.setStyleSheet("font-size: 22px; font-weight: bold;")
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            value_lbl = QLabel(str(value_text), self)
            value_lbl.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
            value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            layout.addWidget(title_lbl)
            layout.addWidget(value_lbl)
            
        create_centered_label("Название", title)
        create_centered_label("Автор", author)
        create_centered_label("Год выпуска", year)
        create_centered_label("Жанр", genre)


class LibraryCatalog(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Каталог библиотеки")
        self.resize(600, 600)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_layout = QHBoxLayout()
        
        left_input_layout = QVBoxLayout()
        self.combo_search_type = QComboBox(self)
        self.combo_search_type.addItems(["Автор", "Название"])
        self.combo_search_type.setFixedWidth(150)
        left_input_layout.addWidget(self.combo_search_type)

        self.txt_search = QLineEdit(self)
        self.txt_search.setFixedWidth(200)
        left_input_layout.addWidget(self.txt_search)
        
        top_layout.addLayout(left_input_layout)

        self.btn_search = QPushButton("Искать", self)
        self.btn_search.setFixedSize(150, 60)
        self.btn_search.clicked.connect(self.search_books)
        top_layout.addWidget(self.btn_search)
        
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        self.list_books = QListWidget(self)
        self.list_books.setStyleSheet("font-size: 16px; padding: 5px;")
        self.list_books.itemDoubleClicked.connect(self.open_book_details)
        main_layout.addWidget(self.list_books)

        self.current_results = {}

        self.search_books()

    def search_books(self):
        self.list_books.clear()
        self.current_results.clear()
        
        search_text = self.txt_search.text().strip()
        search_type = self.combo_search_type.currentText()
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        if not search_text:
            query = "SELECT id, title, author, year, genre, cover_path FROM books"
            cursor.execute(query)
        else:
            if search_type == "Автор":
                query = "SELECT id, title, author, year, genre, cover_path FROM books WHERE author LIKE ?"
            else:
                query = "SELECT id, title, author, year, genre, cover_path FROM books WHERE title LIKE ?"
            cursor.execute(query, (f"%{search_text}%",))
            
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            title = row[1]
            item = QListWidgetItem(title)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_books.addItem(item)
            self.current_results[item] = row

    def open_book_details(self, item):
        book_data = self.current_results.get(item)
        if book_data:
            dialog = BookDetailDialog(book_data, self)
            dialog.exec()


if __name__ == '__main__':
    init_database()
    
    app = QApplication(sys.argv)
    catalog = LibraryCatalog()
    catalog.show()
    sys.exit(app.exec())