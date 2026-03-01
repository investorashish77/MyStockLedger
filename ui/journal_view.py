"""Journal view for transaction notes and analyst consensus."""

from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)
from PyQt5.QtCore import Qt

from database.db_manager import DatabaseManager
from services.ai_summary_service import AISummaryService


class JournalView(QWidget):
    """Journal notes with edit and analyst-view actions."""

    def __init__(self, db: DatabaseManager, ai_service: AISummaryService = None):
        super().__init__()
        self.db = db
        self.ai_service = ai_service
        self.current_user_id = None
        self.current_notes = []
        self.setup_ui()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("Journal")
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        self.notes_table = QTableWidget()
        self.notes_table.setColumnCount(4)
        self.notes_table.setHorizontalHeaderLabels(["Symbol", "Date", "Note", "Analyst View"])
        header = self.notes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.notes_table.verticalHeader().setDefaultSectionSize(46)
        self.notes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notes_table.doubleClicked.connect(self._edit_selected_note)
        root.addWidget(self.notes_table)

        hint = QLabel("Double-click a row to edit note.")
        hint.setObjectName("journalHint")
        root.addWidget(hint)

    def load_for_user(self, user_id: int):
        self.current_user_id = user_id
        self.notes_table.setRowCount(0)
        self.current_notes = self.db.get_user_journal_notes(user_id)

        for i, row in enumerate(self.current_notes):
            self.notes_table.insertRow(i)
            symbol_item = QTableWidgetItem(row.get("symbol") or "-")
            symbol_item.setData(Qt.UserRole, row.get("transaction_id"))
            self.notes_table.setItem(i, 0, symbol_item)
            self.notes_table.setItem(i, 1, QTableWidgetItem(row.get("transaction_date") or "-"))

            note_text = row.get("thesis") or ""
            brief = note_text if len(note_text) <= 180 else f"{note_text[:177]}..."
            note_item = QTableWidgetItem(brief)
            note_item.setToolTip(note_text or "No note")
            self.notes_table.setItem(i, 2, note_item)

            analyst_btn = QPushButton("Analyst View")
            analyst_btn.setObjectName("actionBlendBtn")
            analyst_btn.clicked.connect(lambda _=False, idx=i: self._open_analyst_view(idx))
            self.notes_table.setCellWidget(i, 3, analyst_btn)

    def _ensure_analyst_view_for_stock(self, note_row: dict) -> bool:
        stock_id = note_row.get("stock_id")
        if not stock_id:
            return False
        existing = self.db.get_analyst_consensus(stock_id)
        if existing and (existing.get("report_text") or "").strip():
            return True
        if not self.ai_service or not self.ai_service.is_available():
            return False

        as_of_date = datetime.now().strftime("%Y-%m-%d")
        current_price = self.db.get_latest_price(stock_id)
        result = self.ai_service.generate_analyst_consensus(
            company_name=note_row.get("company_name") or note_row.get("symbol") or "",
            stock_symbol=note_row.get("symbol") or "",
            current_price=current_price,
            as_of_date=as_of_date,
        )
        if result and (result.get("summary_text") or "").strip():
            self.db.upsert_analyst_consensus(
                stock_id=stock_id,
                report_text=result.get("summary_text"),
                status="GENERATED",
                provider=result.get("provider") or self.ai_service.provider,
                as_of_date=as_of_date,
            )
            return True

        self.db.upsert_analyst_consensus(
            stock_id=stock_id,
            report_text=None,
            status="FAILED",
            provider=self.ai_service.provider if self.ai_service else None,
            as_of_date=as_of_date,
        )
        return False

    def _open_analyst_view(self, row_idx: int):
        if row_idx < 0 or row_idx >= len(self.current_notes):
            return
        note_row = self.current_notes[row_idx]
        stock_id = note_row.get("stock_id")
        if not stock_id:
            QMessageBox.information(self, "Analyst View", "Stock reference not available.")
            return
        if not self._ensure_analyst_view_for_stock(note_row):
            QMessageBox.information(
                self,
                "Analyst View",
                "Unable to generate analyst consensus now. Try again later.",
            )
            return

        report = self.db.get_analyst_consensus(stock_id)
        if not report or not (report.get("report_text") or "").strip():
            QMessageBox.information(self, "Analyst View", "Analyst consensus not available yet.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Analyst View - {note_row.get('symbol')}")
        dialog.resize(820, 560)
        self._apply_active_theme(dialog)

        root = QVBoxLayout(dialog)
        meta = QLabel(
            f"{note_row.get('company_name') or note_row.get('symbol')} | "
            f"As of: {report.get('as_of_date') or '-'} | "
            f"Provider: {report.get('provider') or '-'}"
        )
        root.addWidget(meta)

        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(report.get("report_text") or "")
        root.addWidget(viewer)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        root.addWidget(buttons)
        dialog.exec_()

    def _edit_selected_note(self, index):
        row = index.row()
        if row < 0 or row >= len(self.current_notes):
            return
        note_row = self.current_notes[row]
        tx_id = note_row.get("transaction_id")
        if not tx_id:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Journal Note - {note_row.get('symbol')}")
        dialog.resize(680, 420)
        self._apply_active_theme(dialog)

        root = QVBoxLayout(dialog)
        editor = QTextEdit()
        editor.setPlainText(note_row.get("thesis") or "")
        root.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        root.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return

        self.db.update_transaction(tx_id, thesis=editor.toPlainText().strip())
        if self.current_user_id:
            self.load_for_user(self.current_user_id)

    def _apply_active_theme(self, widget: QWidget):
        win = self.window() if hasattr(self, "window") else None
        if win and hasattr(win, "styleSheet"):
            widget.setStyleSheet(win.styleSheet())
