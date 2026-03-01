"""
UI Kit primitives for EquityJournal redesign.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QPushButton, QFrame, QHBoxLayout, QVBoxLayout, QProgressBar


class FilterPillButton(QPushButton):
    """Compact pill-style filter button."""

    def __init__(self, label: str, parent=None):
        """Init.

        Args:
            label: Button text.
            parent: Optional parent widget.
        """
        super().__init__(label, parent)
        self.setObjectName("filterPill")
        self.setCheckable(True)


class SectionPanel(QFrame):
    """Reusable rounded section panel."""

    def __init__(self, title: str = "", parent=None):
        """Init.

        Args:
            title: Optional section title.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        root = QVBoxLayout()
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        self.setLayout(root)
        self._title_label = None
        if title:
            self._title_label = QLabel(title)
            self._title_label.setObjectName("sectionTitle")
            root.addWidget(self._title_label)

    @property
    def body_layout(self) -> QVBoxLayout:
        """Body layout accessor."""
        return self.layout()


class TickerChip(QLabel):
    """Ticker initials badge."""

    def __init__(self, text: str, parent=None):
        """Init."""
        super().__init__(text, parent)
        self.setObjectName("tickerChip")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(34, 34)


class StatCard(QFrame):
    """Minimal stat card primitive for KPI blocks."""

    def __init__(self, title: str, value: str = "₹0.00", sub: str = "0.00%", parent=None):
        """Init."""
        super().__init__(parent)
        self.setObjectName("statCard")
        root = QVBoxLayout()
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)
        self.setLayout(root)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("statCardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("statCardValue")
        self.sub_label = QLabel(sub)
        self.sub_label.setObjectName("statCardSub")
        root.addWidget(self.title_label)
        root.addWidget(self.value_label)
        root.addWidget(self.sub_label)


class SortHeaderButton(QPushButton):
    """Header button for sortable table columns."""

    def __init__(self, label: str, parent=None):
        """Init."""
        super().__init__(label, parent)
        self.setObjectName("sortHeaderBtn")


class WeightBar(QFrame):
    """Simple weighted progress bar."""

    def __init__(self, value_pct: float = 0.0, parent=None):
        """Init."""
        super().__init__(parent)
        self.setObjectName("weightBarWrap")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self._bar = QProgressBar()
        self._bar.setObjectName("weightBar")
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        layout.addWidget(self._bar)
        self.set_value(value_pct)

    def set_value(self, value_pct: float):
        """Set progress value in %."""
        value = max(0.0, min(100.0, float(value_pct or 0.0)))
        self._bar.setValue(int(round(value)))

