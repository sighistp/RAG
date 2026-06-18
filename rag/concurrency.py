"""并发层 — 读写锁、连接池包装。"""

import threading
from contextlib import contextmanager


class ReadWriteLock:
    """读写锁：多个读可并发，写独占。"""

    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0
        self._writing = False

    @contextmanager
    def read(self):
        with self._read_ready:
            while self._writing:
                self._read_ready.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._read_ready:
                self._readers -= 1
                if self._readers == 0:
                    self._read_ready.notify_all()

    @contextmanager
    def write(self):
        self._read_ready.acquire()
        try:
            while self._readers > 0 or self._writing:
                self._read_ready.wait()
            self._writing = True
        finally:
            self._read_ready.release()
        try:
            yield
        finally:
            self._read_ready.acquire()
            try:
                self._writing = False
                self._read_ready.notify_all()
            finally:
                self._read_ready.release()
