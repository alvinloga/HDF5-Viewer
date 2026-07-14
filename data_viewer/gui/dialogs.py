"""Dialog primitives for Data Viewer safe import/save/export flows."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from data_viewer.editing.review import SaveReview
from data_viewer.gui.i18n import Locale, UiStringKey, tr


class PathValidationWidget(QWidget):
    """Reusable path input with inline validation and selectable long-path display."""

    def __init__(self, *, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if mode not in {"open", "save", "export"}:
            raise ValueError("path validation mode must be open, save, or export")
        self._mode = mode
        self._is_valid = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._input = QLineEdit(self)
        self._input.setObjectName("path_input")
        self._input.setAccessibleName(f"{mode} path")
        self._input.textChanged.connect(self._validate_current_path)
        layout.addWidget(self._input)

        self._display = QLabel("", self)
        self._display.setObjectName("path_display_label")
        self._display.setAccessibleName("Selected path")
        self._display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._display)

        self._error = QLabel("", self)
        self._error.setObjectName("path_error_label")
        self._error.setAccessibleName("Path validation error")
        self._error.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._error)

    def set_path(self, path: str | Path) -> None:
        """Set and validate the path text."""

        self._input.setText(str(path))
        self._validate_current_path()

    def path(self) -> Path:
        """Return the current path value."""

        return Path(self._input.text())

    def is_valid(self) -> bool:
        """Return whether the path satisfies the current mode."""

        return self._is_valid

    def _validate_current_path(self) -> None:
        text = self._input.text().strip()
        path = Path(text) if text else None
        error = ""
        if path is None:
            error = "Path is required."
        elif self._mode == "open" and not path.is_file():
            error = "File does not exist."
        elif self._mode in {"save", "export"} and not path.parent.exists():
            error = "Parent directory does not exist."
        elif self._mode in {"save", "export"} and path.exists() and path.is_dir():
            error = "Target path is a directory."

        self._is_valid = error == ""
        self._error.setText(error)
        self._error.setVisible(bool(error))
        self._display.setText(_middle_elide(text, keep=72))
        self._display.setToolTip(text)


class SaveSummaryDialog(QDialog):
    """Modal save authorization summary."""

    def __init__(
        self,
        review: SaveReview,
        parent: QWidget | None = None,
        *,
        locale: Locale = Locale.EN_US,
    ) -> None:
        if review.patch_count <= 0:
            raise ValueError("save summary requires at least one reviewed patch")
        super().__init__(parent)
        self._locale = Locale(locale)
        self.setObjectName("save_summary_dialog")
        self.setWindowTitle(tr(UiStringKey.DIALOG_SAVE_SUMMARY_TITLE, self._locale))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._target_label = _selectable_label(f"target: {review.target_uri}", "save_target_label", self)
        self._strategy_label = _selectable_label(
            f"strategy: {review.strategy.value}",
            "save_strategy_label",
            self,
        )
        resource_text = ", ".join(resource.node_path for resource in review.resources)
        self._resources_label = _selectable_label(
            f"resources: {resource_text}",
            "save_resources_label",
            self,
        )
        kind_text = ", ".join(f"{kind}: {count}" for kind, count in review.changed_patch_kinds)
        self._patch_kinds_label = _selectable_label(
            f"patches: {review.patch_count}; {kind_text}",
            "save_patch_kinds_label",
            self,
        )
        self._warnings_label = _selectable_label(
            "warnings: " + ("; ".join(review.warnings) if review.warnings else "none"),
            "save_warnings_label",
            self,
        )
        for label in (
            self._target_label,
            self._strategy_label,
            self._resources_label,
            self._patch_kinds_label,
            self._warnings_label,
        ):
            layout.addWidget(label)

        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel_button = QPushButton(tr(UiStringKey.COMMAND_CANCEL, self._locale), self)
        self._cancel_button.setObjectName("cancel_button")
        self._cancel_button.setDefault(True)
        self._cancel_button.clicked.connect(self.reject)
        self._save_button = QPushButton(tr(UiStringKey.DIALOG_SAVE_CONFIRM, self._locale), self)
        self._save_button.setObjectName("confirm_save_button")
        self._save_button.setDefault(False)
        self._save_button.clicked.connect(self.accept)
        row.addWidget(self._cancel_button)
        row.addWidget(self._save_button)
        layout.addLayout(row)

    def default_action(self) -> str:
        """Return the action activated by default."""

        return "cancel" if self._cancel_button.isDefault() else "save"


class DestructiveConfirmationDialog(QDialog):
    """Explicit destructive confirmation with Cancel as the safe default."""

    def __init__(
        self,
        *,
        resource_label: str,
        consequence: str,
        parent: QWidget | None = None,
        locale: Locale = Locale.EN_US,
    ) -> None:
        if not resource_label or not consequence:
            raise ValueError("destructive confirmation needs resource and consequence")
        super().__init__(parent)
        self._locale = Locale(locale)
        self.setObjectName("destructive_confirmation_dialog")
        self.setWindowTitle(tr(UiStringKey.DIALOG_DESTRUCTIVE_TITLE, self._locale))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        layout = QVBoxLayout(self)
        summary = _selectable_label(
            f"Confirm operation for {resource_label}.",
            "destructive_summary_label",
            self,
        )
        consequence_label = _selectable_label(
            consequence,
            "destructive_consequence_label",
            self,
        )
        layout.addWidget(summary)
        layout.addWidget(consequence_label)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(tr(UiStringKey.COMMAND_CANCEL, self._locale), self)
        cancel.setObjectName("cancel_button")
        cancel.setDefault(True)
        cancel.clicked.connect(self.reject)
        confirm = QPushButton(tr(UiStringKey.DIALOG_DESTRUCTIVE_CONFIRM, self._locale), self)
        confirm.setObjectName("confirm_button")
        confirm.setDefault(False)
        confirm.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(confirm)
        layout.addLayout(row)


class ImportOptionsDialog(QDialog):
    """Preview-first nonmodal import options dialog."""

    def __init__(
        self,
        source_path: Path,
        parent: QWidget | None = None,
        *,
        locale: Locale = Locale.EN_US,
    ) -> None:
        super().__init__(parent)
        self._locale = Locale(locale)
        self.setObjectName("import_options_dialog")
        self.setWindowTitle(tr(UiStringKey.DIALOG_IMPORT_OPTIONS_TITLE, self._locale))
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._source_path = source_path

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        self._source_label = _selectable_label(
            f"source: {source_path}",
            "import_source_label",
            self,
        )
        self._preview_label = _selectable_label(
            f"Preview: {_preview_text(source_path)}",
            "import_preview_label",
            self,
        )
        self._options_label = _selectable_label(
            "options: detected defaults; no source file changes will be made.",
            "import_options_label",
            self,
        )
        layout.addWidget(self._source_label)
        layout.addWidget(self._preview_label)
        layout.addWidget(self._options_label)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(tr(UiStringKey.COMMAND_CANCEL, self._locale), self)
        cancel.setObjectName("cancel_button")
        cancel.setDefault(True)
        cancel.clicked.connect(self.reject)
        apply = QPushButton(tr(UiStringKey.DIALOG_IMPORT_APPLY, self._locale), self)
        apply.setObjectName("apply_import_button")
        apply.setDefault(False)
        apply.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(apply)
        layout.addLayout(row)


def _selectable_label(text: str, object_name: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(object_name)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    return label


def _middle_elide(text: str, *, keep: int) -> str:
    if len(text) <= keep:
        return text
    head = max(8, keep // 3)
    tail = max(24, keep - head - 1)
    return f"{text[:head]}…{text[-tail:]}"


def _preview_text(source_path: Path, *, limit: int = 512) -> str:
    try:
        text = source_path.read_text(encoding="utf-8")[:limit]
    except Exception:
        return "preview unavailable until format options are confirmed"
    return text.replace("\r\n", "\n")


__all__ = [
    "DestructiveConfirmationDialog",
    "ImportOptionsDialog",
    "PathValidationWidget",
    "SaveSummaryDialog",
]
