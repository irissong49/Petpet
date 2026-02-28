import sys
import os
import random
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QPushButton, QTextEdit, QMenu, QAction
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TODO_FILE = os.path.join(BASE_DIR, "todo.md")

from voice_listener import VoiceListener


class TodoWindow(QWidget):
    """独立的 Todo 浮窗"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(240, 228)

        # 顶部拖动条
        self.title_bar = QLabel("to do list", self)
        self.title_bar.setGeometry(0, 0, 240, 28)
        self.title_bar.setAlignment(Qt.AlignCenter)
        self.title_bar.setStyleSheet("""
            background-color: rgba(180, 210, 255, 230);
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            font-size: 12px;
            color: #333;
        """)

        # 文本编辑区
        self.edit = QTextEdit(self)
        self.edit.setGeometry(0, 28, 240, 200)
        self.edit.setStyleSheet("""
            background-color: rgba(255, 255, 255, 220);
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
            padding: 6px;
            font-size: 20px;
        """)
        self.edit.textChanged.connect(self.save_todo)
        self.load_todo()

        self.drag_pos = None

        # 鼠标离开 5 秒后自动隐藏
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

        # 拖动事件绑定到 title_bar
        self.title_bar.mousePressEvent = self._bar_press
        self.title_bar.mouseMoveEvent = self._bar_move
        self.title_bar.mouseReleaseEvent = self._bar_release

    def load_todo(self):
        if os.path.exists(TODO_FILE):
            with open(TODO_FILE, "r", encoding="utf-8") as f:
                self.edit.setText(f.read())

    def save_todo(self):
        with open(TODO_FILE, "w", encoding="utf-8") as f:
            f.write(self.edit.toPlainText())

    def enterEvent(self, event):
        self.hide_timer.stop()

    def leaveEvent(self, event):
        self.hide_timer.start(5000)

    def _bar_press(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def _bar_move(self, event):
        if self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)

    def _bar_release(self, event):
        self.drag_pos = None


class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        self._x_acc = 0.0
        self._y_acc = 0.0
        self.idle_pix = QPixmap(os.path.join(BASE_DIR, "status_idle.png"))
        self.click_pix = QPixmap(os.path.join(BASE_DIR, "status_onclick.png"))

        self.idle_pix = self.idle_pix.scaledToHeight(300, Qt.SmoothTransformation)
        self.click_pix = self.click_pix.scaledToHeight(300, Qt.SmoothTransformation)

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(self.idle_pix.size())

        self.label = QLabel(self)
        self.label.setPixmap(self.idle_pix)
        self.label.resize(self.idle_pix.size())

        self.drag_pos = None
        self.state_click = False

        self.move(random.randint(200, 800), random.randint(200, 500))

        # 自动漫步
        self.walk_timer = QTimer()
        self.walk_timer.timeout.connect(self.random_walk)
        self.walk_timer.start(50)

        # 点击状态恢复
        self.state_timer = QTimer()
        self.state_timer.timeout.connect(self.restore_idle)

        # Todo 按钮
        self.todo_button = QPushButton("Todo", self)
        self.todo_button.move(10, 10)
        self.todo_button.hide()
        self.todo_button.clicked.connect(self.toggle_todo)

        # 按钮延迟隐藏（5 秒）
        self.hide_button_timer = QTimer()
        self.hide_button_timer.setSingleShot(True)
        self.hide_button_timer.timeout.connect(self.todo_button.hide)

        # 独立 Todo 浮窗
        self.todo_window = TodoWindow()
        # __init__ 末尾加：
        self.voice = VoiceListener()
        self.voice.start()


    def random_walk(self):
        if not self.drag_pos:
            self._x_acc += random.choice([-0.01, 0, 0.01])
            self._y_acc += random.choice([-0.02, 0, 0.02])
            dx = int(self._x_acc)
            dy = int(self._y_acc)
            if dx or dy:
                self.move(self.x() + dx, self.y() + dy)
                self._x_acc -= dx
                self._y_acc -= dy

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.label.setPixmap(self.click_pix)
            self.state_click = True
            self.state_timer.start(1500)
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        # 预留功能（暂时禁用）
        action_settings = QAction("设置", self)
        action_settings.setEnabled(False)
        action_about = QAction("关于", self)
        action_about.setEnabled(False)
        
        # 退出
        action_quit = QAction("退出", self)
        action_quit.triggered.connect(QApplication.quit)
        
        menu.addAction(action_settings)
        menu.addAction(action_about)
        menu.addSeparator()
        menu.addAction(action_quit)
        
        menu.exec_(event.globalPos())
    def restore_idle(self):
        if self.state_click:
            self.label.setPixmap(self.idle_pix)
            self.state_click = False
            self.state_timer.stop()

    def enterEvent(self, event):
        self.hide_button_timer.stop()
        self.todo_button.show()

    def leaveEvent(self, event):
        self.hide_button_timer.start(5000)

    def toggle_todo(self):
        if self.todo_window.isVisible():
            self.todo_window.hide()
            self.todo_window.hide_timer.stop()
        else:
            pet_geo = self.frameGeometry()
            self.todo_window.move(pet_geo.right() + 10, pet_geo.top())
            self.todo_window.show()
            self.todo_window.edit.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = DesktopPet()
    pet.show()
    sys.exit(app.exec_())