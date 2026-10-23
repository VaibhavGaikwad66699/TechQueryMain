"""Serialize library writes in the supported single-API-process deployment."""
from functools import wraps
from threading import RLock

_lock = RLock()


def library_mutation(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        with _lock:
            return function(*args, **kwargs)
    return guarded
