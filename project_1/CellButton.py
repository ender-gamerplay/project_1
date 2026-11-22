from PyQt6.QtWidgets import (QPushButton)
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon


class CellButton(QPushButton):
    """Класс отдельной клетки игрового поля"""
    def __init__(self, x, y, parent=None):
        super().__init__(parent)
        self.x = x
        self.y = y
        self.is_mine = False
        self.is_revealed = False
        self.is_flagged = False
        self.adjacent_mines = 0
        self.setFixedSize(QSize(35, 35))

    def refresh_style(self, textures=None):
        """Полное обновление внешнего вида кнопки на основе её текущего состояния"""
        # Очищаем старые параметры, чтобы стили не накладывались друг на друга
        self.setIcon(QIcon())
        self.setText("")
        self.setStyleSheet("")

        # 1. Если используются кастомные текстуры
        if textures:
            # Состояние: Закрытая клетка с ФЛАГОМ
            if not self.is_revealed and self.is_flagged and textures.get('flag'):
                self.setIcon(QIcon(textures['flag']))
                self.setIconSize(self.size())
                return
            
            # Состояние: Открытая клетка с МИНОЙ
            elif self.is_revealed and self.is_mine and textures.get('mine'):
                self.setIcon(QIcon(textures['mine']))
                self.setIconSize(self.size())
                return
            
            # Состояние: Открытая ПУСТАЯ клетка или клетка с цифрой
            elif self.is_revealed and not self.is_mine:
                if textures.get('opened'):
                    clean_path = textures['opened'].replace("\\", "/")
                    self.setStyleSheet(f"border: 1px solid #b0b0b0; background-image: url('{clean_path}'); background-position: center; background-repeat: no-repeat;")
                else:
                    self.setStyleSheet("background-color: #e0e0e0; border: 1px solid #b0b0b0;")
                self.display_number()
                return
            
            # Состояние: Просто ЗАКРЫТАЯ клетка
            elif not self.is_revealed and not self.is_flagged and textures.get('closed'):
                self.setIcon(QIcon(textures['closed']))
                self.setIconSize(self.size())
                return

        # 2. Стандартный классический стиль (если текстуры не заданы или отсутствуют)
        if not self.is_revealed:
            if self.is_flagged:
                self.setText("🚩")
                self.setStyleSheet("color: red; background-color: #d0d0d0; border: 2px outset #ffffff; font-weight: bold; font-size: 14px;")
            else:
                self.setStyleSheet("background-color: #d0d0d0; border: 2px outset #ffffff;")
        else:
            if self.is_mine:
                self.setText("💣")
                self.setStyleSheet("background-color: #ffcccc; border: 1px solid #b0b0b0; font-size: 14px;")
            else:
                self.setStyleSheet("background-color: #e0e0e0; border: 1px solid #b0b0b0;")
                self.display_number()

    def display_number(self):
        """Отрисовка цифры количества мин вокруг клетки"""
        if self.adjacent_mines > 0:
            self.setText(str(self.adjacent_mines))
            colors = {1: "blue", 2: "green", 3: "red", 4: "darkBlue", 5: "darkRed", 6: "cyan", 7: "black", 8: "grey"}
            color = colors.get(self.adjacent_mines, 'black')
            # Дописываем цвет текста к текущему стилю (чтобы не затереть текстуру заднего фона)
            self.setStyleSheet(self.styleSheet() + f" color: {color}; font-weight: bold; font-size: 14px;")