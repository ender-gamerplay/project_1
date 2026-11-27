import sys
import random
import os
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow,
                             QMessageBox, QFileDialog, QInputDialog)
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from CellButton import CellButton
from minesweeper_ui import Ui_MainWindow


# Настройки уровней сложности: (ширина, высота, количество мин)
DIFFICULTIES = {
    "Новичок (10x10)": (10, 10, 12),
    "Любитель (16x16)": (16, 16, 40),
    "Профессионал (30x16)": (30, 16, 99)
}

def get_db_path():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "records.db")

class Minesweeper(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        
        self.current_diff_name = "Новичок (10x10)"
        self.cols, self.rows, self.mines_count = DIFFICULTIES[self.current_diff_name]
        
        # Хранилище путей к файлам текстур
        self.textures = {'closed': None, 'opened': None, 'mine': None, 'flag': None}
        
        # Нужно для музыки
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.5)
        self.player.setLoops(QMediaPlayer.Loops.Infinite)

        # Переменные для челленджа Limbo
        self.is_limbo_mode = False
        self.limbo_shuffling = False
        self.limbo_swaps_left = 0
        self.limbo_animations = []
        self.limbo_music_path = None
        self.limbo_music_path = None
        self.limbo_start_ms = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.time_elapsed = 0

        self.start_new_game()
        self.connect_signals()

        self.init_db()


    def connect_signals(self):
        # Меню: Игра
        self.action_new_game.triggered.connect(self.start_new_game)
        self.action_diff_easy.triggered.connect(lambda: self.change_difficulty("Новичок (10x10)"))
        self.action_diff_medium.triggered.connect(lambda: self.change_difficulty("Любитель (16x16)"))
        self.action_diff_hard.triggered.connect(lambda: self.change_difficulty("Профессионал (30x16)"))

        # Меню: Текстуры
        self.action_tex_closed.triggered.connect(lambda: self.load_texture('closed'))
        self.action_tex_opened.triggered.connect(lambda: self.load_texture('opened'))
        self.action_tex_mine.triggered.connect(lambda: self.load_texture('mine'))
        self.action_tex_flag.triggered.connect(lambda: self.load_texture('flag'))
        self.action_tex_reset.triggered.connect(self.reset_textures)

        # Меню: Музыка
        self.action_music_load.triggered.connect(self.load_music)
        self.action_music_toggle.triggered.connect(self.toggle_music)
        self.action_music_stop.triggered.connect(self.stop_music)

        # Меню: Челленджи
        self.action_limbo_start.triggered.connect(self.start_limbo_challenge)
        self.action_limbo_music.triggered.connect(self.load_limbo_music)
        self.action_limbo_timecode.triggered.connect(self.set_limbo_timecode)
        self.action_limbo_exit.triggered.connect(self.exit_limbo_mode)

        # Кнопки верхней панели
        self.restart_btn.clicked.connect(self.start_new_game)
        self.easter_egg_btn.clicked.connect(self.show_easter_egg)

        # Рекорды
        self.action_records.triggered.connect(self.show_records)

    def change_difficulty(self, name):
        self.current_diff_name = name
        self.cols, self.rows, self.mines_count = DIFFICULTIES[name]
        self.start_new_game()
        self.is_limbo_mode = False
        self.current_diff_name = name

    def start_new_game(self):
        self.timer.stop()
        self.time_elapsed = 0
        self.timer_lcd.display(0)
        self.first_click = True
        self.flags_count = 0
        self.revealed_count = 0
        self.cells = {}
        self.restart_btn.setText("😊")
        self.mines_lcd.display(self.mines_count)
        #Переменные для челенджей
        self.timer.stop()
        self.limbo_shuffling = False

        # Очистка старой сетки
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Построение нового поля
        for y in range(self.rows):
            for x in range(self.cols):
                btn = CellButton(x, y)
                # Надежная передача объекта кнопки через lambda
                btn.clicked.connect(lambda checked, b=btn: self.handle_left_click(b))
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.customContextMenuRequested.connect(lambda pos, b=btn: self.handle_right_click(b))
                
                self.grid_layout.addWidget(btn, y, x)
                self.cells[(x, y)] = btn
                btn.refresh_style(self.textures)

        # Исправление бага с размером окна при переключении сложностей
        self.setMinimumSize(QSize(0, 0))
        self.setMaximumSize(QSize(16777215, 16777215))
        self.grid_widget.updateGeometry()
        self.centralWidget().updateGeometry()
        self.resize(self.centralWidget().sizeHint())
        self.adjustSize()

    def update_timer(self):
        if self.time_elapsed < 999:
            self.time_elapsed += 1
            self.timer_lcd.display(self.time_elapsed)

    def generate_mines(self, first_x, first_y):
        # Формируем безопасную зону 3x3 вокруг первого клика (сам клик + все его соседи).
        # Это гарантирует, что у первой клетки будет 0 мин вокруг, и откроется большая область.
        safe_zone = set()
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                safe_zone.add((first_x + dx, first_y + dy))

        # Исключаем безопасную зону из списка возможных мест для мин
        all_positions = [
            (x, y) for x in range(self.cols) for y in range(self.rows)
            if (x, y) not in safe_zone
        ]

        # Защита на случай, если поле слишком маленькое для выбранного числа мин
        if len(all_positions) < self.mines_count:
            all_positions = [
                (x, y) for x in range(self.cols) for y in range(self.rows)
                if (x, y) != (first_x, first_y)
            ]

        actual_mines = min(self.mines_count, len(all_positions))
        mine_positions = random.sample(all_positions, actual_mines)

        for x, y in mine_positions:
            self.cells[(x, y)].is_mine = True

        # Подсчёт мин вокруг каждой клетки
        for (x, y), btn in self.cells.items():
            if btn.is_mine:
                continue
            count = 0
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    nx, ny = x + dx, y + dy
                    if (nx, ny) in self.cells and self.cells[(nx, ny)].is_mine:
                        count += 1
            btn.adjacent_mines = count

    def handle_left_click(self, btn):
        if self.limbo_shuffling or self.is_limbo_mode:
            return
        if btn.is_flagged:
            return

        # Если клетка уже открыта — запускаем открытие соседей (аккорд)
        if btn.is_revealed:
            self.chord_cell(btn)
            return

        if self.first_click:
            self.first_click = False
            self.generate_mines(btn.x, btn.y)
            self.timer.start(1000)

        if btn.is_mine:
            self.game_over(won=False)
        else:
            self.reveal_cell(btn)
            
        if self.revealed_count == (self.cols * self.rows) - self.mines_count:
            self.game_over(won=True)

    def chord_cell(self, btn):
        """Открытие соседних закрытых клеток без флагов при клике на открытую цифру"""
        if btn.adjacent_mines == 0:
            return

        neighbors = []
        flagged_neighbors = 0

        # Собираем всех соседей и считаем флаги вокруг
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = btn.x + dx, btn.y + dy
                if (nx, ny) in self.cells:
                    neighbor = self.cells[(nx, ny)]
                    neighbors.append(neighbor)
                    if neighbor.is_flagged:
                        flagged_neighbors += 1

        # Срабатывает, только если количество флагов совпадает с цифрой на клетке
        if flagged_neighbors != btn.adjacent_mines:
            return

        hit_mine = False
        for neighbor in neighbors:
            if not neighbor.is_revealed and not neighbor.is_flagged:
                if neighbor.is_mine:
                    hit_mine = True
                else:
                    self.reveal_cell(neighbor)

        # Проверяем поражение или победу после открытия соседей
        if hit_mine:
            self.game_over(won=False)
        elif self.revealed_count == (self.cols * self.rows) - self.mines_count:
            self.game_over(won=True)

    def handle_right_click(self, btn):
        if self.limbo_shuffling or btn.is_revealed:
            return
            
        btn.is_flagged = not btn.is_flagged
        if btn.is_flagged:
            self.flags_count += 1
        else:
            self.flags_count -= 1
        self.mines_lcd.display(self.mines_count - self.flags_count)
        btn.refresh_style(self.textures)

        # Проверка победы/поражения в челлендже Limbo сразу после установки флага
        if self.is_limbo_mode and btn.is_flagged:
            self.game_over(won=btn.is_mine)

    def reveal_cell(self, btn):
        if btn.is_revealed or btn.is_flagged:
            return
        btn.is_revealed = True
        self.revealed_count += 1
        btn.refresh_style(self.textures)
        if btn.adjacent_mines == 0 and not btn.is_mine:
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    nx, ny = btn.x + dx, btn.y + dy
                    if (nx, ny) in self.cells:
                        self.reveal_cell(self.cells[(nx, ny)])
    def game_over(self, won):
        self.timer.stop()
        self.restart_btn.setText("😎" if won else "😵")
        for btn in self.cells.values():
            if btn.is_mine:
                btn.is_revealed = True
                btn.refresh_style(self.textures)

        # Запись рекорда при победе
        if won:
            mode_name = "LIMBO" if self.is_limbo_mode else self.current_diff_name
            name, ok = QInputDialog.getText(
                self,
                "Новый рекорд!",
                f"Вы победили за {self.time_elapsed} сек.!\nВведите ваше имя для таблицы рекордов:",
                text="Игрок"
            )
            if ok:
                clean_name = name.strip() or "Аноним"
                self.save_record(clean_name, mode_name, self.time_elapsed)

        title = "Победа!" if won else "Игра окончена"
        text = "Вы успешно разминировали поле!" if won else "Вы подорвались на мине!"
        reply = QMessageBox.question(
            self, title, text + f"\nВремя: {self.time_elapsed} сек.\nХотите сыграть еще раз?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.is_limbo_mode:
                self.start_limbo_challenge()
            else:
                self.start_new_game()


    def load_texture(self, texture_type):
        file_filter = "Изображения (*.png *.jpg *.jpeg *.bmp)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", file_filter)
        if file_path:
            self.textures[texture_type] = file_path
        # Принудительно заставляем каждую плитку перерисоваться под новый набор текстур
        for btn in self.cells.values():
            btn.refresh_style(self.textures)

    def reset_textures(self):
        self.textures = {'closed': None, 'opened': None, 'mine': None, 'flag': None}
        for btn in self.cells.values():
            btn.refresh_style(self.textures)

    def load_music(self):
        file_filter = "Аудиофайлы (*.mp3 *.wav *.ogg *.flac)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите фоновую музыку", "", file_filter)
        if file_path:
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.play()
            self.action_music_toggle.setEnabled(True)

    def toggle_music(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop_music(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.action_music_toggle.setEnabled(True)

    def load_limbo_music(self):
        file_filter = "Аудиофайлы (*.mp3 *.wav *.ogg *.flac)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите музыку для LIMBO", "", file_filter)
        if file_path:
            self.limbo_music_path = file_path
            self.set_limbo_timecode()

    def on_playback_state_changed(self, state):
        """Перемотка срабатывает строго в момент начала воспроизведения"""
        if state == QMediaPlayer.PlaybackState.PlayingState and self.pending_seek_ms is not None:
            seek_pos = self.pending_seek_ms
            self.pending_seek_ms = None
            # Вызываем перемотку сразу и дублируем через 50 мс для капризных MP3-кодеков Windows
            self.player.setPosition(seek_pos)
            QTimer.singleShot(50, lambda: self.player.setPosition(seek_pos))



    def exit_limbo_mode(self):
        """Выход из челленджа обратно в стандартный сапёр"""
        self.is_limbo_mode = False
        self.limbo_shuffling = False
        self.cols, self.rows, self.mines_count = DIFFICULTIES[self.current_diff_name]
        self.start_new_game()

    def start_limbo_challenge(self):
        """Запуск челленджа Limbo: показ бомбы -> 20 перемешиваний -> выбор флагом"""
        # Если музыка для Limbo не выбрана, предлагаем выбрать (можно нажать Отмена)
        if self.limbo_music_path:
            target_url = QUrl.fromLocalFile(self.limbo_music_path)
            if self.player.source() == target_url:
                # Если трек уже загружен в плеер — перематываем сразу
                self.player.setPosition(self.limbo_start_ms)
            else:
                # Если загружаем впервые — ставим в очередь на перемотку после загрузки
                self.pending_seek_ms = self.limbo_start_ms
                self.player.setSource(target_url)
            
            self.player.play()
            self.action_music_toggle.setEnabled(True)


        self.is_limbo_mode = True
        self.limbo_shuffling = True
        self.cols, self.rows, self.mines_count = 4, 2, 1  # 8 ключей (4x2), 1 мина
        self.start_new_game()

        # Увеличим размер клеток для зрелищности
        for btn in self.cells.values():
            btn.setFixedSize(QSize(55, 55))
        self.adjustSize()

        # Прячем 1 мину в случайную клетку и временно показываем её игроку
        mine_pos = random.choice(list(self.cells.keys()))
        mine_btn = self.cells[mine_pos]
        mine_btn.is_mine = True
        mine_btn.is_revealed = True
        mine_btn.refresh_style(self.textures)
        self.restart_btn.setText("👀")

        # Через 1 секунду закрываем мину и запускаем 20 перемешиваний
        QTimer.singleShot(1000, lambda: self.begin_limbo_shuffle(mine_btn))

    def begin_limbo_shuffle(self, mine_btn):
        """Закрытие мины и старт серии из 20 обменов"""
        if not self.is_limbo_mode:
            return
        mine_btn.is_revealed = False
        mine_btn.refresh_style(self.textures)
        self.restart_btn.setText("🌀")
        self.limbo_swaps_left = 20
        self.perform_limbo_swap()

    def perform_limbo_swap(self):
        """Один шаг синхронного перемешивания всех 8 клеток крест-накрест"""
        if not self.is_limbo_mode:
            return

        if self.limbo_swaps_left <= 0:
            self.limbo_shuffling = False
            self.restart_btn.setText("🔑")  # Можно ставить флаг!
            return

        self.limbo_swaps_left -= 1

        # 4 варианта перекрёстного обмена для сетки 4x2 (верхний ряд y=0, нижний y=1)
        patterns = [
            # 1. Двойной крест (левый квадрат 2x2 крест-накрест + правый квадрат 2x2 крест-накрест)
            {
                (0, 0): (1, 1), (1, 1): (0, 0),
                (1, 0): (0, 1), (0, 1): (1, 0),
                (2, 0): (3, 1), (3, 1): (2, 0),
                (3, 0): (2, 1), (2, 1): (3, 0),
            },
            # 2. Большой X-крест (крайние меняются по большой диагонали, центральные — по малой)
            {
                (0, 0): (3, 1), (3, 1): (0, 0),
                (3, 0): (0, 1), (0, 1): (3, 0),
                (1, 0): (2, 1), (2, 1): (1, 0),
                (2, 0): (1, 1), (1, 1): (2, 0),
            },
            # 3. Перекрёстный сдвиг (верх уходит вниз со сдвигом, низ — вверх со сдвигом)
            {
                (0, 0): (1, 1), (1, 0): (2, 1), (2, 0): (3, 1), (3, 0): (0, 1),
                (0, 1): (3, 0), (1, 1): (0, 0), (2, 1): (1, 0), (3, 1): (2, 0),
            },
            # 4. Встречный крест (крайние идут в центр по диагонали, центр — по краям)
            {
                (0, 0): (2, 1), (2, 1): (0, 0),
                (3, 0): (1, 1), (1, 1): (3, 0),
                (1, 0): (3, 1), (3, 1): (1, 0),
                (2, 0): (0, 1), (0, 1): (2, 0),
            }
        ]

        move_map = random.choice(patterns)

        # Запоминаем текущие кнопки и их экранные координаты до перестановки
        old_cells = dict(self.cells)
        start_positions = {pos: btn.pos() for pos, btn in old_cells.items()}

        # Обновляем логические позиции в словаре и в сетке QGridLayout
        for src_pos, dst_pos in move_map.items():
            btn = old_cells[src_pos]
            self.cells[dst_pos] = btn
            btn.x, btn.y = dst_pos
            self.grid_layout.addWidget(btn, dst_pos[1], dst_pos[0])

        # Создаём группу параллельных анимаций для всех 8 клеток (330 мс * 20 = 6.6 сек)
        self.limbo_anim_group = QParallelAnimationGroup()
        duration = 330

        for src_pos, dst_pos in move_map.items():
            btn = old_cells[src_pos]
            anim = QPropertyAnimation(btn, b"pos")
            anim.setDuration(duration)
            anim.setStartValue(start_positions[src_pos])
            anim.setEndValue(start_positions[dst_pos])
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self.limbo_anim_group.addAnimation(anim)

        self.limbo_anim_group.finished.connect(self.perform_limbo_swap)
        self.limbo_anim_group.start()

    def set_limbo_timecode(self):
        """Ввод стартового тайм-кода в формате ММ:СС или в секундах"""
        current_sec = self.limbo_start_ms // 1000
        default_text = f"{current_sec // 60}:{current_sec % 60:02d}"
        
        text, ok = QInputDialog.getText(
            self,
            "Тайм-код для LIMBO",
            "Введите время старта (например, 1:45 или 105):",
            text=default_text
        )
        if ok and text.strip():
            try:
                parts = text.strip().replace(",", ".").split(":")
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = float(parts[1])
                    total_seconds = minutes * 60 + seconds
                elif len(parts) == 1:
                    total_seconds = float(parts[0])
                else:
                    raise ValueError
                
                self.limbo_start_ms = max(0, int(total_seconds * 1000))
            except ValueError:
                QMessageBox.warning(self, "Ошибка", "Неверный формат! Используйте ММ:СС (например, 1:45) или секунды.")

    def show_easter_egg(self):
        QMessageBox.information(self, "Секрет", "Поздравляю вы нашли пасхалку!")

    def init_db(self):
        """Создание SQL-таблицы рекордов при первом запуске"""
        with sqlite3.connect(get_db_path()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    time_seconds INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def save_record(self, player_name, difficulty, time_seconds):
        """Сохранение новой победы в SQL-таблицу"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with sqlite3.connect(get_db_path()) as conn:
            conn.execute(
                "INSERT INTO records (player_name, difficulty, time_seconds, created_at) VALUES (?, ?, ?, ?)",
                (player_name, difficulty, time_seconds, now)
            )

    def show_records(self):
        """Окно просмотра топ-10 лучших результатов"""
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.execute(
                "SELECT player_name, difficulty, time_seconds, created_at FROM records ORDER BY time_seconds ASC LIMIT 10"
            )
            rows = cursor.fetchall()

        if not rows:
            QMessageBox.information(self, "Таблица рекордов", "Рекордов пока нет. Победите в игре, чтобы стать первым!")
            return

        lines = ["🏆 ТОП-10 РЕКОРДОВ:\n"]
        for i, (name, diff, sec, date) in enumerate(rows, start=1):
            lines.append(f"{i}. {name} — {sec} сек. [{diff}] ({date})")

        QMessageBox.information(self, "Таблица рекордов", "\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = Minesweeper()
    game.show()
    sys.exit(app.exec())