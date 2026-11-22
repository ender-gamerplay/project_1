import sys
from math import *
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit


class Evaluator(QWidget):
    def __init__(self):
        self.__width = 300
        self.__hight = 300
        self.__index = 0
        #self.__directions = ("->", "<-")
        
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setGeometry(300, 300, self.__width, self.__hight)
        self.setWindowTitle("МЕГА КРУТОЕ ПРИЛОЖЕНИЕ")
        self.first_value = QLineEdit(self)
        self.first_value.move(5, 5)
        self.first_value.resize(100, 40)
        
        self.second_value = QLineEdit(self)
        self.second_value.move(160, 5)
        self.second_value.resize(100, 40)
        
        self.trick_button = QPushButton("->", self)
        self.trick_button.move(110, 5)
        self.trick_button.resize(40, 40)
        self.trick_button.clicked.connect(self.trick)
        
    def trick(self):
        self.second_value.setText(str(eval(self.first_value.text())))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = Evaluator()
    ex.show()
    sys.exit(app.exec())