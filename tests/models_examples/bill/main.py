import typing

import numpy as np
from fewvar import FEWVar
import math


class EmpiricalGaussBird:
    """
    A toy model that keeps track of an empirical estimate of a Gaussian distribution
    for the change in the target variable using a fading estimator of variance (FEWVar).

    Parameters
    ----------
    fading_factor : float
        Parameter controlling how quickly older data is de-emphasized in variance estimation.
    horizon : int
        The “look-ahead” in time after which the recorded data becomes valid for updating.
    """

    def __init__(self, fading_factor=0.0001, horizon=10):
        self.fading_factor = fading_factor
        self.horizon = horizon
        self.current_x = None
        self.ewa_dx = FEWVar(fading_factor=fading_factor)
        self.quarantine = []
        self.count = 0

    def tick(self, payload):
        """
        Ingest a new record (payload), store it internally, and update the
        estimated distribution if a previously ‘horizon-shifted’ data point
        is now valid for comparison.

        Parameters
        ----------
        payload : dict
            Must contain 'time' (int/float) and 'dove_location' (float).
        """

        x = payload['dove_location']
        t = payload['time']

        # Save an entry with the time t + horizon, so that
        # once we reach that time in subsequent ticks, we'll
        # treat x as the valid "past" data point.
        self.quarantine.append((t + self.horizon, x))
        self.current_x = x

        # Find the most recent quarantined data point
        # that has become valid for the current time t:

        valid = [(j, (ti, xi)) for (j, (ti, xi)) in enumerate(self.quarantine) if ti <= t]


        if valid:
            # The last valid entry (i.e., the one with ti > t)
            prev_ndx, (ti, prev_x) = valid[-1]
            x_change = x - prev_x

            # Update the exponentially weighted average of the changes
            self.ewa_dx.update(x_change)

            # We only want to use this piece of historical data once, so
            # truncate the quarantine list up to the valid entry.
            self.quarantine = self.quarantine[:prev_ndx]

    def predict(self):
        """
        Return a dictionary representing the current best guess of the distribution
        over the next increment, modeled as Gaussian with mean = current_x and
        std. deviation = stdev of historical changes.
        """

        x_mean = self.current_x
        try:
            x_var = self.ewa_dx.get()
            x_std = math.sqrt(x_var)
        except:
            # If we have no data yet, default to some positive value
            x_std = 1.0

        prediction_rec = {
            'model_type': 'gaussian',
            'model_params': {
                'mu': x_mean,
                'sigma': x_std
            }
        }
        return prediction_rec


def train():
    pass


def infer(
    payload_stream: typing.Iterator[dict],
):
    model = EmpiricalGaussBird(fading_factor=0.001)

    # NOTE: DO NOT REMOVE THIS YIELD
    # Signals to the system that your attacker is initialized and ready.
    yield

    for payload in payload_stream:
        model.tick(payload)
        yield model.predict()
