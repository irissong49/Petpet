import sys
import os
import random
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QPushButton, QTextEdit, QMenu, QAction
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QFont, QPainter, QColor, QPainterPath, QFontMetrics

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
TODO_FILE = os.path.join(BASE_DIR, "todo.md")

from voice_listener import VoiceListener


# ── 对话气泡（方框样式）────────────────────────────────────

class SpeechBubble(QWidget):
    MAX_WIDTH = 260
    PADDING   = 12
    CORNER_R  = 10
    FONT_SIZE = 9

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._text = ""

        self.setWindowOpacity(0.0)
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

        self._auto_hide = QTimer(self)
        self._auto_hide.setSingleShot(True)
        self._auto_hide.timeout.connect(self._fade_out)

    def show_text(self, text: str, pet_widget: QWidget):
        self._text = text

        font = QFont("Microsoft YaHei", self.FONT_SIZE)
        fm   = QFontMetrics(font)

        max_text_w = self.MAX_WIDTH - self.PADDING * 2
        rect = fm.boundingRect(
            0, 0, max_text_w, 0,
            Qt.TextWordWrap | Qt.AlignLeft,
            text
        )
        bubble_w = rect.width()  + self.PADDING * 2
        bubble_h = rect.height() + self.PADDING * 2
        self.resize(bubble_w, bubble_h)

        pet_geo = pet_widget.frameGeometry()
        x = pet_geo.left() + (pet_geo.width() - bubble_w) // 2
        y = pet_geo.bottom() + 6
        self.move(x, y)

        # 重置动画，避免重复连接
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except TypeError:
            pass
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self.show()
        self._anim.start()

        self._auto_hide.start(10_000)

    def _fade_out(self):
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except TypeError:
            pass
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._on_fade_done)
        self._anim.start()

    def _on_fade_done(self):
        try:
            self._anim.finished.disconnect()
        except TypeError:
            pass
        self.hide()

    def mousePressEvent(self, event):
        self._auto_hide.stop()
        self._fade_out()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        bw = float(self.width())
        bh = float(self.height())
        r  = float(self.CORNER_R)
        p  = self.PADDING

        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, bw, bh, r, r)

        painter.fillPath(path, QColor(255, 255, 255, 230))
        painter.setPen(QColor(180, 210, 255, 220))
        painter.drawPath(path)

        painter.setPen(QColor(50, 50, 60))
        painter.setFont(QFont("Microsoft YaHei", self.FONT_SIZE))
        painter.drawText(
            p, p,
            int(bw) - p * 2, int(bh) - p * 2,
            Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter,
            self._text
        )


# ── Todo 浮窗 ──────────────────────────────────────────────

class TodoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(240, 228)

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

        self.drag_pos  = None
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

        self.title_bar.mousePressEvent   = self._bar_press
        self.title_bar.mouseMoveEvent    = self._bar_move
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


# ── 桌宠主窗口 ─────────────────────────────────────────────

class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        self._x_acc = 0.0
        self._y_acc = 0.0

        self.idle_pix  = QPixmap(os.path.join(BASE_DIR, "status_idle.png"))
        self.click_pix = QPixmap(os.path.join(BASE_DIR, "status_onclick.png"))
        self.idle_pix  = self.idle_pix.scaledToHeight(300, Qt.SmoothTransformation)
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

        self.drag_pos    = None
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

        self.hide_button_timer = QTimer()
        self.hide_button_timer.setSingleShot(True)
        self.hide_button_timer.timeout.connect(self.todo_button.hide)

        self.todo_window = TodoWindow()

        # 对话气泡
        self.bubble = SpeechBubble()

        # 语音监听
        self.voice = VoiceListener()
        self.voice.reply_text.connect(self.show_bubble)
        self.voice.start()

    def show_bubble(self, text: str):
        self.bubble.show_text(text, self)

    def _update_bubble_pos(self):
        """桌宠移动时气泡跟随"""
        if self.bubble.isVisible():
            self.bubble.show_text(self.bubble._text, self)

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
                self._update_bubble_pos()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.label.setPixmap(self.click_pix)
            self.state_click = True
            self.state_timer.start(1500)
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)
            self._update_bubble_pos()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        action_settings = QAction("设置", self)
        action_settings.setEnabled(False)
        action_about = QAction("关于", self)
        action_about.setEnabled(False)
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