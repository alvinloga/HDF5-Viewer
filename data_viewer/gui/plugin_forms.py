"""Standard Qt parameter forms for Plugin API v1 schemas."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from data_viewer.plugins.parameters import (
    ParameterDefinition,
    ParameterSchema,
    validate_parameters,
)


class ParameterFormWidget(QWidget):
    """Keyboard-accessible standard form for a validated parameter schema."""

    def __init__(self, schema: ParameterSchema, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._schema = schema
        self._widgets: dict[str, QWidget] = {}
        self.setObjectName("plugin_parameter_form")
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for definition in schema.properties:
            editor = self._build_editor(definition)
            editor.setObjectName(f"parameter_{definition.name}")
            editor.setAccessibleName(definition.title)
            if definition.description:
                editor.setAccessibleDescription(definition.description)
                editor.setToolTip(definition.description)
            editor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self._widgets[definition.name] = editor
            layout.addRow(definition.title, editor)

    def values(self) -> Mapping[str, object]:
        """Return current form values as an immutable mapping."""

        return MappingProxyType(
            {definition.name: self._value_for(definition) for definition in self._schema.properties}
        )

    def validate_current(self) -> Mapping[str, object]:
        """Validate current form values against the schema."""

        return validate_parameters(self._schema, self.values())

    def _build_editor(self, definition: ParameterDefinition) -> QWidget:
        if definition.enum:
            combo = QComboBox(self)
            for item in definition.enum:
                combo.addItem(str(item), item)
            combo.setCurrentText(str(definition.default))
            return combo
        if definition.type == "integer":
            spin = QSpinBox(self)
            spin.setMinimum(int(definition.minimum if definition.minimum is not None else -2_147_483_648))
            spin.setMaximum(int(definition.maximum if definition.maximum is not None else 2_147_483_647))
            default = definition.default
            if not isinstance(default, int) or isinstance(default, bool):
                raise TypeError(f"{definition.name} integer default was not validated")
            spin.setValue(default)
            return spin
        if definition.type == "number":
            double_spin = QDoubleSpinBox(self)
            double_spin.setMinimum(float(definition.minimum if definition.minimum is not None else -1.0e12))
            double_spin.setMaximum(float(definition.maximum if definition.maximum is not None else 1.0e12))
            default = definition.default
            if not isinstance(default, (int, float)) or isinstance(default, bool):
                raise TypeError(f"{definition.name} number default was not validated")
            double_spin.setValue(float(default))
            return double_spin
        if definition.type == "boolean":
            checkbox = QCheckBox(self)
            checkbox.setChecked(bool(definition.default))
            return checkbox
        line = QLineEdit(self)
        line.setText(str(definition.default))
        return line

    def _value_for(self, definition: ParameterDefinition) -> object:
        widget = self._widgets[definition.name]
        if isinstance(widget, QComboBox):
            return widget.currentData()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QLineEdit):
            return widget.text()
        raise TypeError(f"unsupported parameter widget for {definition.name}")  # pragma: no cover


__all__ = ["ParameterFormWidget"]
