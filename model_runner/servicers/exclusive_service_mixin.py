from contextlib import contextmanager

import threading
from grpc import StatusCode, ServicerContext

class ExclusiveServiceMixin:
    _svc_lock = threading.Lock()  # one lock for all methods

    @contextmanager
    def _exclusive(self, context: ServicerContext):
        # fail fast if another call is already running
        if not self._svc_lock.acquire(False):
            context.abort(StatusCode.RESOURCE_EXHAUSTED, "Server busy")
        try:
            yield
        finally:
            self._svc_lock.release()