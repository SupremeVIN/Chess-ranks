import sys
import requests
import json
import os
from datetime import datetime
from io import BytesIO
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QGroupBox, QGridLayout,
    QMessageBox, QFrame, QSplitter, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import QRect

# Файл для кеша
CACHE_FILE = "chess_cache.json"
CACHE_DURATION = 3600  # 1 час в секундах

class CacheManager:
    """Менеджер кеширования"""
    def __init__(self):
        self.cache = {}
        self.load_cache()
    
    def load_cache(self):
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
        except:
            self.cache = {}
    
    def save_cache(self):
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def get(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now().timestamp() - entry['timestamp'] < CACHE_DURATION:
                return entry['data']
        return None
    
    def set(self, key, data):
        self.cache[key] = {
            'timestamp': datetime.now().timestamp(),
            'data': data
        }
        self.save_cache()

class RatingFetcher(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, platform, username, game_type):
        super().__init__()
        self.platform = platform
        self.username = username
        self.game_type = game_type
        self.cache_manager = CacheManager()
    
    def run(self):
        try:
            cache_key = f"{self.platform}_{self.username}_{self.game_type}"
            cached_data = self.cache_manager.get(cache_key)
            
            if cached_data:
                self.finished.emit(cached_data)
                return
            
            if self.platform == "Lichess":
                data = self.get_lichess_data()
            else:
                data = self.get_chesscom_data()
            
            self.cache_manager.set(cache_key, data)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))
    
    def get_lichess_data(self):
        url = f"https://lichess.org/api/user/{self.username}"
        headers = {"Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            raise Exception(f"Игрок '{self.username}' не найден на Lichess!")
        elif response.status_code != 200:
            raise Exception(f"Ошибка API Lichess: {response.status_code}")
        
        data = response.json()
        
        if "perfs" in data and self.game_type in data["perfs"]:
            rating = data["perfs"][self.game_type].get("rating")
        else:
            raise Exception(f"Рейтинг для '{self.game_type}' не найден у игрока '{self.username}'!")
        
        stats = {
            'rating': rating,
            'avatar': data.get("avatar", None),
            'username': data.get("username", self.username),
            'joined': data.get("createdAt", None),
            'platform': 'Lichess'
        }
        
        return stats
    
    def get_chesscom_data(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"https://api.chess.com/pub/player/{self.username}/stats"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            raise Exception(f"Игрок '{self.username}' не найден на Chess.com!")
        elif response.status_code == 403:
            raise Exception("Доступ к Chess.com API запрещён. Проверьте подключение или попробуйте позже.")
        elif response.status_code != 200:
            raise Exception(f"Ошибка API Chess.com: {response.status_code}")
        
        data = response.json()
        
        game_map = {
            "bullet": "chess_bullet",
            "blitz": "chess_blitz",
            "rapid": "chess_rapid",
            "classical": "chess_daily",
            "ultraBullet": None
        }
        
        chess_game_type = game_map.get(self.game_type)
        if chess_game_type is None:
            raise Exception(f"Тип игры '{self.game_type}' не поддерживается на Chess.com")
        
        if chess_game_type in data:
            rating = data[chess_game_type].get("last", {}).get("rating")
            if rating is None:
                rating = data[chess_game_type].get("best", {}).get("rating")
        else:
            raise Exception(f"Рейтинг для '{self.game_type}' не найден у игрока '{self.username}'!")
        
        if rating is None:
            raise Exception(f"Рейтинг для '{self.game_type}' не найден у игрока '{self.username}'!")
        
        player_url = f"https://api.chess.com/pub/player/{self.username}"
        player_response = requests.get(player_url, headers=headers, timeout=10)
        player_data = {}
        if player_response.status_code == 200:
            player_data = player_response.json()
        
        stats = {
            'rating': rating,
            'avatar': player_data.get("avatar", None),
            'username': player_data.get("username", self.username),
            'joined': player_data.get("joined", None),
            'platform': 'Chess.com'
        }
        
        return stats

class ChessRatingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("♟ Шахматный рейтинг и ранг")
        self.setMinimumSize(1000, 800)
        self.resize(1200, 900)
        
        # Основной стиль
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d0d0d;
            }
            QWidget {
                background-color: #0d0d0d;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QGroupBox {
                color: #ffffff;
                border: 1px solid #2a2a2a;
                border-radius: 16px;
                margin-top: 12px;
                padding-top: 12px;
                font-size: 14px;
                font-weight: bold;
                background-color: #141414;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 12px 0 12px;
                color: #ffd700;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 2px solid #2a2a2a;
                border-radius: 10px;
                padding: 12px 14px;
                font-size: 14px;
                selection-background-color: #4a6fa5;
            }
            QLineEdit:focus {
                border: 2px solid #4a6fa5;
                background-color: #252525;
            }
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 2px solid #2a2a2a;
                border-radius: 10px;
                padding: 12px 14px;
                font-size: 14px;
            }
            QComboBox:hover {
                border: 2px solid #4a6fa5;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 6px solid #ffffff;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 2px solid #2a2a2a;
                selection-background-color: #4a6fa5;
                padding: 5px;
            }
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 14px 24px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
            QPushButton:pressed {
                background-color: #3a5f95;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #555;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #1a1a1a;
                width: 4px;
                border-radius: 8px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a6fa5;
                border-radius: 8px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Главный сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ===== ЛЕВАЯ ПАНЕЛЬ =====
        left_panel = QWidget()
        left_panel.setFixedWidth(360)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(16)
        left_layout.setContentsMargins(28, 28, 22, 28)
        
        # Заголовок
        title = QLabel("♟ Шахматный рейтинг")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 26px;
            font-weight: bold;
            color: #ffd700;
            padding: 10px;
            letter-spacing: 0.5px;
        """)
        left_layout.addWidget(title)
        
        # Группа ввода
        input_group = QGroupBox("Поиск игрока")
        input_layout = QVBoxLayout()
        input_layout.setSpacing(14)
        input_layout.setContentsMargins(18, 20, 18, 18)
        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)
        
        # Ник
        nick_label = QLabel("👤 Ник:")
        nick_label.setStyleSheet("color: #aaa; font-size: 13px; font-weight: 500;")
        input_layout.addWidget(nick_label)
        self.nick_input = QLineEdit()
        self.nick_input.setPlaceholderText("magnuscarlsen")
        self.nick_input.setText("hikaru")
        input_layout.addWidget(self.nick_input)
        
        # Платформа
        platform_label = QLabel("🌐 Платформа:")
        platform_label.setStyleSheet("color: #aaa; font-size: 13px; font-weight: 500;")
        input_layout.addWidget(platform_label)
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["♛ Lichess", "♚ Chess.com"])
        self.platform_combo.currentTextChanged.connect(self.on_platform_changed)
        input_layout.addWidget(self.platform_combo)
        
        # Игра
        game_label = QLabel("⏱ Игра:")
        game_label.setStyleSheet("color: #aaa; font-size: 13px; font-weight: 500;")
        input_layout.addWidget(game_label)
        self.game_type_combo = QComboBox()
        self.game_type_combo.addItems(["⚡ bullet", "⚡ blitz", "⏳ rapid", "⌛ classical"])
        input_layout.addWidget(self.game_type_combo)
        
        # Кнопка
        self.get_rating_btn = QPushButton("🚀 Получить рейтинг")
        self.get_rating_btn.setMinimumHeight(50)
        self.get_rating_btn.clicked.connect(self.get_rating)
        input_layout.addWidget(self.get_rating_btn)
        
        # Система рангов
        ranks_group = QGroupBox("Система рангов")
        ranks_layout = QVBoxLayout()
        ranks_layout.setSpacing(2)
        ranks_layout.setContentsMargins(16, 14, 16, 14)
        ranks_group.setLayout(ranks_layout)
        left_layout.addWidget(ranks_group)
        
        rank_colors = {
            "SSS": "#FF6B6B", "SS": "#FF9F43", "S": "#FECA57",
            "A": "#54A0FF", "B": "#5F27CD", "C": "#1DD1A1",
            "D": "#10AC84", "E": "#00D2D3", "F": "#48DBFB", "G": "#8395A7"
        }
        
        ranks_info = [
            ("SSS", "2700+", "Супер-гроссмейстер"),
            ("SS", "2500-2699", "Гроссмейстер"),
            ("S", "2400-2499", "Международный мастер"),
            ("A", "2300-2399", "Мастер ФИДЕ"),
            ("B", "2200-2299", "Кандидат в мастера"),
            ("C", "2000-2199", "КМС"),
            ("D", "1800-1999", "Первый разряд"),
            ("E", "1600-1799", "Второй разряд"),
            ("F", "1400-1599", "Третий разряд"),
            ("G", "1000-1399", "Четвёртый разряд"),
            ("H", "<1000", "Начальный уровень")
        ]
        
        for rank, rating, desc in ranks_info:
            color = rank_colors.get(rank, "#888")
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    border: none;
                    border-bottom: 1px solid #1a1a1a;
                    padding: 3px 0;
                }
            """)
            layout = QHBoxLayout(frame)
            layout.setSpacing(8)
            layout.setContentsMargins(0, 0, 0, 0)
            
            rank_label = QLabel(rank)
            rank_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px; min-width: 35px;")
            
            rating_label = QLabel(rating)
            rating_label.setStyleSheet("color: #666; font-size: 12px; min-width: 65px;")
            
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #888; font-size: 11px;")
            
            layout.addWidget(rank_label)
            layout.addWidget(rating_label)
            layout.addWidget(desc_label)
            layout.addStretch()
            ranks_layout.addWidget(frame)
        
        left_layout.addStretch()
        
        # ===== ПРАВАЯ ПАНЕЛЬ =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(16)
        right_layout.setContentsMargins(30, 28, 30, 30)
        
        # Информационная карточка
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background-color: #141414;
                border-radius: 20px;
                border: 1px solid #2a2a2a;
                padding: 24px;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(18)
        
        # Верхняя секция
        top_section = QHBoxLayout()
        top_section.setSpacing(20)
        top_section.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Аватар
        avatar_container = QVBoxLayout()
        avatar_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(130, 130)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 3px solid #4a6fa5;
                border-radius: 12px;
                font-size: 70px;
                color: #ccc;
            }
        """)
        self.avatar_label.setText("👤")
        avatar_container.addWidget(self.avatar_label)
        top_section.addLayout(avatar_container)
        
        # Информация об игроке
        player_info = QVBoxLayout()
        player_info.setSpacing(4)
        
        self.username_display = QLabel("Ожидание ввода")
        self.username_display.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffd700;")
        player_info.addWidget(self.username_display)
        
        self.platform_display = QLabel("🌐 —")
        self.platform_display.setStyleSheet("color: #87ceeb; font-size: 14px;")
        player_info.addWidget(self.platform_display)
        
        self.joined_display = QLabel("📅 Дата регистрации: —")
        self.joined_display.setStyleSheet("color: #666; font-size: 13px;")
        player_info.addWidget(self.joined_display)
        
        self.cache_display = QLabel("")
        self.cache_display.setStyleSheet("color: #4CAF50; font-size: 12px;")
        player_info.addWidget(self.cache_display)
        
        player_info.addStretch()
        top_section.addLayout(player_info)
        
        # Описание ранга
        desc_container = QVBoxLayout()
        desc_container.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        desc_label = QLabel("📌 Описание ранга")
        desc_label.setStyleSheet("color: #87ceeb; font-size: 12px; font-weight: 600; letter-spacing: 0.5px;")
        desc_container.addWidget(desc_label)
        
        self.rank_description = QLabel("Введите данные и нажмите кнопку")
        self.rank_description.setWordWrap(True)
        self.rank_description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.rank_description.setStyleSheet("""
            QLabel {
                color: #ffd700;
                font-size: 13px;
                line-height: 1.4;
                background-color: #1a1a1a;
                border-radius: 12px;
                border-left: 4px solid #ffd700;
                padding: 14px 16px;
                max-height: 100px;
            }
        """)
        desc_container.addWidget(self.rank_description)
        
        top_section.addLayout(desc_container, 2)
        info_layout.addLayout(top_section)
        
        # Средняя секция: ранг и рейтинг
        middle_section = QHBoxLayout()
        middle_section.setSpacing(40)
        middle_section.setAlignment(Qt.AlignmentFlag.AlignCenter)
        middle_section.setContentsMargins(0, 10, 0, 10)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #222; max-height: 1px;")
        info_layout.addWidget(separator)
        
        # Ранг
        rank_container = QVBoxLayout()
        rank_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rank_label = QLabel("РАНГ")
        rank_label.setStyleSheet("font-size: 13px; color: #888; letter-spacing: 1px; font-weight: 500;")
        rank_container.addWidget(rank_label)
        self.rank_display = QLabel("?")
        self.rank_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rank_display.setFixedHeight(90)
        self.rank_display.setMinimumWidth(110)
        self.rank_display.setStyleSheet("""
            QLabel {
                font-size: 72px;
                font-weight: 800;
                background-color: #1e1e1e;
                border-radius: 16px;
                border: 2px solid #ffd700;
                color: #ffd700;
                padding: 8px 24px;
            }
        """)
        rank_container.addWidget(self.rank_display)
        middle_section.addLayout(rank_container)
        
        # Рейтинг
        rating_container = QVBoxLayout()
        rating_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rating_label = QLabel("РЕЙТИНГ")
        rating_label.setStyleSheet("font-size: 13px; color: #888; letter-spacing: 1px; font-weight: 500;")
        rating_container.addWidget(rating_label)
        self.rating_display = QLabel("—")
        self.rating_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_display.setFixedHeight(90)
        self.rating_display.setMinimumWidth(110)
        self.rating_display.setStyleSheet("""
            QLabel {
                font-size: 72px;
                font-weight: 700;
                background-color: #1e1e1e;
                border-radius: 16px;
                border: 1px solid #2a2a2a;
                color: #87ceeb;
                padding: 8px 24px;
            }
        """)
        rating_container.addWidget(self.rating_display)
        middle_section.addLayout(rating_container)
        
        info_layout.addLayout(middle_section)
        
        right_layout.addWidget(info_card)
        right_layout.addStretch()
        
        # Добавляем панели в сплиттер
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([360, 840])
        
        main_layout.addWidget(splitter)
        
        # Инициализация
        self.rating_fetcher = None
        self.cache_manager = CacheManager()
    
    def on_platform_changed(self, text):
        platform = text.split()[-1] if " " in text else text
        self.game_type_combo.clear()
        
        if platform == "Lichess":
            self.game_type_combo.addItems(["⚡ bullet", "⚡ blitz", "⏳ rapid", "⌛ classical", "💥 ultraBullet"])
        else:
            self.game_type_combo.addItems(["⚡ bullet", "⚡ blitz", "⏳ rapid", "⌛ classical"])
    
    def get_rating(self):
        nickname = self.nick_input.text().strip()
        if not nickname:
            QMessageBox.warning(self, "Ошибка", "Введите ник игрока!")
            return
        
        platform = self.platform_combo.currentText().split()[-1]
        game_type = self.game_type_combo.currentText().split()[-1]
        
        self.rating_display.setText("⏳")
        self.rank_display.setText("⏳")
        self.rank_description.setText("Загрузка...")
        self.get_rating_btn.setEnabled(False)
        self.get_rating_btn.setText("⏳ Загрузка...")
        self.username_display.setText(nickname)
        self.platform_display.setText(f"🌐 {platform}")
        self.cache_display.setText("")
        
        self.rating_fetcher = RatingFetcher(platform, nickname, game_type)
        self.rating_fetcher.finished.connect(self.on_rating_received)
        self.rating_fetcher.error.connect(self.on_rating_error)
        self.rating_fetcher.start()
    
    def on_rating_received(self, data):
        rating = data['rating']
        avatar_url = data['avatar']
        username = data['username']
        joined = data['joined']
        platform = data['platform']
        
        self.rating_display.setText(str(rating))
        self.username_display.setText(username)
        self.platform_display.setText(f"🌐 {platform if platform == 'Lichess' else 'Chess.com'}")
        
        cache_key = f"{platform}_{username}_{self.game_type_combo.currentText().split()[-1]}"
        cached_data = self.cache_manager.get(cache_key)
        if cached_data:
            self.cache_display.setText("⚡ Из кеша")
            self.cache_display.setStyleSheet("color: #4CAF50; font-size: 12px;")
        else:
            self.cache_display.setText("🔄 Свежие данные")
            self.cache_display.setStyleSheet("color: #87ceeb; font-size: 12px;")
        
        if joined:
            try:
                if platform == "Lichess":
                    joined_date = datetime.fromtimestamp(joined / 1000)
                else:
                    joined_date = datetime.fromtimestamp(joined)
                self.joined_display.setText(f"📅 Регистрация: {joined_date.strftime('%d.%m.%Y')}")
            except:
                self.joined_display.setText("📅 Дата регистрации: неизвестна")
        else:
            self.joined_display.setText("📅 Дата регистрации: неизвестна")
        
        if avatar_url:
            self.load_avatar(avatar_url)
        else:
            self.avatar_label.setText("♛" if platform == "Lichess" else "♚")
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    border: 3px solid #4a6fa5;
                    border-radius: 12px;
                    font-size: 70px;
                    color: #ccc;
                }
            """)
        
        rank, description, color = self.get_rank(rating)
        self.rank_display.setText(rank)
        self.rank_display.setStyleSheet(f"""
            QLabel {{
                font-size: 72px;
                font-weight: 800;
                background-color: #1e1e1e;
                border-radius: 16px;
                border: 2px solid {color};
                color: {color};
                padding: 8px 24px;
            }}
        """)
        self.rank_description.setText(description)
        
        self.get_rating_btn.setEnabled(True)
        self.get_rating_btn.setText("🚀 Получить рейтинг")
    
    def on_rating_error(self, error_msg):
        QMessageBox.warning(self, "Ошибка", error_msg)
        self.rating_display.setText("❌")
        self.rank_display.setText("—")
        self.rank_description.setText("❌ Ошибка получения данных")
        self.get_rating_btn.setEnabled(True)
        self.get_rating_btn.setText("🚀 Получить рейтинг")
    
    def load_avatar(self, url):
        try:
            if url:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(BytesIO(response.content).getvalue())
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(130, 130, Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                                              Qt.TransformationMode.SmoothTransformation)
                        x = (pixmap.width() - 130) // 2
                        y = (pixmap.height() - 130) // 2
                        pixmap = pixmap.copy(x, y, 130, 130)
                        self.avatar_label.setPixmap(pixmap)
                        self.avatar_label.setText("")
                        self.avatar_label.setStyleSheet("""
                            QLabel {
                                background-color: #1e1e1e;
                                border: 3px solid #4a6fa5;
                                border-radius: 12px;
                                padding: 0;
                            }
                        """)
                        return
            platform = self.platform_combo.currentText().split()[-1]
            self.avatar_label.setText("♛" if platform == "Lichess" else "♚")
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    border: 3px solid #4a6fa5;
                    border-radius: 12px;
                    font-size: 70px;
                    color: #ccc;
                }
            """)
        except:
            platform = self.platform_combo.currentText().split()[-1]
            self.avatar_label.setText("♛" if platform == "Lichess" else "♚")
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    border: 3px solid #4a6fa5;
                    border-radius: 12px;
                    font-size: 70px;
                    color: #ccc;
                }
            """)
    
    def get_rank(self, rating):
        if rating >= 2700:
            return "SSS", "Супер-гроссмейстер (2700+) — Элита мировых шахмат. Игроки этого уровня входят в топ-30 планеты. Они обладают феноменальной памятью, глубочайшим пониманием дебютов и эндшпиля, а также уникальной интуицией. Ошибки — редкость, а каждая партия — это произведение искусства. Здесь играют Карлсен, Каруана, Непомнящий. Попасть сюда — значит войти в историю шахмат.", "#FF6B6B"
        elif rating >= 2500:
            return "SS", "Гроссмейстер (GM) (2500-2699) — Высшее официальное звание ФИДЕ. Гроссмейстер — это профессионал, который прошёл через тысячи турнирных партий. Он видит тактические комбинации на 5–10 ходов вперёд, безупречно разыгрывает сложнейшие эндшпили и может обыграть 99,9% шахматистов мира с завязанными глазами. Это уровень постоянных турниров, работы с секундантами и борьбы за звание чемпиона страны.", "#FF9F43"
        elif rating >= 2400:
            return "S", "Международный мастер (IM) (2400-2499) — Профессионал высокого уровня. Международный мастер — это игрок, который буквально живёт шахматами. Он имеет глубокие знания в дебютной теории, отлично чувствует динамику позиции и редко ошибается даже в цейтноте. Такой игрок может дать фору любому любителю и успешно конкурирует с гроссмейстерами в быстрых шахматах. Это своего рода «чёрный пояс» в мире шахмат.", "#FECA57"
        elif rating >= 2300:
            return "A", "Мастер ФИДЕ (FM) (2300-2399) — Сильный профессиональный игрок. Мастер ФИДЕ — это тот, кто уже получил международное признание. У него отличная тактическая подготовка, он уверенно разыгрывает миттельшпиль и понимает тонкие позиционные нюансы. Такой игрок легко выигрывает у любителей с форой в фигуру и может работать тренером или аналитиком. Это рубеж, за которым начинается настоящий профессионализм.", "#54A0FF"
        elif rating >= 2200:
            return "B", "Кандидат в мастера ФИДЕ (CM) (2200-2299) — Опытный турнирный игрок. Кандидат в мастера — это крепкий шахматист, который уже не допускает грубых тактических ошибок. Он знает основные дебюты за обе стороны, умеет строить позиционные планы и грамотно реализовывать лишнюю пешку в эндшпиле. На этом уровне уже можно претендовать на призовые места в открытых турнирах и успешно противостоять мастерам в рапиде.", "#5F27CD"
        elif rating >= 2000:
            return "C", "Кандидат в мастера спорта (2000-2199) — Очень сильный любитель. Такой игрок уже имеет спортивный разряд и участвует в официальных соревнованиях. Он уверенно побеждает в клубных турнирах, хорошо знает дебютные схемы, умеет считать варианты на 3–4 хода вперёд и не теряет голову в сложных позициях. Это тот уровень, когда шахматы перестают быть просто игрой и становятся серьёзным хобби с турнирной практикой.", "#1DD1A1"
        elif rating >= 1800:
            return "D", "Первый разряд (1800-1999) — Сильный любитель. Игрок первого разряда — это гордость любого шахматного клуба. Он уже имеет системные знания дебютов, уверенно разыгрывает типовые позиции и редко зевает фигуры. Умеет ставить мат в эндшпиле и может дать бой кандидату в мастера в быстрой партии. На этом уровне начинается настоящее понимание позиционной борьбы.", "#10AC84"
        elif rating >= 1600:
            return "E", "Второй разряд (1600-1799) — Опытный любитель. Такой игрок уже прошёл «детские» ошибки. Он знает принципы развития фигур, контролирует центр, не забывает про рокировку. Может увидеть простую тактику в 2–3 хода и понимает, как играть в эндшпиле с равным материалом. Играет регулярно, участвует в турнирах выходного дня и стабильно растёт в рейтинге. До первого разряда — всего пара удачных турниров.", "#00D2D3"
        elif rating >= 1400:
            return "F", "Третий разряд (1400-1599) — Средний любитель. Уверенный игрок, который знает основные правила и уже имеет турнирный опыт. Он не зевает мат в один ход, знает пару дебютов (например, итальянку или испанку) и умеет ставить простые матовые конструкции. Играет осмысленно, но иногда ещё допускает позиционные просчёты. Это самый массовый уровень среди взрослых любителей, играющих в клубах.", "#48DBFB"
        elif rating >= 1000:
            return "G", "Четвёртый разряд (1000-1399) — Начинающий любитель. Игрок, который уже освоил основы: знает ценность фигур, умеет рокироваться, ставить детский мат и видит одноходовые угрозы. Пока ещё не всегда понимает, как строить план в миттельшпиле, но уже не делает грубых ошибок в каждом ходе. Регулярно играет онлайн и постепенно набирает опыт. Главное на этом этапе — больше практики!", "#8395A7"
        else:
            return "H", "Начальный уровень (менее 1000) — Новичок. Только начинает свой путь в шахматах. Знает, как ходят фигуры, но часто забывает про рокировку или ценность пешек. Счёт вариантов ограничен 1–2 ходами, а эндшпиль кажется сложным. Но это самый важный этап — именно здесь закладывается любовь к игре. Ошибки неизбежны, но каждая партия — это шаг вперёд. Рекомендация: больше играть, решать задачи и смотреть лекции для начинающих.", "#888"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = ChessRatingApp()
    window.show()
    sys.exit(app.exec())
