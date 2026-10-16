"""Shared worker signals for progress, log, error, and finished."""

try:
    from qtpy.QtCore import QObject, Signal
except ModuleNotFoundError:
    from src.ui.qt import QObject, Signal


class WorkerSignals(QObject):
    """Qt signals for worker → UI communication."""

    progress = Signal(float, str)
    log = Signal(str)
    error = Signal(str)
    finished = Signal(object)
