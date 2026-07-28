"""Shared worker signals for progress, log, error, and finished."""

from qtpy.QtCore import QObject, Signal


class WorkerSignals(QObject):
    """Qt signals for worker → UI communication."""

    progress = Signal(float, str)
    log = Signal(str)
    error = Signal(str)
    finished = Signal(object)
