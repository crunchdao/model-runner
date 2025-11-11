from trackerbase import TrackerBase
from trackerbase import BenchmarkTracker  # keep me


class DummyTracker(TrackerBase):

    def __init__(self):
        super().__init__(horizon=10)
