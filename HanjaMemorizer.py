"""
한자 암기 프로그램 v4.1
- 로컬 엑셀 파일 로드
- 구글 시트 URL로 로드
- 이전 파일 캐싱 및 드롭다운 선택
- 한자 2초 표시 → 음/뜻/음독/훈독 2초 표시 반복
- 새 시트 양식의 음독/훈독 열 표시
- 창 크기 조절 및 저해상도 환경 대응
- 랜덤 순서로 학습
- 암기완료 토글 기능 (전체모드 / 미암기모드)
"""

import sys
import os
import json
import random
import re
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QFrame, QSpinBox,
    QGroupBox, QProgressBar, QComboBox, QLineEdit, QDialog, QDialogButtonBox,
    QCheckBox, QButtonGroup, QRadioButton, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont


# 캐시 디렉토리 설정 (py파일이 있는 폴더에 저장)
def get_app_dir():
    """py파일이 있는 디렉토리 반환"""
    if getattr(sys, 'frozen', False):
        # exe로 빌드된 경우
        return os.path.dirname(sys.executable)
    else:
        # py파일로 실행하는 경우
        return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()
DATA_DIR = os.path.join(APP_DIR, "data")
CACHE_INDEX_FILE = os.path.join(DATA_DIR, "cache_index.json")
MEMORIZED_FILE = os.path.join(DATA_DIR, "memorized_hanja.json")


def ensure_data_dir():
    """데이터 디렉토리 생성"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def load_cache_index():
    """캐시 인덱스 로드"""
    ensure_data_dir()
    if os.path.exists(CACHE_INDEX_FILE):
        try:
            with open(CACHE_INDEX_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"files": []}
    return {"files": []}


def save_cache_index(index):
    """캐시 인덱스 저장"""
    ensure_data_dir()
    with open(CACHE_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def load_memorized_hanja():
    """암기완료 한자 목록 로드"""
    ensure_data_dir()
    if os.path.exists(MEMORIZED_FILE):
        try:
            with open(MEMORIZED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"memorized": []}
    return {"memorized": []}


def save_memorized_hanja(data):
    """암기완료 한자 목록 저장"""
    ensure_data_dir()
    with open(MEMORIZED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_memorized(hanja):
    """암기완료 한자 추가"""
    data = load_memorized_hanja()
    if hanja not in data["memorized"]:
        data["memorized"].append(hanja)
        save_memorized_hanja(data)
    return data["memorized"]


def remove_memorized(hanja):
    """암기완료 한자 제거"""
    data = load_memorized_hanja()
    if hanja in data["memorized"]:
        data["memorized"].remove(hanja)
        save_memorized_hanja(data)
    return data["memorized"]


def is_memorized(hanja):
    """암기완료 여부 확인"""
    data = load_memorized_hanja()
    return hanja in data["memorized"]


def get_memorized_count():
    """암기완료 한자 개수"""
    data = load_memorized_hanja()
    return len(data["memorized"])


def add_to_cache(name, source_type, source_path, data):
    """데이터를 캐시에 추가"""
    ensure_data_dir()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-_]', '_', name)[:50]
    cache_filename = f"{safe_name}_{timestamp}.json"
    cache_filepath = os.path.join(DATA_DIR, cache_filename)
    
    with open(cache_filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    index = load_cache_index()
    index["files"] = [f for f in index["files"] if f.get("source_path") != source_path]
    
    index["files"].insert(0, {
        "name": name,
        "source_type": source_type,
        "source_path": source_path,
        "cache_file": cache_filename,
        "cached_at": timestamp,
        "count": len(data)
    })
    
    if len(index["files"]) > 20:
        old_files = index["files"][20:]
        index["files"] = index["files"][:20]
        
        for old in old_files:
            old_path = os.path.join(DATA_DIR, old["cache_file"])
            if os.path.exists(old_path):
                os.remove(old_path)
    
    save_cache_index(index)
    return cache_filepath


def load_from_cache(cache_filename):
    """캐시에서 데이터 로드"""
    cache_filepath = os.path.join(DATA_DIR, cache_filename)
    if os.path.exists(cache_filepath):
        with open(cache_filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def extract_google_sheet_id(url):
    """구글 시트 URL에서 ID 추출"""
    patterns = [
        r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
        r'id=([a-zA-Z0-9-_]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_google_sheet_csv_url(sheet_url, gid="0"):
    """구글 시트 CSV 다운로드 URL 생성"""
    sheet_id = extract_google_sheet_id(sheet_url)
    if sheet_id:
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return None


class GoogleSheetDialog(QDialog):
    """구글 시트 URL 입력 다이얼로그"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("구글 시트 불러오기")
        self.setFixedSize(500, 200)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
            }
            QLabel {
                color: white;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #16213e;
                color: white;
                border: 2px solid #0f3460;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #4ecca3;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        info_label = QLabel("구글 시트 URL을 입력하세요.\n(시트가 '링크가 있는 모든 사용자에게 공개'로 설정되어야 합니다)")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://docs.google.com/spreadsheets/d/...")
        layout.addWidget(self.url_input)
        
        name_layout = QHBoxLayout()
        name_label = QLabel("저장 이름:")
        name_layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예: 일본어 한자 1급")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3;
                color: #1a1a2e;
                border: none;
                padding: 8px 20px;
                font-weight: bold;
                border-radius: 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #7ed6b9;
            }
        """)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_url(self):
        return self.url_input.text().strip()
    
    def get_name(self):
        name = self.name_input.text().strip()
        if not name:
            return "구글시트_" + datetime.now().strftime("%Y%m%d")
        return name


class HanjaMemorizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.hanja_list_full = []  # 전체 한자 리스트
        self.hanja_list = []  # 현재 표시할 한자 리스트 (필터링됨)
        self.current_index = 0
        self.showing_hanja = True
        self.is_running = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.toggle_display)
        
        self.hanja_time = 2000
        self.meaning_time = 2000
        
        # 모드: "all" = 전체, "unmemorized" = 미암기만
        self.current_mode = "all"
        
        self.init_ui()
        self.load_cache_dropdown()
        
    def init_ui(self):
        self.setWindowTitle("한자 암기 프로그램 v4.1")
        # 기본 크기는 유지하되, 저해상도 환경에서 사용자가 창을 줄일 수 있게 설정
        self.resize(900, 750)
        self.setMinimumSize(520, 420)
        self.setStyleSheet("background-color: #1a1a2e;")

        # 창을 작게 줄였을 때 내부 영역이 잘리지 않도록 스크롤 영역 사용
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a2e;
                border: none;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background-color: #16213e;
                border: none;
                width: 10px;
                height: 10px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background-color: #4ecca3;
                border-radius: 5px;
            }
        """)

        main_widget = QWidget()
        scroll_area.setWidget(main_widget)
        self.setCentralWidget(scroll_area)

        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 18, 18, 18)
        
        # ===== 파일 로드 영역 =====
        load_frame = QFrame()
        load_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        load_layout = QVBoxLayout(load_frame)
        
        # 첫 번째 줄: 캐시된 파일 선택
        cache_layout = QHBoxLayout()
        
        cache_label = QLabel("📚 저장된 파일:")
        cache_label.setStyleSheet("color: white; font-size: 12px; min-width: 80px;")
        cache_layout.addWidget(cache_label)
        
        self.cache_combo = QComboBox()
        self.cache_combo.setStyleSheet("""
            QComboBox {
                background-color: #0f3460;
                color: white;
                border: none;
                padding: 8px 12px;
                font-size: 12px;
                border-radius: 5px;
                min-width: 300px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid white;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f3460;
                color: white;
                selection-background-color: #4ecca3;
                selection-color: #1a1a2e;
            }
        """)
        cache_layout.addWidget(self.cache_combo, 1)
        
        self.load_cache_btn = QPushButton("불러오기")
        self.load_cache_btn.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3;
                color: #1a1a2e;
                border: none;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7ed6b9;
            }
        """)
        self.load_cache_btn.clicked.connect(self.load_from_cache_selected)
        cache_layout.addWidget(self.load_cache_btn)
        
        load_layout.addLayout(cache_layout)
        
        # 구분선
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #0f3460;")
        load_layout.addWidget(separator)
        
        # 두 번째 줄: 새 파일 로드 버튼들
        new_load_layout = QHBoxLayout()
        
        new_label = QLabel("📁 새 파일:")
        new_label.setStyleSheet("color: white; font-size: 12px; min-width: 80px;")
        new_load_layout.addWidget(new_label)
        
        self.local_btn = QPushButton("💻 로컬 파일 열기")
        self.local_btn.setStyleSheet("""
            QPushButton {
                background-color: #e94560;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
        """)
        self.local_btn.clicked.connect(self.load_local_excel)
        new_load_layout.addWidget(self.local_btn)
        
        self.google_btn = QPushButton("☁️ 구글 시트 불러오기")
        self.google_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5dade2;
            }
        """)
        self.google_btn.clicked.connect(self.load_google_sheet)
        new_load_layout.addWidget(self.google_btn)
        
        new_load_layout.addStretch()
        
        load_layout.addLayout(new_load_layout)
        
        layout.addWidget(load_frame)
        
        # ===== 모드 선택 영역 =====
        mode_frame = QFrame()
        mode_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border-radius: 10px;
                padding: 8px;
            }
        """)
        mode_layout = QHBoxLayout(mode_frame)
        
        mode_label = QLabel("📖 학습 모드:")
        mode_label.setStyleSheet("color: white; font-size: 12px;")
        mode_layout.addWidget(mode_label)
        
        self.mode_all_radio = QRadioButton("전체 한자")
        self.mode_all_radio.setChecked(True)
        self.mode_all_radio.setStyleSheet("""
            QRadioButton {
                color: white;
                font-size: 12px;
                padding: 5px 10px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:checked {
                background-color: #4ecca3;
                border: 2px solid #4ecca3;
                border-radius: 8px;
            }
            QRadioButton::indicator:unchecked {
                background-color: #0f3460;
                border: 2px solid #0f3460;
                border-radius: 8px;
            }
        """)
        self.mode_all_radio.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_all_radio)
        
        self.mode_unmemorized_radio = QRadioButton("미암기 한자만")
        self.mode_unmemorized_radio.setStyleSheet("""
            QRadioButton {
                color: white;
                font-size: 12px;
                padding: 5px 10px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:checked {
                background-color: #e94560;
                border: 2px solid #e94560;
                border-radius: 8px;
            }
            QRadioButton::indicator:unchecked {
                background-color: #0f3460;
                border: 2px solid #0f3460;
                border-radius: 8px;
            }
        """)
        self.mode_unmemorized_radio.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_unmemorized_radio)
        
        mode_layout.addStretch()
        
        # 암기 통계 라벨
        self.memorized_stats_label = QLabel("암기완료: 0개")
        self.memorized_stats_label.setStyleSheet("color: #4ecca3; font-size: 12px; font-weight: bold;")
        mode_layout.addWidget(self.memorized_stats_label)
        
        layout.addWidget(mode_frame)
        
        # ===== 컨트롤 영역 =====
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        control_layout = QHBoxLayout(control_frame)
        
        # 시간 설정
        time_group = QGroupBox("표시 시간 (초)")
        time_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-size: 11px;
                border: 1px solid #0f3460;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        time_layout = QHBoxLayout(time_group)
        
        hanja_label = QLabel("한자:")
        hanja_label.setStyleSheet("color: white;")
        time_layout.addWidget(hanja_label)
        
        self.hanja_time_spin = QSpinBox()
        self.hanja_time_spin.setRange(1, 10)
        self.hanja_time_spin.setValue(2)
        self.hanja_time_spin.setStyleSheet("""
            QSpinBox {
                background-color: #0f3460;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
        """)
        self.hanja_time_spin.valueChanged.connect(self.update_hanja_time)
        time_layout.addWidget(self.hanja_time_spin)
        
        meaning_label = QLabel("음/뜻:")
        meaning_label.setStyleSheet("color: white;")
        time_layout.addWidget(meaning_label)
        
        self.meaning_time_spin = QSpinBox()
        self.meaning_time_spin.setRange(1, 10)
        self.meaning_time_spin.setValue(2)
        self.meaning_time_spin.setStyleSheet("""
            QSpinBox {
                background-color: #0f3460;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
        """)
        self.meaning_time_spin.valueChanged.connect(self.update_meaning_time)
        time_layout.addWidget(self.meaning_time_spin)
        
        control_layout.addWidget(time_group)
        
        control_layout.addStretch()
        
        # 시작/정지 버튼
        self.start_btn = QPushButton("▶ 시작")
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3;
                color: #1a1a2e;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #7ed6b9;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.start_btn.clicked.connect(self.toggle_start)
        control_layout.addWidget(self.start_btn)
        
        # 섞기 버튼
        self.shuffle_btn = QPushButton("🔀 섞기")
        self.shuffle_btn.setEnabled(False)
        self.shuffle_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #f5b041;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.shuffle_btn.clicked.connect(self.shuffle_hanja)
        control_layout.addWidget(self.shuffle_btn)
        
        layout.addWidget(control_frame)
        
        # ===== 상태 표시 =====
        status_layout = QHBoxLayout()
        
        self.file_label = QLabel("파일: 로드되지 않음")
        self.file_label.setStyleSheet("color: #888; font-size: 12px;")
        status_layout.addWidget(self.file_label)
        
        self.count_label = QLabel("총 0개 한자")
        self.count_label.setStyleSheet("color: #888; font-size: 12px;")
        status_layout.addWidget(self.count_label)
        
        self.progress_label = QLabel("진행: 0 / 0")
        self.progress_label.setStyleSheet("color: #4ecca3; font-size: 12px;")
        status_layout.addWidget(self.progress_label)
        
        layout.addLayout(status_layout)
        
        # 프로그레스 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #16213e;
                border: none;
                border-radius: 5px;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #4ecca3;
                border-radius: 5px;
            }
        """)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        
        # ===== 메인 디스플레이 =====
        self.display_frame = QFrame()
        self.display_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border-radius: 20px;
            }
        """)
        display_layout = QVBoxLayout(self.display_frame)
        display_layout.setContentsMargins(30, 16, 30, 24)
        display_layout.setSpacing(6)
        
        # 상단: 암기완료 체크박스
        top_layout = QHBoxLayout()
        top_layout.addStretch()
        
        self.memorized_checkbox = QCheckBox("✓ 암기 완료")
        self.memorized_checkbox.setStyleSheet("""
            QCheckBox {
                color: #4ecca3;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 12px;
                background-color: #0f3460;
                border-radius: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #1a1a2e;
                border: 2px solid #4ecca3;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #4ecca3;
                border: 2px solid #4ecca3;
                border-radius: 4px;
            }
            QCheckBox:hover {
                background-color: #1a4a7a;
            }
        """)
        self.memorized_checkbox.toggled.connect(self.on_memorized_toggled)
        top_layout.addWidget(self.memorized_checkbox)
        
        display_layout.addLayout(top_layout)
        
        # 한자 표시
        self.hanja_label = QLabel("漢字")
        self.hanja_label.setAlignment(Qt.AlignCenter)
        self.hanja_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 150px;
                font-weight: bold;
            }
        """)
        display_layout.addWidget(self.hanja_label)
        
        self.reading_label = QLabel("")
        self.reading_label.setAlignment(Qt.AlignCenter)
        self.reading_label.setWordWrap(True)
        self.reading_label.setStyleSheet("""
            QLabel {
                color: #4ecca3;
                font-size: 48px;
                font-weight: bold;
            }
        """)
        display_layout.addWidget(self.reading_label)
        
        self.meaning_label = QLabel("")
        self.meaning_label.setAlignment(Qt.AlignCenter)
        self.meaning_label.setWordWrap(True)
        self.meaning_label.setStyleSheet("""
            QLabel {
                color: #f39c12;
                font-size: 32px;
            }
        """)
        display_layout.addWidget(self.meaning_label)

        # 음독/훈독 표시 - 기존 뜻 텍스트보다 약 2px 작게 설정
        self.onyomi_label = QLabel("")
        self.onyomi_label.setAlignment(Qt.AlignCenter)
        self.onyomi_label.setWordWrap(True)
        self.onyomi_label.setStyleSheet("""
            QLabel {
                color: #b5ead7;
                font-size: 30px;
            }
        """)
        display_layout.addWidget(self.onyomi_label)

        self.kunyomi_label = QLabel("")
        self.kunyomi_label.setAlignment(Qt.AlignCenter)
        self.kunyomi_label.setWordWrap(True)
        self.kunyomi_label.setStyleSheet("""
            QLabel {
                color: #c7ceea;
                font-size: 30px;
            }
        """)
        display_layout.addWidget(self.kunyomi_label)
        
        layout.addWidget(self.display_frame, 1)
        
        # ===== 네비게이션 =====
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("◀ 이전")
        self.prev_btn.setEnabled(False)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1a4a7a;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        self.prev_btn.clicked.connect(self.prev_hanja)
        nav_layout.addWidget(self.prev_btn)
        
        nav_layout.addStretch()
        
        self.next_btn = QPushButton("다음 ▶")
        self.next_btn.setEnabled(False)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1a4a7a;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        self.next_btn.clicked.connect(self.next_hanja)
        nav_layout.addWidget(self.next_btn)
        
        layout.addLayout(nav_layout)
        
        # 암기 통계 업데이트
        self.update_memorized_stats()
        self.apply_responsive_display_styles(dimmed=False)

    def get_responsive_scale(self):
        """현재 창 크기에 맞춘 글자 축소 비율 반환"""
        width_scale = self.width() / 900
        height_scale = self.height() / 750
        return max(0.45, min(1.0, width_scale, height_scale))

    def scaled_font_size(self, base_size, minimum_size):
        """기준 글자 크기를 창 크기에 맞춰 축소"""
        return max(minimum_size, int(base_size * self.get_responsive_scale()))

    def apply_responsive_display_styles(self, dimmed=False):
        """창 크기에 따라 한자/뜻/음독/훈독 글자 크기를 자동 조절"""
        required_labels = ['hanja_label', 'reading_label', 'meaning_label', 'onyomi_label', 'kunyomi_label']
        if not all(hasattr(self, label_name) for label_name in required_labels):
            return

        hanja_color = "#888888" if dimmed else "#ffffff"
        hanja_size = self.scaled_font_size(150, 68)
        reading_size = self.scaled_font_size(48, 24)
        meaning_size = self.scaled_font_size(32, 18)
        yomikata_size = self.scaled_font_size(30, 16)

        self.hanja_label.setStyleSheet(f"""
            QLabel {{
                color: {hanja_color};
                font-size: {hanja_size}px;
                font-weight: bold;
            }}
        """)
        self.reading_label.setStyleSheet(f"""
            QLabel {{
                color: #4ecca3;
                font-size: {reading_size}px;
                font-weight: bold;
            }}
        """)
        self.meaning_label.setStyleSheet(f"""
            QLabel {{
                color: #f39c12;
                font-size: {meaning_size}px;
            }}
        """)
        self.onyomi_label.setStyleSheet(f"""
            QLabel {{
                color: #b5ead7;
                font-size: {yomikata_size}px;
            }}
        """)
        self.kunyomi_label.setStyleSheet(f"""
            QLabel {{
                color: #c7ceea;
                font-size: {yomikata_size}px;
            }}
        """)

    def resizeEvent(self, event):
        """사용자가 창 크기를 바꾸면 메인 표시 글자도 함께 조정"""
        super().resizeEvent(event)
        if hasattr(self, 'hanja_label'):
            self.apply_responsive_display_styles(dimmed=not self.showing_hanja)
    
    def load_cache_dropdown(self):
        """캐시된 파일 목록을 드롭다운에 로드"""
        self.cache_combo.clear()
        self.cache_combo.addItem("-- 저장된 파일 선택 --", None)
        
        index = load_cache_index()
        for file_info in index.get("files", []):
            display_name = f"{file_info['name']} ({file_info['count']}개)"
            if file_info['source_type'] == 'google':
                display_name = f"☁️ {display_name}"
            else:
                display_name = f"💻 {display_name}"
            self.cache_combo.addItem(display_name, file_info)
    
    def load_from_cache_selected(self):
        """선택된 캐시 파일 로드"""
        file_info = self.cache_combo.currentData()
        if not file_info:
            QMessageBox.warning(self, "알림", "파일을 선택해주세요.")
            return
        
        data = load_from_cache(file_info['cache_file'])
        if data:
            self.hanja_list_full = data
            self.apply_mode_filter()
            self.on_data_loaded(file_info['name'])
        else:
            QMessageBox.critical(self, "오류", "캐시 파일을 찾을 수 없습니다.")
    
    def load_local_excel(self):
        """로컬 엑셀 파일 로드"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "엑셀 파일 선택",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if file_path:
            try:
                df = pd.read_excel(file_path)
                data = self.parse_dataframe(df)
                
                if data:
                    filename = os.path.basename(file_path)
                    name = os.path.splitext(filename)[0]
                    add_to_cache(name, "local", file_path, data)
                    
                    self.hanja_list_full = data
                    self.apply_mode_filter()
                    self.on_data_loaded(name)
                    self.load_cache_dropdown()
                    
                    QMessageBox.information(
                        self,
                        "로드 완료",
                        f"{len(self.hanja_list_full)}개의 한자를 로드했습니다."
                    )
                    
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 읽기 오류:\n{str(e)}")
    
    def load_google_sheet(self):
        """구글 시트에서 로드"""
        dialog = GoogleSheetDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            url = dialog.get_url()
            name = dialog.get_name()
            
            if not url:
                QMessageBox.warning(self, "알림", "URL을 입력해주세요.")
                return
            
            csv_url = get_google_sheet_csv_url(url)
            if not csv_url:
                QMessageBox.critical(self, "오류", "올바른 구글 시트 URL이 아닙니다.")
                return
            
            try:
                df = pd.read_csv(csv_url)
                data = self.parse_dataframe(df)
                
                if data:
                    add_to_cache(name, "google", url, data)
                    
                    self.hanja_list_full = data
                    self.apply_mode_filter()
                    self.on_data_loaded(name)
                    self.load_cache_dropdown()
                    
                    QMessageBox.information(
                        self,
                        "로드 완료",
                        f"구글 시트에서 {len(self.hanja_list_full)}개의 한자를 로드했습니다."
                    )
                else:
                    QMessageBox.warning(self, "알림", "데이터를 찾을 수 없습니다.")
                    
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "오류",
                    f"구글 시트 로드 실패:\n{str(e)}\n\n"
                    "시트가 '링크가 있는 모든 사용자에게 공개'로 설정되어 있는지 확인해주세요."
                )
    
    def parse_dataframe(self, df):
        """데이터프레임에서 한자 데이터 추출
        새 시트 양식: 번호 / 한자 / 음(한국어) / 뜻(한국어) / 페이지 / 음독 / 훈독
        """
        data = []

        # 헤더 앞뒤 공백 제거
        df.columns = [str(col).strip() for col in df.columns]

        def clean_value(value):
            """셀 값을 문자열로 정리"""
            if pd.isna(value):
                return ""
            value = str(value).strip()
            if value.lower() == "nan":
                return ""
            return value

        def get_value(row, column_names, fallback_index=None):
            """헤더명 우선, 없으면 기존 열 번호 방식으로 값 읽기"""
            for column_name in column_names:
                if column_name in row.index:
                    value = clean_value(row[column_name])
                    if value:
                        return value

            if fallback_index is not None and len(row) > fallback_index:
                return clean_value(row.iloc[fallback_index])

            return ""
        
        for _, row in df.iterrows():
            try:
                hanja = get_value(row, ["한자"], 1)
                reading = get_value(row, ["음(한국어)", "음", "한자음"], 2)
                meaning = get_value(row, ["뜻(한국어)", "뜻", "한자뜻"], 3)
                onyomi = get_value(row, ["음독", "音読み", "onyomi", "on"], 5)
                kunyomi = get_value(row, ["훈독", "訓読み", "kunyomi", "kun"], 6)
                
                if hanja and hanja != "한자":
                    data.append({
                        'hanja': hanja,
                        'reading': reading,
                        'meaning': meaning,
                        'onyomi': onyomi,
                        'kunyomi': kunyomi
                    })
            except Exception:
                continue
        
        return data
    
    def on_mode_changed(self, checked):
        """모드 변경 시"""
        if self.mode_all_radio.isChecked():
            self.current_mode = "all"
        else:
            self.current_mode = "unmemorized"
        
        if self.hanja_list_full:
            self.apply_mode_filter()
            self.update_display_after_filter()
    
    def apply_mode_filter(self):
        """현재 모드에 따라 한자 리스트 필터링"""
        if self.current_mode == "all":
            self.hanja_list = self.hanja_list_full.copy()
        else:
            # 미암기 한자만 필터링
            self.hanja_list = [
                h for h in self.hanja_list_full 
                if not is_memorized(h['hanja'])
            ]
        
        random.shuffle(self.hanja_list)
    
    def update_display_after_filter(self):
        """필터링 후 디스플레이 업데이트"""
        if not self.hanja_list:
            if self.current_mode == "unmemorized":
                QMessageBox.information(self, "알림", "모든 한자를 암기했습니다! 🎉")
            self.hanja_label.setText("완료!")
            self.reading_label.setText("")
            self.meaning_label.setText("")
            self.onyomi_label.setText("")
            self.kunyomi_label.setText("")
            self.start_btn.setEnabled(False)
            return
        
        self.current_index = 0
        self.count_label.setText(f"총 {len(self.hanja_list)}개 한자")
        self.progress_bar.setMaximum(len(self.hanja_list))
        self.update_progress()
        self.show_current_hanja()
        self.start_btn.setEnabled(True)
    
    def on_data_loaded(self, name):
        """데이터 로드 완료 시 UI 업데이트"""
        self.file_label.setText(f"파일: {name}")
        self.count_label.setText(f"총 {len(self.hanja_list)}개 한자")
        self.progress_bar.setMaximum(len(self.hanja_list))
        self.progress_bar.setValue(0)
        
        self.start_btn.setEnabled(True)
        self.shuffle_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        
        self.current_index = 0
        self.update_progress()
        self.show_current_hanja()
        self.update_memorized_stats()
    
    def on_memorized_toggled(self, checked):
        """암기완료 체크박스 토글 시"""
        if not self.hanja_list:
            return
        
        current = self.hanja_list[self.current_index]
        hanja = current['hanja']
        
        if checked:
            add_memorized(hanja)
        else:
            remove_memorized(hanja)
        
        self.update_memorized_stats()
    
    def update_memorized_stats(self):
        """암기 통계 업데이트"""
        memorized_count = get_memorized_count()
        total_count = len(self.hanja_list_full) if self.hanja_list_full else 0
        
        if total_count > 0:
            percentage = (memorized_count / total_count) * 100
            self.memorized_stats_label.setText(
                f"암기완료: {memorized_count}/{total_count}개 ({percentage:.1f}%)"
            )
        else:
            self.memorized_stats_label.setText(f"암기완료: {memorized_count}개")
    
    def shuffle_hanja(self):
        if self.hanja_list:
            random.shuffle(self.hanja_list)
            self.current_index = 0
            self.update_progress()
            self.show_current_hanja()
            QMessageBox.information(self, "섞기 완료", "한자 순서를 랜덤으로 섞었습니다.")
    
    def update_hanja_time(self, value):
        self.hanja_time = value * 1000
        
    def update_meaning_time(self, value):
        self.meaning_time = value * 1000
    
    def toggle_start(self):
        if self.is_running:
            self.stop_memorizing()
        else:
            self.start_memorizing()
    
    def start_memorizing(self):
        if not self.hanja_list:
            return
            
        self.is_running = True
        self.start_btn.setText("⏹ 정지")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #e94560;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
        """)
        
        self.showing_hanja = True
        self.show_current_hanja()
        self.timer.start(self.hanja_time)
    
    def stop_memorizing(self):
        self.is_running = False
        self.timer.stop()
        self.start_btn.setText("▶ 시작")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3;
                color: #1a1a2e;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #7ed6b9;
            }
        """)
    
    def toggle_display(self):
        if not self.hanja_list:
            return
            
        if self.showing_hanja:
            self.showing_hanja = False
            self.show_reading_meaning()
            self.timer.start(self.meaning_time)
        else:
            self.showing_hanja = True
            self.current_index = (self.current_index + 1) % len(self.hanja_list)
            self.update_progress()
            self.show_current_hanja()
            self.timer.start(self.hanja_time)
    
    def show_current_hanja(self):
        if not self.hanja_list:
            return
            
        current = self.hanja_list[self.current_index]
        self.hanja_label.setText(current['hanja'])
        self.reading_label.setText("")
        self.meaning_label.setText("")
        self.onyomi_label.setText("")
        self.kunyomi_label.setText("")
        
        # 암기완료 체크박스 상태 업데이트
        self.memorized_checkbox.blockSignals(True)
        self.memorized_checkbox.setChecked(is_memorized(current['hanja']))
        self.memorized_checkbox.blockSignals(False)
        
        self.apply_responsive_display_styles(dimmed=False)
    
    def show_reading_meaning(self):
        if not self.hanja_list:
            return
            
        current = self.hanja_list[self.current_index]
        self.reading_label.setText(current.get('reading', ''))
        self.meaning_label.setText(current.get('meaning', ''))

        onyomi = current.get('onyomi', '').strip()
        kunyomi = current.get('kunyomi', '').strip()
        self.onyomi_label.setText(f"음독: {onyomi}" if onyomi else "")
        self.kunyomi_label.setText(f"훈독: {kunyomi}" if kunyomi else "")
        
        self.apply_responsive_display_styles(dimmed=True)
    
    def update_progress(self):
        if self.hanja_list:
            self.progress_label.setText(f"진행: {self.current_index + 1} / {len(self.hanja_list)}")
            self.progress_bar.setValue(self.current_index + 1)
    
    def prev_hanja(self):
        if not self.hanja_list:
            return
        self.current_index = (self.current_index - 1) % len(self.hanja_list)
        self.showing_hanja = True
        self.update_progress()
        self.show_current_hanja()
        
        if self.is_running:
            self.timer.stop()
            self.timer.start(self.hanja_time)
    
    def next_hanja(self):
        if not self.hanja_list:
            return
        self.current_index = (self.current_index + 1) % len(self.hanja_list)
        self.showing_hanja = True
        self.update_progress()
        self.show_current_hanja()
        
        if self.is_running:
            self.timer.stop()
            self.timer.start(self.hanja_time)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.toggle_start()
        elif event.key() == Qt.Key_Left:
            self.prev_hanja()
        elif event.key() == Qt.Key_Right:
            self.next_hanja()
        elif event.key() == Qt.Key_R:
            self.shuffle_hanja()
        elif event.key() == Qt.Key_M:
            # M키로 암기완료 토글
            self.memorized_checkbox.setChecked(not self.memorized_checkbox.isChecked())


def main():
    app = QApplication(sys.argv)
    
    font = QFont("Malgun Gothic", 10)
    app.setFont(font)
    
    window = HanjaMemorizer()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()