import threading
from grpc import StatusCode

class ExclusiveServiceMixin:
    _svc_lock = threading.Lock()  # one lock for all methods

    def _enter_or_abort(self, context) -> bool:
        # non-blocking: if busy, fail fast
        if not self._svc_lock.acquire(False):
            context.abort(StatusCode.RESOURCE_EXHAUSTED, "Server busy")
        return True

    def _exit(self):
        self._svc_lock.release()