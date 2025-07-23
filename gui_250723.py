import sys
import os
import webbrowser
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QComboBox, QFileDialog,
    QVBoxLayout, QHBoxLayout, QProgressBar, QSizePolicy, QInputDialog, QMessageBox
)
from PyQt5.QtGui import QFontDatabase, QFont, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# OCR & Excel 모듈
from gemini_receipt_ocr_250722 import process_receipts
from excel_writer_250722 import generate_excel

# ===== 경로 설정 =====
base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

TITLE_FONT_PATH = os.path.join(base_path, "font", "SacheonHangGong-Regular.ttf")
BODY_FONT_PATH = os.path.join(base_path, "font", "KoPubWorld Dotum Bold.ttf")
LOGO_PATH = os.path.join(base_path, "insert_image", "logo.png")
ICON_PATH = os.path.join(base_path, "insert_image", "icon.png")
TEMPLATE_PATH = os.path.join(base_path, "reciept_format", "영수증계산기.xlsx")

HELP_URL = "https://endurable-bucket-1af.notion.site/238db291835e8087b298f3083f9f153f?source=copy_link"

# ✅ 직원명 리스트
EMPLOYEE_NAMES = [
    "최종화", "김종곤", "박종철", "조경현", "최홍영", "김호선", "박다혜", "강윤영",
    "박상현", "정지은", "김민주", "유호정", "최윤선", "권익준",
    "김익현", "김호연", "이한울", "장수현", "장현조", "최창원",
    "김동빈", "박성진"
]

# ===== 스레드 클래스 =====
class ProcessThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(int, str)

    def __init__(self, api_key, image_files, save_folder):
        super().__init__()
        self.api_key = api_key
        self.image_files = image_files
        self.save_folder = save_folder

    def run(self):
        try:
            output_text_folder = os.path.join(self.save_folder, "텍스트결과")
            output_excel = os.path.join(self.save_folder, "교통비_결과.xlsx")

            # ✅ API Key + 직원명 리스트 전달
            total = process_receipts(
                self.api_key,
                self.image_files,
                output_text_folder,
                EMPLOYEE_NAMES,
                progress_callback=lambda val: self.progress.emit(val)
            )

            generate_excel(
                output_text_folder,
                TEMPLATE_PATH,
                output_excel,
                progress_callback=lambda val: self.progress.emit(val)
            )

            self.finished.emit(total, output_excel)
        except Exception as e:
            print("오류 발생:", e)
            self.finished.emit(0, "")


# ===== 드래그앤드랍 가능한 QLabel =====
class DropLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.parent_widget = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.parent_widget:
            self.parent_widget.select_receipts()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("border:2px dashed #0080FF; border-radius:10px; background-color:#f0f8ff;")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("border:2px dashed #00AFFF; border-radius:10px;")

    def dropEvent(self, event):
        self.setStyleSheet("border:2px dashed #00AFFF; border-radius:10px;")
        
        if self.parent_widget:
            image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff')
            dropped_files = []
            
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(image_extensions):
                    dropped_files.append(file_path)
            
            if dropped_files:
                self.parent_widget.add_image_files(dropped_files)
                event.acceptProposedAction()


# ===== 메인 GUI 클래스 =====
class ReceiptApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("영수증정리프로그램 25.07 Ver1")
        self.setFixedSize(500, 600)
        self.setStyleSheet("background-color: white;")
        self.image_files = []
        self.save_folder = ""

        self.setup_fonts()
        self.initUI()

    def setup_fonts(self):
        try:
            title_font_id = QFontDatabase.addApplicationFont(TITLE_FONT_PATH)
            body_font_id = QFontDatabase.addApplicationFont(BODY_FONT_PATH)
            
            if title_font_id != -1 and body_font_id != -1:
                title_family = QFontDatabase.applicationFontFamilies(title_font_id)[0]
                body_family = QFontDatabase.applicationFontFamilies(body_font_id)[0]
                self.TITLE_FONT = QFont(title_family, 24)
                self.SUBHEADER_FONT = QFont(body_family, 14, QFont.Bold)
                self.BODY_FONT = QFont(body_family, 11)
                self.PROGRESS_FONT = QFont(body_family, 16, QFont.Bold)
            else:
                raise Exception("Font loading failed")
        except:
            self.TITLE_FONT = QFont("맑은 고딕", 24)
            self.SUBHEADER_FONT = QFont("맑은 고딕", 14, QFont.Bold)
            self.BODY_FONT = QFont("맑은 고딕", 11)
            self.PROGRESS_FONT = QFont("맑은 고딕", 16, QFont.Bold)

    def initUI(self):
        # 제목
        self.title_label = QLabel("영수증정리프로그램")
        self.title_label.setFont(self.TITLE_FONT)
        self.title_label.setAlignment(Qt.AlignCenter)

        # help 버튼
        self.help_btn = QPushButton("help")
        self.help_btn.setFont(self.BODY_FONT)
        self.help_btn.setFixedSize(70, 30)
        self.help_btn.setStyleSheet("background-color:#00AFFF; color:white; border-radius:5px;")
        self.help_btn.clicked.connect(lambda: webbrowser.open(HELP_URL))
        help_layout = QHBoxLayout()
        help_layout.addStretch()
        help_layout.addWidget(self.help_btn)

        # 본부선택(준비중)
        self.dept_label = QLabel("본부선택(준비중)")
        self.dept_label.setFont(self.SUBHEADER_FONT)
        self.dept_label.setStyleSheet("color:#adadad;")
        self.dept_combo = QComboBox()
        self.dept_combo.addItems(["준비중"])
        self.dept_combo.setEnabled(False)
        dept_layout = QHBoxLayout()
        dept_layout.addWidget(self.dept_label)
        dept_layout.addWidget(self.dept_combo)

        # 영수증 업로드
        self.upload_header = QLabel("영수증 업로드")
        self.upload_header.setFont(self.SUBHEADER_FONT)
        
        self.drop_area = DropLabel(self)
        self.drop_area.setText("Drag & drop\n파일 직접선택")
        self.drop_area.setFont(self.BODY_FONT)
        self.drop_area.setStyleSheet("border:2px dashed #00AFFF; border-radius:10px;")
        self.drop_area.setAlignment(Qt.AlignCenter)
        self.drop_area.setFixedHeight(90)

        self.reupload_btn = QPushButton("재업로드")
        self.reupload_btn.setFont(self.BODY_FONT)
        self.reupload_btn.setStyleSheet("background-color:#00AFFF; color:white; border-radius:5px;")
        self.reupload_btn.clicked.connect(self.reset_to_initial)
        self.reupload_btn.hide()

        # 기존데이터 수정(준비중)
        self.modify_header = QLabel("기존데이터 수정(준비중)")
        self.modify_header.setFont(self.SUBHEADER_FONT)
        self.modify_header.setStyleSheet("color:#adadad;")

        self.excel_btn = QPushButton("excel")
        self.excel_btn.setFont(self.BODY_FONT)
        self.excel_btn.setFixedHeight(50)
        self.excel_btn.setStyleSheet("background-color:#d3d3d3; color:white; border-radius:5px;")
        self.excel_btn.setEnabled(False)

        self.add_btn = QPushButton("추가영수증")
        self.add_btn.setFont(self.BODY_FONT)
        self.add_btn.setFixedHeight(50)
        self.add_btn.setStyleSheet("background-color:#d3d3d3; color:white; border-radius:5px;")
        self.add_btn.setEnabled(False)

        modify_layout = QHBoxLayout()
        modify_layout.addWidget(self.excel_btn)
        modify_layout.addWidget(self.add_btn)

        # 실행 버튼
        self.run_btn = QPushButton("실행")
        self.run_btn.setFont(QFont(self.BODY_FONT.family(), 14, QFont.Bold))
        self.run_btn.setFixedSize(120, 50)
        self.run_btn.setStyleSheet("background-color:#00AFFF; color:white; border-radius:8px;")
        self.run_btn.clicked.connect(self.choose_save_folder)
        run_layout = QHBoxLayout()
        run_layout.addStretch()
        run_layout.addWidget(self.run_btn)
        run_layout.addStretch()

        # 진행 UI
        self.progress_icon = QLabel()
        if os.path.exists(ICON_PATH):
            self.progress_icon.setPixmap(QPixmap(ICON_PATH).scaled(300, 300, Qt.KeepAspectRatio))
        self.progress_icon.hide()

        self.progress_msg = QLabel("처리중입니다")
        self.progress_msg.setFont(self.PROGRESS_FONT)
        self.progress_msg.setAlignment(Qt.AlignCenter)
        self.progress_msg.hide()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress_bar.setStyleSheet("QProgressBar::chunk {background-color:#00AFFF;}")
        self.progress_bar.hide()

        self.percent_label = QLabel("0%")
        self.percent_label.setFont(self.PROGRESS_FONT)
        self.percent_label.setAlignment(Qt.AlignRight)
        self.percent_label.hide()

        progress_bar_layout = QHBoxLayout()
        progress_bar_layout.addWidget(self.progress_bar, stretch=1)
        progress_bar_layout.addWidget(self.percent_label)

        self.main_button = QPushButton("메인으로")
        self.main_button.setFont(QFont(self.BODY_FONT.family(), 12, QFont.Bold))
        self.main_button.setStyleSheet("background-color:#00AFFF; color:white; border-radius:5px;")
        self.main_button.setFixedSize(100, 40)
        self.main_button.hide()
        self.main_button.clicked.connect(self.reset_ui)

        self.progress_layout = QVBoxLayout()
        self.progress_layout.setSpacing(5)
        self.progress_layout.addWidget(self.progress_icon, alignment=Qt.AlignCenter)
        self.progress_layout.addSpacing(5)
        self.progress_layout.addWidget(self.progress_msg, alignment=Qt.AlignCenter)
        self.progress_layout.addSpacing(5)
        self.progress_layout.addLayout(progress_bar_layout)
        self.progress_layout.addSpacing(5)
        self.progress_layout.addWidget(self.main_button, alignment=Qt.AlignCenter)

        # 로고
        self.logo_label = QLabel()
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH).scaledToWidth(150, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignCenter)

        # 메인 레이아웃
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addLayout(help_layout)
        self.main_layout.addSpacing(5)
        self.main_layout.addLayout(dept_layout)
        self.main_layout.addSpacing(20)
        self.main_layout.addWidget(self.upload_header)
        self.main_layout.addWidget(self.drop_area)
        self.main_layout.addWidget(self.reupload_btn)
        self.main_layout.addSpacing(20)
        self.main_layout.addWidget(self.modify_header)
        self.main_layout.addLayout(modify_layout)
        self.main_layout.addSpacing(30)
        self.main_layout.addLayout(run_layout)
        self.main_layout.addLayout(self.progress_layout)
        self.main_layout.addStretch()
        self.main_layout.addWidget(self.logo_label)

        self.setLayout(self.main_layout)

    # ===== 기능 구현 =====
    def add_image_files(self, files):
        self.image_files.extend(files)
        self.update_drop_area_text()

    def update_drop_area_text(self):
        if self.image_files:
            self.drop_area.setText(f"{len(self.image_files)}개 파일 추가됨")
            self.reupload_btn.show()
        else:
            self.drop_area.setText("Drag & drop\n파일 직접선택")
            self.reupload_btn.hide()

    def select_receipts(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "영수증 이미지 선택", "", "Image Files (*.jpg *.jpeg *.png *.bmp *.gif *.tiff)"
        )
        if files:
            self.add_image_files(files)

    def reset_to_initial(self):
        self.image_files.clear()
        self.update_drop_area_text()

    def choose_save_folder(self):
        if not self.image_files:
            QMessageBox.warning(self, "알림", "먼저 영수증 이미지를 추가하세요.")
            return

        # ✅ API Key 입력
        api_key, ok = QInputDialog.getText(self, "API Key 입력", "OpenAI API Key를 입력하세요:")
        if not ok or not api_key.strip():
            QMessageBox.warning(self, "알림", "API Key가 필요합니다.")
            return

        default_path = os.path.expanduser("~\\Documents")
        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택", default_path)

        if folder:
            self.save_folder = folder
            self.show_progress_ui()
            self.run_process(api_key)

    def show_progress_ui(self):
        for widget in [self.dept_label, self.dept_combo, self.upload_header, self.drop_area,
                       self.reupload_btn, self.modify_header, self.excel_btn, self.add_btn, self.run_btn]:
            widget.hide()

        self.progress_icon.show()
        self.progress_msg.show()
        self.progress_bar.show()
        self.percent_label.show()

    def run_process(self, api_key):
        # ✅ API Key 전달
        self.thread = ProcessThread(api_key, self.image_files, self.save_folder)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.show_finish_screen)
        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.percent_label.setText(f"{value}%")

    def open_result_folder(self):
        if self.save_folder and os.path.exists(self.save_folder):
            try:
                os.startfile(self.save_folder)
            except:
                try:
                    subprocess.run(['explorer', self.save_folder], check=True)
                except:
                    print("폴더 열기에 실패했습니다.")

    def show_finish_screen(self, total, result_excel_path):
        self.progress_msg.setText(f"총 {total}개 처리완료!")
        self.progress_bar.setValue(100)
        self.percent_label.setText("100%")
        self.main_button.show()
        self.raise_()
        self.activateWindow()
        self.open_result_folder()

    def reset_ui(self):
        self.progress_icon.hide()
        self.progress_msg.hide()
        self.progress_bar.hide()
        self.percent_label.hide()
        self.main_button.hide()

        for widget in [self.dept_label, self.dept_combo, self.upload_header, self.drop_area,
                       self.modify_header, self.excel_btn, self.add_btn, self.run_btn]:
            widget.show()

        self.reset_to_initial()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReceiptApp()
    window.show()
    sys.exit(app.exec_())