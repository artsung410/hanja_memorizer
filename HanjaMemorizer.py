"""
한자 암기 프로그램 v2
- 로컬 엑셀 파일 로드
- 구글 시트 URL로 로드
- 이전 파일 캐싱 및 드롭다운 선택
- 한자 2초 표시 → 음/뜻 2초 표시 반복
- 랜덤 순서로 학습
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
    QGroupBox, QProgressBar, QComboBox, QLineEdit, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont


# 캐시 디렉토리 설정
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".hanja_memorizer")
CACHE_INDEX_FILE = os.path.join(CACHE_DIR, "cache_index.json")


def ensure_cache_dir():
    """캐시 디렉토리 생성"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def load_cache_index():
    """캐시 인덱스 로드"""
    ensure_cache_dir()
    if os.path.exists(CACHE_INDEX_FILE):
        try:
            with open(CACHE_INDEX_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"files": []}
    return {"files": []}


def save_cache_index(index):
    """캐시 인덱스 저장"""
    ensure_cache_dir()
    with open(CACHE_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def add_to_cache(name, source_type, source_path, data):
    """데이터를 캐시에 추가"""
    ensure_cache_dir()
    
    # 캐시 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-_]', '_', name)[:50]
    cache_filename = f"{safe_name}_{timestamp}.json"
    cache_filepath = os.path.join(CACHE_DIR, cache_filename)
    
    # 데이터 저장
    with open(cache_filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 인덱스 업데이트
    index = load_cache_index()
    
    # 중복 제거 (같은 소스 경로)
    index["files"] = [f for f in index["files"] if f.get("source_path") != source_path]
    
    # 새 항목 추가
    index["files"].insert(0, {
        "name": name,
        "source_type": source_type,
        "source_path": source_path,
        "cache_file": cache_filename,
        "cached_at": timestamp,
        "count": len(data)
    })
    
    # 최대 20개까지만 유지
    if len(index["files"]) > 20:
        old_files = index["files"][20:]
        index["files"] = index["files"][:20]
        
        # 오래된 캐시 파일 삭제
        for old in old_files:
            old_path = os.path.join(CACHE_DIR, old["cache_file"])
            if os.path.exists(old_path):
                os.remove(old_path)
    
    save_cache_index(index)
    return cache_filepath


def load_from_cache(cache_filename):
    """캐시에서 데이터 로드"""
    cache_filepath = os.path.join(CACHE_DIR, cache_filename)
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
        
        # 안내 라벨
        info_label = QLabel("구글 시트 URL을 입력하세요.\n(시트가 '링크가 있는 모든 사용자에게 공개'로 설정되어야 합니다)")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # URL 입력
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://docs.google.com/spreadsheets/d/...")
        layout.addWidget(self.url_input)
        
        # 시트 이름 입력
        name_layout = QHBoxLayout()
        name_label = QLabel("저장 이름:")
        name_layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예: 일본어 한자 1급")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # 버튼
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
        self.hanja_list = []
        self.current_index = 0
        self.showing_hanja = True
        self.is_running = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.toggle_display)
        
        self.hanja_time = 2000
        self.meaning_time = 2000
        
        self.init_ui()
        self.load_cache_dropdown()
        
    def init_ui(self):
        self.setWindowTitle("한자 암기 프로그램 v2")
        self.setGeometry(100, 100, 900, 700)
        self.setStyleSheet("background-color: #1a1a2e;")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
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
        self.cache_combo.currentIndexChanged.connect(self.on_cache_selected)
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
        display_frame = QFrame()
        display_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border-radius: 20px;
            }
        """)
        display_layout = QVBoxLayout(display_frame)
        display_layout.setContentsMargins(40, 40, 40, 40)
        
        self.hanja_label = QLabel("漢字")
        self.hanja_label.setAlignment(Qt.AlignCenter)
        self.hanja_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 160px;
                font-weight: bold;
            }
        """)
        display_layout.addWidget(self.hanja_label)
        
        self.reading_label = QLabel("")
        self.reading_label.setAlignment(Qt.AlignCenter)
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
        self.meaning_label.setStyleSheet("""
            QLabel {
                color: #f39c12;
                font-size: 32px;
            }
        """)
        display_layout.addWidget(self.meaning_label)
        
        layout.addWidget(display_frame, 1)
        
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
    
    def on_cache_selected(self, index):
        """캐시 드롭다운 선택 시"""
        pass
    
    def load_from_cache_selected(self):
        """선택된 캐시 파일 로드"""
        file_info = self.cache_combo.currentData()
        if not file_info:
            QMessageBox.warning(self, "알림", "파일을 선택해주세요.")
            return
        
        data = load_from_cache(file_info['cache_file'])
        if data:
            self.hanja_list = data
            random.shuffle(self.hanja_list)
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
                    # 캐시에 저장
                    filename = os.path.basename(file_path)
                    name = os.path.splitext(filename)[0]
                    add_to_cache(name, "local", file_path, data)
                    
                    self.hanja_list = data
                    random.shuffle(self.hanja_list)
                    self.on_data_loaded(name)
                    self.load_cache_dropdown()
                    
                    QMessageBox.information(
                        self,
                        "로드 완료",
                        f"{len(self.hanja_list)}개의 한자를 로드했습니다."
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
                # CSV로 다운로드
                df = pd.read_csv(csv_url)
                data = self.parse_dataframe(df)
                
                if data:
                    # 캐시에 저장
                    add_to_cache(name, "google", url, data)
                    
                    self.hanja_list = data
                    random.shuffle(self.hanja_list)
                    self.on_data_loaded(name)
                    self.load_cache_dropdown()
                    
                    QMessageBox.information(
                        self,
                        "로드 완료",
                        f"구글 시트에서 {len(self.hanja_list)}개의 한자를 로드했습니다."
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
        """데이터프레임에서 한자 데이터 추출"""
        data = []
        
        for _, row in df.iterrows():
            try:
                hanja = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                reading = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ""
                meaning = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ""
                
                if hanja and hanja != "nan" and hanja != "한자":
                    data.append({
                        'hanja': hanja,
                        'reading': reading,
                        'meaning': meaning
                    })
            except:
                continue
        
        return data
    
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
        
        self.hanja_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 160px;
                font-weight: bold;
            }
        """)
    
    def show_reading_meaning(self):
        if not self.hanja_list:
            return
            
        current = self.hanja_list[self.current_index]
        self.reading_label.setText(current['reading'])
        self.meaning_label.setText(current['meaning'])
        
        self.hanja_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 160px;
                font-weight: bold;
            }
        """)
    
    def update_progress(self):
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


def main():
    app = QApplication(sys.argv)
    
    font = QFont("Malgun Gothic", 10)
    app.setFont(font)
    
    window = HanjaMemorizer()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()