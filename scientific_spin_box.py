import re

from PySide2 import QtGui
from PySide2.QtWidgets import QDoubleSpinBox
import numpy as np

# Regular expression to find floats. Match groups are the whole string, the
# whole coefficient, the decimal part of the coefficient, and the exponent
# part.
_float_re = re.compile(r'(([+-]?\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)')


class FloatValidator(QtGui.QValidator):
    """
    Validator class for floats in scientific notation
    """
    def validate(self, string, position):
        if self.valid_float_string(string):
            return self.State.Acceptable
        if string == "" or string[position-1] in 'e.-+':
            return self.State.Intermediate
        return self.State.Invalid

    @staticmethod
    def valid_float_string(string):
        match = _float_re.search(string)
        return match.groups()[0] == string if match else False

    def fixup(self, text):
        match = _float_re.search(text)
        return match.groups()[0] if match else ""


class ScientificDoubleSpinBox(QDoubleSpinBox):
    """
    Double spin box which allows use of scientific notation
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimum(-np.inf)
        self.setMaximum(np.inf)
        self.validator = FloatValidator()
        self.setDecimals(1000)

    def validate(self, text, position):
        return self.validator.validate(text, position)

    def fixup(self, text):
        return self.validator.fixup(text)

    def valueFromText(self, text):
        return float(text)

    def textFromValue(self, value):
        """Modified form of the 'g' format specifier."""
        flt_str = "{:g}".format(value).replace("e+", "e")
        flt_str = re.sub(r"e(-?)0*(\d+)", r"e\1\2", flt_str)
        return flt_str

    def stepBy(self, steps):
        text = self.cleanText()
        groups = _float_re.search(text).groups()
        decimal = float(groups[1]) + steps
        new_string = "{:g}".format(decimal) + (groups[3] if groups[3] else "")
        self.lineEdit().setText(new_string)
