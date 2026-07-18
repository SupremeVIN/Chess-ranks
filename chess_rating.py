import sys
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                             QPushButton, QGroupBox, QGridLayout, QMessageBox,
                             QSizePolicy, QFrame, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from io import BytesIO
from datetime import datetime

class RatingFetcher(QThread):
    """Поток для получения рейтинга без блокировки UI"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, platform, username, game_type):
        super().__init__()
        self.platform = platform
        self.username = username
        self.game_type = game_type
    
    def run(self):
        try:
            if self.platform == "Lichess":
                data = self.get_lichess_data()
            else:
                data = self.get_chesscom_data()
            
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))
    
    def get_lichess_data(self):
        # Получаем основную информацию о пользователе
        url = f"https://lichess.org/api/user/{self.username}"
        headers = {"Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            raise Exception(f"Игрок '{self.username}' не найден на Lichess!")
        elif response.status_code != 200:
            raise Exception(f"Ошибка API Lichess: {response.status_code}")
        
        data = response.json()
        
        # Получаем рейтинг для выбранного типа игры
        if "perfs" in data and self.game_type in data["perfs"]:
            rating = data["perfs"][self.game_type].get("rating")
        else:
            raise Exception(f"Рейтинг для '{self.game_type}' не найден у игрока '{self.username}'!")
        
        stats = {
            'rating': rating,
            'avatar': data.get("avatar", None),
            'username': data.get("username", self.username),
            'joined': data.get("createdAt", None),
            'platform': 'Lichess',
            'total_games': 0,
            'total_wins': 0,
            'total_draws': 0,
            'total_losses': 0,
            'game_stats': {}
        }
        
        # Получаем детальную статистику через отдельные запросы
        game_types = ["bullet", "blitz", "rapid", "classical", "ultraBullet"]
        
        for game_type in game_types:
            try:
                # Используем правильный эндпоинт для получения статистики
                perf_url = f"https://lichess.org/api/user/{self.username}/perf/{game_type}"
                perf_response = requests.get(perf_url, headers=headers, timeout=10)
                
                if perf_response.status_code == 200:
                    perf_data = perf_response.json()
                    
                    # Извлекаем статистику
                    games = perf_data.get("games", 0)
                    wins = perf_data.get("wins", 0)
                    draws = perf_data.get("draws", 0)
                    losses = perf_data.get("losses", 0)
                    rating_val = perf_data.get("rating", 0)
                    
                    stats['game_stats'][game_type] = {
                        'games': games,
                        'wins': wins,
                        'draws': draws,
                        'losses': losses,
                        'rating': rating_val
                    }
                    
                    # Добавляем к общей статистике
                    stats['total_games'] += games
                    stats['total_wins'] += wins
                    stats['total_draws'] += draws
                    stats['total_losses'] += losses
            except Exception as e:
                # Если запрос не удался, пробуем использовать данные из основного запроса
                if "perfs" in data and game_type in data["perfs"]:
                    perf_data = data["perfs"][game_type]
                    games = perf_data.get("games", 0)
                    # Для Lichess в основном запросе нет wins/draws/losses, поэтому оставляем 0
                    # Но мы уже получили данные через отдельный запрос
                    pass
        
        return stats
    
    def get_chesscom_data(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Получаем статистику игрока
        url = f"https://api.chess.com/pub/player/{self.username}/stats"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            raise Exception(f"Игрок '{self.username}' не найден на Chess.com!")
        elif response.status_code == 403:
            raise Exception("Доступ к Chess.com API запрещён. Проверьте подключение или попробуйте позже.")
        elif response.status_code != 200:
            raise Exception(f"Ошибка API Chess.com: {response.status_code}")
        
        data = response.json()
        
        # Получаем рейтинг
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
        
        # Получаем информацию об игроке
        player_url = f"https://api.chess.com/pub/player/{self.username}"
        player_response = requests.get(player_url, headers=headers, timeout=10)
        player_data = {}
        if player_response.status_code == 200:
            player_data = player_response.json()
        
        # Получаем статистику
        stats = {
            'rating': rating,
            'avatar': player_data.get("avatar", None),
            'username': player_data.get("username", self.username),
            'joined': player_data.get("joined", None),
            'platform': 'Chess.com',
            'total_games': 0,
            'total_wins': 0,
            'total_draws': 0,
            'total_losses': 0,
            'game_stats': {}
        }
        
        # Chess.com статистика
        chess_types = {
            'bullet': 'chess_bullet',
            'blitz': 'chess_blitz',
            'rapid': 'chess_rapid',
            'classical': 'chess_daily'
        }
        
        for game_type_key, api_key in chess_types.items():
            if api_key in data:
                game_data = data[api_key]
                games = 0
                wins = 0
                draws = 0
                losses = 0
                rating_val = 0
                
                if 'record' in game_data:
                    wins = game_data['record'].get('win', 0)
                    draws = game_data['record'].get('draw', 0)
                    losses = game_data['record'].get('loss', 0)
                    games = wins + draws + losses
                
                if 'last' in game_data and 'rating' in game_data['last']:
                    rating_val = game_data['last']['rating']
                elif 'best' in game_data and 'rating' in game_data['best']:
                    rating_val = game_data['best']['rating']
                
                stats['game_stats'][game_type_key] = {
                    'games': games,
                    'wins': wins,
                    'draws': draws,
                    'losses': losses,
                    'rating': rating_val
                }
                
                stats['total_games'] += games
                stats['total_wins'] += wins
                stats['total_draws'] += draws
                stats['total_losses'] += losses
        
        return stats

class ChessRatingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Шахматный рейтинг и ранг")
        self.setMinimumSize(1100, 750)
        self.resize(1200, 800)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QWidget {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 14px;
            }
            QGroupBox {
                color: #ffffff;
                border: 2px solid #3a3a3a;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                font-size: 15px;
                font-weight: bold;
                background-color: #252525;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #ffd700;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 2px solid #3a3a3a;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 14px;
                selection-background-color: #4a6fa5;
                min-height: 30px;
            }
            QLineEdit:focus {
                border: 2px solid #4a6fa5;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 2px solid #3a3a3a;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 14px;
                min-height: 30px;
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
                background-color: #2d2d2d;
                color: #ffffff;
                border: 2px solid #3a3a3a;
                selection-background-color: #4a6fa5;
                padding: 5px;
            }
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 15px;
                font-weight: bold;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
            QPushButton:pressed {
                background-color: #3a5f95;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #666;
            }
            #avatar_label {
                background-color: #2d2d2d;
                border: 3px solid #4a6fa5;
                min-width: 120px;
                min-height: 120px;
                max-width: 120px;
                max-height: 120px;
            }
            #rating_label {
                font-size: 32px;
                font-weight: bold;
                color: #87ceeb;
                padding: 10px;
                background-color: #2d2d2d;
                border-radius: 10px;
                min-width: 120px;
            }
            #rank_label {
                font-size: 72px;
                font-weight: bold;
                color: #ffd700;
                padding: 10px;
                background-color: #2d2d2d;
                border-radius: 10px;
                min-height: 90px;
                min-width: 100px;
            }
            #rank_description_label {
                color: #ffd700;
                font-size: 16px;
                padding: 12px 18px;
                background-color: #2d2d2d;
                border-radius: 8px;
                border-left: 4px solid #ffd700;
                min-height: 60px;
            }
            #username_label {
                font-size: 22px;
                font-weight: bold;
                color: #ffd700;
            }
            #info_frame {
                background-color: #252525;
                border-radius: 10px;
                padding: 15px;
            }
            .title_label {
                color: #ffd700;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
            .stat_label {
                color: #87ceeb;
                font-size: 16px;
                font-weight: bold;
            }
            .stat_value {
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
            }
            .section_title {
                color: #ffd700;
                font-size: 16px;
                font-weight: bold;
                padding: 5px 0;
                border-bottom: 1px solid #3a3a3a;
            }
            .progress_bar {
                background-color: #3a3a3a;
                border-radius: 4px;
                min-height: 20px;
                max-height: 20px;
            }
            .progress_bar::chunk {
                border-radius: 4px;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Левая панель - ввод данных
        left_panel = QWidget()
        left_panel.setMaximumWidth(380)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        
        # Заголовок
        title = QLabel("♟ Шахматный рейтинг")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("title_label")
        left_layout.addWidget(title)
        
        # Группа ввода
        input_group = QGroupBox("Введите данные")
        input_layout = QGridLayout()
        input_layout.setSpacing(12)
        input_layout.setContentsMargins(15, 20, 15, 15)
        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)
        
        # Ник игрока
        input_layout.addWidget(QLabel("👤 Ник:"), 0, 0)
        self.nick_input = QLineEdit()
        self.nick_input.setPlaceholderText("magnuscarlsen")
        input_layout.addWidget(self.nick_input, 0, 1)
        
        # Платформа
        input_layout.addWidget(QLabel("🌐 Платформа:"), 1, 0)
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["♛ Lichess", "♚ Chess.com"])
        self.platform_combo.currentTextChanged.connect(self.on_platform_changed)
        input_layout.addWidget(self.platform_combo, 1, 1)
        
        # Тип игры
        input_layout.addWidget(QLabel("⏱ Игра:"), 2, 0)
        self.game_type_combo = QComboBox()
        self.game_type_combo.addItems(["⚡ bullet", "⚡ blitz", "⏳ rapid", "⌛ classical"])
        input_layout.addWidget(self.game_type_combo, 2, 1)
        
        # Кнопка
        self.get_rating_btn = QPushButton("🚀 Получить рейтинг")
        self.get_rating_btn.setMinimumHeight(45)
        self.get_rating_btn.clicked.connect(self.get_rating)
        input_layout.addWidget(self.get_rating_btn, 3, 0, 1, 2)
        
        # Информация о рангах
        info_group = QGroupBox("Система рангов")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        ranks_info = [
            ("SSS", "2700+", "Супер-гроссмейстер"),
            ("SS", "2500-2699", "Гроссмейстер (GM)"),
            ("S", "2400-2499", "Международный мастер (IM)"),
            ("A", "2300-2399", "Мастер ФИДЕ (FM)"),
            ("B", "2200-2299", "Кандидат в мастера (CM)"),
            ("C", "2000-2199", "Кандидат в мастера спорта"),
            ("D", "1800-1999", "Первый разряд"),
            ("E", "1600-1799", "Второй разряд"),
            ("F", "1400-1599", "Третий разряд"),
            ("G", "1000-1399", "Четвёртый разряд")
        ]
        
        for rank, rating, desc in ranks_info:
            rank_label = QLabel(f"<b>{rank}</b>  {rating}  —  {desc}")
            rank_label.setStyleSheet("color: #aaa; font-size: 11px; padding: 2px;")
            info_layout.addWidget(rank_label)
        
        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)
        left_layout.addStretch()
        
        # Правая панель - информация
        right_panel = QWidget()
        right_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        # Информационный фрейм
        info_frame = QFrame()
        info_frame.setObjectName("info_frame")
        info_layout_right = QVBoxLayout(info_frame)
        info_layout_right.setSpacing(15)
        
        # Верхняя часть: аватар, ник и комментарий (справа)
        top_section = QHBoxLayout()
        top_section.setSpacing(20)
        top_section.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Аватар
        avatar_container = QVBoxLayout()
        avatar_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label = QLabel()
        self.avatar_label.setObjectName("avatar_label")
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setText("👤")
        self.avatar_label.setStyleSheet("font-size: 48px; background-color: #2d2d2d; border-radius: 0px;")
        avatar_container.addWidget(self.avatar_label)
        top_section.addLayout(avatar_container)
        
        # Информация об игроке (слева от комментария)
        player_info_container = QVBoxLayout()
        player_info_container.setSpacing(8)
        
        self.username_display = QLabel("Ожидание ввода")
        self.username_display.setObjectName("username_label")
        player_info_container.addWidget(self.username_display)
        
        self.platform_display = QLabel("")
        self.platform_display.setStyleSheet("color: #87ceeb; font-size: 14px;")
        player_info_container.addWidget(self.platform_display)
        
        self.joined_display = QLabel("")
        self.joined_display.setStyleSheet("color: #aaa; font-size: 13px;")
        player_info_container.addWidget(self.joined_display)
        
        player_info_container.addStretch()
        top_section.addLayout(player_info_container)
        
        # Комментарий к рейтингу (справа, занимает всё свободное пространство)
        comment_container = QVBoxLayout()
        comment_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        comment_label = QLabel("📌 Описание ранга:")
        comment_label.setStyleSheet("color: #87ceeb; font-size: 14px; font-weight: bold;")
        comment_container.addWidget(comment_label)
        
        self.rank_description = QLabel("Введите данные и нажмите кнопку")
        self.rank_description.setObjectName("rank_description_label")
        self.rank_description.setWordWrap(True)
        self.rank_description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        comment_container.addWidget(self.rank_description)
        
        top_section.addLayout(comment_container, 2)  # Даём больше места комментарию
        
        info_layout_right.addLayout(top_section)
        
        # Средняя часть: ранг и рейтинг
        middle_section = QHBoxLayout()
        middle_section.setSpacing(30)
        middle_section.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Ранг
        rank_container = QVBoxLayout()
        rank_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rank_container.addWidget(QLabel("РАНГ"))
        self.rank_display = QLabel("?")
        self.rank_display.setObjectName("rank_label")
        self.rank_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rank_container.addWidget(self.rank_display)
        middle_section.addLayout(rank_container)
        
        # Рейтинг
        rating_container = QVBoxLayout()
        rating_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rating_container.addWidget(QLabel("РЕЙТИНГ"))
        self.rating_display = QLabel("—")
        self.rating_display.setObjectName("rating_label")
        self.rating_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rating_container.addWidget(self.rating_display)
        middle_section.addLayout(rating_container)
        
        middle_section.addStretch()
        info_layout_right.addLayout(middle_section)
        
        # Нижняя часть: статистика (Все игры и Текущая игра друг под другом)
        stats_section = QVBoxLayout()
        stats_section.setSpacing(15)
        
        # Заголовок секции статистики
        stats_title = QLabel("📊 Подробная характеристика:")
        stats_title.setObjectName("section_title")
        stats_section.addWidget(stats_title)
        
        # Блок "Все игры"
        all_games_group = QGroupBox("Все игры")
        all_games_layout = QVBoxLayout(all_games_group)
        all_games_layout.setSpacing(8)
        self.create_stats_widget(all_games_layout, "all")
        stats_section.addWidget(all_games_group)
        
        # Блок "Текущая игра"
        current_game_group = QGroupBox("Текущая игра")
        current_game_layout = QVBoxLayout(current_game_group)
        current_game_layout.setSpacing(8)
        self.create_stats_widget(current_game_layout, "current")
        stats_section.addWidget(current_game_group)
        
        info_layout_right.addLayout(stats_section)
        
        info_layout_right.addStretch()
        right_layout.addWidget(info_frame)
        
        # Добавляем панели в главный layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)
        
        # Инициализация
        self.rating_fetcher = None
        self.current_rating = None
    
    def create_stats_widget(self, layout, prefix):
        """Создаёт виджет статистики"""
        # Статистика в сетке
        stats_grid = QGridLayout()
        stats_grid.setSpacing(8)
        stats_grid.setColumnStretch(0, 1)
        stats_grid.setColumnStretch(1, 1)
        
        # Всего игр
        stats_grid.addWidget(QLabel("Всего партий:"), 0, 0)
        label = QLabel("—")
        label.setObjectName(f"{prefix}_games_label")
        label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold;")
        setattr(self, f"{prefix}_games_label", label)
        stats_grid.addWidget(label, 0, 1)
        
        # Победы
        stats_grid.addWidget(QLabel("🏆 Победы:"), 1, 0)
        label = QLabel("—")
        label.setObjectName(f"{prefix}_wins_label")
        label.setStyleSheet("color: #4CAF50; font-size: 18px; font-weight: bold;")
        setattr(self, f"{prefix}_wins_label", label)
        stats_grid.addWidget(label, 1, 1)
        
        # Ничьи
        stats_grid.addWidget(QLabel("🤝 Ничьи:"), 2, 0)
        label = QLabel("—")
        label.setObjectName(f"{prefix}_draws_label")
        label.setStyleSheet("color: #FFC107; font-size: 18px; font-weight: bold;")
        setattr(self, f"{prefix}_draws_label", label)
        stats_grid.addWidget(label, 2, 1)
        
        # Поражения
        stats_grid.addWidget(QLabel("❌ Поражения:"), 3, 0)
        label = QLabel("—")
        label.setObjectName(f"{prefix}_losses_label")
        label.setStyleSheet("color: #f44336; font-size: 18px; font-weight: bold;")
        setattr(self, f"{prefix}_losses_label", label)
        stats_grid.addWidget(label, 3, 1)
        
        # Проценты
        stats_grid.addWidget(QLabel("Проценты:"), 4, 0, 1, 2)
        
        # Прогресс-бары
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(4)
        
        # Победы
        win_layout = QHBoxLayout()
        win_layout.addWidget(QLabel("Победы:"))
        progress = QProgressBar()
        progress.setObjectName(f"{prefix}_win_progress")
        progress.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(True)
        progress.setFormat("%p%")
        setattr(self, f"{prefix}_win_progress", progress)
        win_layout.addWidget(progress)
        progress_layout.addLayout(win_layout)
        
        # Ничьи
        draw_layout = QHBoxLayout()
        draw_layout.addWidget(QLabel("Ничьи:"))
        progress = QProgressBar()
        progress.setObjectName(f"{prefix}_draw_progress")
        progress.setStyleSheet("QProgressBar::chunk { background-color: #FFC107; }")
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(True)
        progress.setFormat("%p%")
        setattr(self, f"{prefix}_draw_progress", progress)
        draw_layout.addWidget(progress)
        progress_layout.addLayout(draw_layout)
        
        # Поражения
        loss_layout = QHBoxLayout()
        loss_layout.addWidget(QLabel("Поражения:"))
        progress = QProgressBar()
        progress.setObjectName(f"{prefix}_loss_progress")
        progress.setStyleSheet("QProgressBar::chunk { background-color: #f44336; }")
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(True)
        progress.setFormat("%p%")
        setattr(self, f"{prefix}_loss_progress", progress)
        loss_layout.addWidget(progress)
        progress_layout.addLayout(loss_layout)
        
        stats_grid.addLayout(progress_layout, 5, 0, 1, 2)
        layout.addLayout(stats_grid)
    
    def on_platform_changed(self, text):
        """Обновляет список игр при смене платформы"""
        platform = text.split()[-1] if " " in text else text
        self.game_type_combo.clear()
        
        if platform == "Lichess":
            self.game_type_combo.addItems(["⚡ bullet", "⚡ blitz", "⏳ rapid", "⌛ classical", "💥 ultraBullet"])
        else:  # Chess.com
            self.game_type_combo.addItems(["⚡ bullet", "⚡ blitz", "⏳ rapid", "⌛ classical"])
    
    def get_rating(self):
        """Запускает получение рейтинга"""
        nickname = self.nick_input.text().strip()
        if not nickname:
            QMessageBox.warning(self, "Ошибка", "Введите ник игрока!")
            return
        
        platform = self.platform_combo.currentText().split()[-1]
        game_type = self.game_type_combo.currentText().split()[-1]
        
        # Очищаем предыдущие результаты
        self.rating_display.setText("⏳")
        self.rank_display.setText("⏳")
        self.rank_description.setText("Загрузка...")
        self.get_rating_btn.setEnabled(False)
        self.username_display.setText(nickname)
        self.platform_display.setText(f"🌐 {platform}")
        
        # Запускаем поток для получения данных
        self.rating_fetcher = RatingFetcher(platform, nickname, game_type)
        self.rating_fetcher.finished.connect(self.on_rating_received)
        self.rating_fetcher.error.connect(self.on_rating_error)
        self.rating_fetcher.start()
    
    def update_stats_widget(self, prefix, games, wins, draws, losses):
        """Обновляет статистику в виджете"""
        games_label = getattr(self, f"{prefix}_games_label", None)
        wins_label = getattr(self, f"{prefix}_wins_label", None)
        draws_label = getattr(self, f"{prefix}_draws_label", None)
        losses_label = getattr(self, f"{prefix}_losses_label", None)
        win_progress = getattr(self, f"{prefix}_win_progress", None)
        draw_progress = getattr(self, f"{prefix}_draw_progress", None)
        loss_progress = getattr(self, f"{prefix}_loss_progress", None)
        
        if games_label:
            games_label.setText(str(games) if games > 0 else "0")
        if wins_label:
            wins_label.setText(str(wins))
        if draws_label:
            draws_label.setText(str(draws))
        if losses_label:
            losses_label.setText(str(losses))
        
        # Вычисляем проценты
        if games > 0:
            win_pct = int((wins / games) * 100)
            draw_pct = int((draws / games) * 100)
            loss_pct = int((losses / games) * 100)
            
            # Корректируем, чтобы сумма была 100%
            total = win_pct + draw_pct + loss_pct
            if total != 100 and total > 0:
                diff = 100 - total
                if win_pct >= draw_pct and win_pct >= loss_pct:
                    win_pct += diff
                elif draw_pct >= win_pct and draw_pct >= loss_pct:
                    draw_pct += diff
                else:
                    loss_pct += diff
            
            if win_progress:
                win_progress.setValue(win_pct)
            if draw_progress:
                draw_progress.setValue(draw_pct)
            if loss_progress:
                loss_progress.setValue(loss_pct)
        else:
            if win_progress:
                win_progress.setValue(0)
            if draw_progress:
                draw_progress.setValue(0)
            if loss_progress:
                loss_progress.setValue(0)
    
    def on_rating_received(self, data):
        """Обработка полученных данных"""
        rating = data['rating']
        avatar_url = data['avatar']
        username = data['username']
        joined = data['joined']
        platform = data['platform']
        
        # Общая статистика
        total_games = data['total_games']
        total_wins = data['total_wins']
        total_draws = data['total_draws']
        total_losses = data['total_losses']
        
        # Статистика текущей игры
        game_type = self.game_type_combo.currentText().split()[-1]
        game_stats = data['game_stats'].get(game_type, {})
        game_games = game_stats.get('games', 0)
        game_wins = game_stats.get('wins', 0)
        game_draws = game_stats.get('draws', 0)
        game_losses = game_stats.get('losses', 0)
        
        self.current_rating = rating
        self.rating_display.setText(str(rating))
        self.username_display.setText(username)
        self.platform_display.setText(f"🌐 {platform}")
        
        # Дата регистрации
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
        
        # Загружаем аватарку
        if avatar_url:
            self.load_avatar(avatar_url)
        else:
            if platform == "Lichess":
                self.avatar_label.setText("♛")
            else:
                self.avatar_label.setText("♚")
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setStyleSheet("font-size: 48px; background-color: #2d2d2d; border-radius: 0px;")
        
        # Определяем ранг
        rank, description = self.get_rank(rating)
        self.rank_display.setText(rank)
        self.rank_description.setText(description)
        
        # Обновляем статистику
        self.update_stats_widget("all", total_games, total_wins, total_draws, total_losses)
        self.update_stats_widget("current", game_games, game_wins, game_draws, game_losses)
        
        self.get_rating_btn.setEnabled(True)
    
    def on_rating_error(self, error_msg):
        """Обработка ошибок"""
        QMessageBox.warning(self, "Ошибка", error_msg)
        self.rating_display.setText("❌")
        self.rank_display.setText("—")
        self.rank_description.setText("❌ Ошибка получения данных")
        self.get_rating_btn.setEnabled(True)
    
    def load_avatar(self, url):
        """Загружает аватарку по URL (квадратную)"""
        try:
            if url:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(BytesIO(response.content).getvalue())
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(120, 120, Qt.AspectRatioMode.IgnoreAspectRatio, 
                                              Qt.TransformationMode.SmoothTransformation)
                        self.avatar_label.setPixmap(pixmap)
                        self.avatar_label.setText("")
                        self.avatar_label.setStyleSheet("background-color: #2d2d2d; border-radius: 0px;")
                        return
            # Если не удалось загрузить, показываем иконку
            platform = self.platform_combo.currentText().split()[-1]
            if platform == "Lichess":
                self.avatar_label.setText("♛")
            else:
                self.avatar_label.setText("♚")
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setStyleSheet("font-size: 48px; background-color: #2d2d2d; border-radius: 0px;")
        except:
            platform = self.platform_combo.currentText().split()[-1]
            if platform == "Lichess":
                self.avatar_label.setText("♛")
            else:
                self.avatar_label.setText("♚")
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setStyleSheet("font-size: 48px; background-color: #2d2d2d; border-radius: 0px;")
    
    def get_rank(self, rating):
        """Определяет ранг на основе рейтинга"""
        if rating >= 2700:
            return "SSS", "Супер-гроссмейстер (2700+) — элита мировых шахмат"
        elif rating >= 2500:
            return "SS", "Международный гроссмейстер (GM) (2500-2699) — высшее звание"
        elif rating >= 2400:
            return "S", "Международный мастер (IM) (2400-2499) — профессионал высокого уровня"
        elif rating >= 2300:
            return "A", "Мастер ФИДЕ (FM) (2300-2399) — сильный профессиональный игрок"
        elif rating >= 2200:
            return "B", "Кандидат в мастера ФИДЕ (CM) (2200-2299) — опытный игрок"
        elif rating >= 2000:
            return "C", "Кандидат в мастера спорта (2000-2199) — очень сильный любитель"
        elif rating >= 1800:
            return "D", "Первый разряд (1800-1999) — сильный любитель"
        elif rating >= 1600:
            return "E", "Второй разряд (1600-1799) — опытный любитель"
        elif rating >= 1400:
            return "F", "Третий разряд (1400-1599) — средний любитель"
        elif rating >= 1000:
            return "G", "Четвёртый разряд (1000-1399) — начинающий любитель"
        else:
            return "H", "Начальный уровень (менее 1000) — новичок"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = ChessRatingApp()
    window.show()
    sys.exit(app.exec())
