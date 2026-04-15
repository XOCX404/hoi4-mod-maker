"""
模式操作提示条 — 每个编辑模式首次切换时显示一行操作说明。
"""
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QSettings

from ui.i18n import tr

_ACCENT = "#6c6cf0"
_HINT_BG = "rgba(108, 108, 240, 0.10)"
_BORDER = "#3a3a4a"
_TEXT = "#e0e0f0"
_DIM = "#8888a8"

_SETTINGS_GROUP = "ModeHints"


class ModeHintBar(QWidget):
    """可关闭的单行模式提示条。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(f"""
            ModeHintBar {{
                background: {_HINT_BG};
                border-bottom: 1px solid {_BORDER};
            }}
        """)
        self._settings = QSettings("HOI4MapMaker", _SETTINGS_GROUP)
        self._current_mode = ""

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(8)

        self._icon = QLabel("💡")
        self._icon.setFixedWidth(20)
        self._icon.setStyleSheet("font-size: 14px; background: transparent;")
        lay.addWidget(self._icon)

        self._text = QLabel()
        self._text.setStyleSheet(f"color: {_TEXT}; font-size: 12px; background: transparent;")
        self._text.setWordWrap(False)
        lay.addWidget(self._text, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {_DIM};
                font-size: 14px;
            }}
            QPushButton:hover {{
                color: {_TEXT};
            }}
        """)
        close_btn.clicked.connect(self._dismiss)
        lay.addWidget(close_btn)

        self.hide()

    def on_mode_changed(self, mode: str) -> None:
        """模式切换时调用，首次显示提示。"""
        self._current_mode = mode
        hint_key = f"hint_mode_{mode}"
        hint_text = tr(hint_key)

        # key 没翻译 = 没有提示
        if hint_text == hint_key:
            self.hide()
            return

        # 检查是否已经看过
        if self._settings.value(f"seen_{mode}", False, type=bool):
            self.hide()
            return

        self._text.setText(hint_text)
        self.show()

    def _dismiss(self) -> None:
        """关闭并记录已看过。"""
        if self._current_mode:
            self._settings.setValue(f"seen_{self._current_mode}", True)
        self.hide()

    @staticmethod
    def reset_all_hints() -> None:
        """重置所有模式提示（帮助菜单调用）。"""
        settings = QSettings("HOI4MapMaker", _SETTINGS_GROUP)
        settings.clear()
