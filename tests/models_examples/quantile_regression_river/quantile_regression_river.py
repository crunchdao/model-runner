import os
import pandas as pd
import numpy as np
import math
from pathlib import Path
import matplotlib.pyplot as plt


TEST_DATA_START_TIME = 90000


current_dir = Path.cwd()
PATH_DATA = current_dir.parent.parent.parent / 'data' / 'bird_feed_data.csv'


def local_test_data_generator(path_data=PATH_DATA, chunksize=1000, start_time=TEST_DATA_START_TIME):
    """
    Generate the local test data yielding one record (dict) at a time.

    :param path_data: path to .csv data file
    :param chunksize: Number of rows to read at a time (default is 1000).
    """
    prev_time = start_time
    for chunk in pd.read_csv(path_data, chunksize=chunksize):
        for k, row in chunk.iterrows():
            if k > 500:
                row['time'] = row['time'] / math.pi  # don't ask
                if row['time'] > prev_time:
                    prev_time = row['time']
                    yield row.to_dict()


def remote_test_data_generator(chunksize=1000, start_time=TEST_DATA_START_TIME):
    """
    Generate the remote test data yielding one record (dict) at a time.

    :param chunksize: Number of rows to read at a time (default is 1000).
    """
    url = 'https://raw.githubusercontent.com/microprediction/birdgame/refs/heads/main/data/bird_feed_data.csv'
    prev_time = start_time
    for chunk in pd.read_csv(url, chunksize=chunksize):
        for k, row in chunk.iterrows():
            if k > 500:
                row['time'] = row['time'] / math.pi  # don't ask
                if row['time'] > prev_time:
                    prev_time = row['time']
                    yield row.to_dict()


import numpy as np
import matplotlib.pyplot as plt
from river import linear_model, preprocessing, optim


def visualize_quantile_regression(lr=0.05):
    """ Function to visualize quantile regression with different quantiles. """

    # Generate synthetic data
    np.random.seed(42)
    X = np.linspace(0, 10, 200)
    y = np.sin(X) + np.random.normal(0, 0.3, size=X.shape)  # True function + noise

    # Initialize models for different quantiles
    models = {}
    quantiles = [0.05, 0.5, 0.95]

    for alpha in quantiles:
        scale = preprocessing.StandardScaler()
        learn = linear_model.LinearRegression(
            intercept_lr=0,
            optimizer=optim.SGD(lr),
            loss=optim.losses.Quantile(alpha=alpha)
        )
        models[f"q {alpha:.2f}"] = preprocessing.TargetStandardScaler(regressor=scale | learn)

    # Make predictions and Train Quantile Regression models
    predictions = {q: [] for q in models.keys()}
    for x_val, y_val in zip(X, y):
        x_dict = {"feature": x_val}
        for q in models.keys():
            pred = models[q].predict_one(x_dict)
            predictions[q].append(pred)
            models[q].learn_one(x_dict, y_val)

    plt.figure(figsize=(10, 5))
    plt.scatter(X, y, label="Observations", alpha=0.5, color="gray")
    plt.plot(X, predictions["q 0.50"], label="Median (q=0.50)", color="blue")
    plt.plot(X, predictions["q 0.05"], label="Lower Bound (q=0.05)", color="red", linestyle="--")
    plt.plot(X, predictions["q 0.95"], label="Upper Bound (q=0.95)", color="green", linestyle="--")
    plt.fill_between(X, predictions["q 0.05"], predictions["q 0.95"], alpha=0.1, label="Predicted 90% interval")

    plt.xlabel("X")
    plt.ylabel("y")
    plt.legend()
    plt.title(f"Quantile Regression - stream learning (lr={lr})")
    plt.show()


# Run quantile regression for different learning rates

# for lr in [0.05, 0.01]:
#    visualize_quantile_regression(lr=lr)


from birdgame.trackers.trackerbase import TrackerBase
import math
import numpy as np
from river import linear_model, optim
from river import preprocessing


class QuantileRegressionRiverTracker(TrackerBase):
    """
    A model that tracks the dove location using Quantile regression on stream learning.

    Parameters
    ----------
    horizon : int
        The "look-ahead" in time after which the recorded data becomes valid for updating.
    """

    def __init__(self, horizon=10):
        super().__init__(horizon)
        self.current_x = None
        self.miss_count = 0

        # Initialize river models dictionary
        self.models = {}
        self.lr = 0.005
        for i, alpha in enumerate([0.05, 0.5, 0.95]):
            scale = preprocessing.StandardScaler()

            # you can optimize learning rate or use other optimizer (RMSProp, ...)
            learn = linear_model.LinearRegression(
                intercept_lr=0,
                optimizer=optim.SGD(self.lr),
                loss=optim.losses.Quantile(alpha=alpha)
            )

            model = scale | learn

            self.models[f"q {alpha:.2f}"] = preprocessing.TargetStandardScaler(regressor=model)

    def tick(self, payload):
        """
        Ingest a new record (payload), store it internally and update the
        estimated Gaussian mixture model.

        The core distribution captures regular variance, while the tail distribution
        captures extreme deviations.

        Parameters
        ----------
        payload : dict
            Must contain 'time' (int/float) and 'dove_location' (float).
        """

        x = payload['dove_location']
        t = payload['time']
        self.add_to_quarantine(t, x)
        self.current_x = x
        prev_x = self.pop_from_quarantine(t)

        if prev_x is not None:

            ### (optional idea)
            # Get the predicted quantile values from the models
            if "q 0.05" in self.models:
                y_lower = self.models["q 0.05"].predict_one({"x": prev_x})
                y_upper = self.models["q 0.95"].predict_one({"x": prev_x})

                # Check if observed value `x` is between the predicted quantiles
                if y_lower <= x <= y_upper:
                    prediction_error = 0  # prediction is within bounds
                    # idea: learn two time when prediction is within bounds
                    for i, alpha in enumerate([0.05, 0.5, 0.95]):
                        self.models[f"q {alpha:.2f}"].learn_one({"x": prev_x}, x)
                else:
                    prediction_error = 1  # prediction is outside bounds
            ###

            # River learn_one (online learning)
            for i, alpha in enumerate([0.05, 0.5, 0.95]):
                self.models[f"q {alpha:.2f}"].learn_one({"x": prev_x}, x)

            self.count += 1

    def predict(self):
        """
        Return a dictionary representing the best guess of the distribution
        modeled as a Gaussian distribution.
        """
        x_mean = self.current_x
        components = []

        if "q 0.05" in self.models:
            # Quantile regression prediction 5%, 50% and 95%
            y_lower = self.models["q 0.05"].predict_one({"x": self.current_x})
            y_mean = self.models["q 0.50"].predict_one({"x": self.current_x})
            y_upper = self.models["q 0.95"].predict_one({"x": self.current_x})

            loc = y_mean
            scale = np.abs((y_upper - y_lower)) / 3.289707253902945  # 3.289707253902945 = (norm.ppf(0.95) - norm.ppf(0.05))
            scale = max(scale, 1e-6)
        else:
            loc = x_mean
            scale = 1.0

        components = {
            "density": {
                "type": "builtin",
                "name": "norm",
                "params": {"loc": loc, "scale": scale}
            },
            "weight": 1
        }

        prediction_density = {
            "type": "mixture",
            "components": [components]
        }
        return prediction_density


import typing


def train():
    pass


def infer(
    payload_stream: typing.Iterator[dict],
):
    # Parameters
    HORIZON = 10

    # Initialize Model
    model = QuantileRegressionRiverTracker(horizon=HORIZON)

    yield  # Signal initialization completion

    for payload in payload_stream:
        model.tick(payload)
        yield model.predict()


def compute_pdf_score(past_pdf, observed_dove_location):
    """ Compute weighted PDF score of a normal distribution """
    weighted_pdf_score = 0
    highest_weight = 0
    stored_predictions = []

    for component in past_pdf.get('components', []):
        density = component['density']
        loc, scale, weight = density['params']['loc'], density['params']['scale'], component['weight']

        # Compute PDF score (Gaussian)
        pdf_score = (1 / (math.sqrt(2 * math.pi * scale ** 2))) * \
                    math.exp(-((observed_dove_location - loc) ** 2) / (2 * scale ** 2))

        weighted_pdf_score += weight * pdf_score

        # Store prediction with highest weight
        if weight > highest_weight:
            stored_predictions = [(loc, scale, observed_dove_location, pdf_score)]
            highest_weight = weight

    return round(weighted_pdf_score, 3), stored_predictions


def find_past_pdf(pdf_history, current_time, horizon):
    """ Function to find the most recent valid past prediction """
    for past_time, p_pdf in reversed(pdf_history):
        if past_time < current_time - horizon:
            return p_pdf
    return None  # No valid past prediction


import time
import json
from tqdm.auto import tqdm


# Parameters
# HORIZON = 10
# MAX_TRACKER_COUNT = 10000
# SHOW_PRINT = True
# STEP_PRINT = 1000


# Initialize Tracker
# tracker = QuantileRegressionRiverTracker(horizon=HORIZON)


# History to track evaluation metrics and the PDFs
# pdf_score_history = []
# pdf_history = []
# store_pred = []


# Start Processing Data
# start_time = time.time()
# if os.path.exists(PATH_DATA):
#    data_generator = local_test_data_generator()
# else:
#    data_generator = remote_test_data_generator()
#
# for payload in tqdm(data_generator, position=0, leave=True):
#    try:
#        tracker.tick(payload)
#        pdf = tracker.predict()
#        current_time = payload['time']
#
#        # Store the latest PDF prediction
#        pdf_history.append((current_time, pdf))
#
#        # Find past PDF predicition for evaluation
#        past_pdf = find_past_pdf(pdf_history, current_time, HORIZON)
#
#        if past_pdf:
#            observed_dove_location = payload['dove_location']
#            weighted_pdf_score, predictions = compute_pdf_score(past_pdf, observed_dove_location)
#
#            # Store results
#            pdf_score_history.append(weighted_pdf_score)
#            for p in predictions:
#                row = [current_time]
#                row.extend(p)
#                store_pred.append(row)
#
#            if SHOW_PRINT and len(pdf_history) % STEP_PRINT == 0:
#                print(
#                    f"[{tracker.count}] PDF Score: {weighted_pdf_score:.4f} / true: {observed_dove_location:.4f} / "
#                    f"pred: {predictions[0][0]:.4f} / dif: {observed_dove_location - predictions[0][0]:.4f} / "
#                    f"scale: {predictions[0][1]:.4f}"
#                )
#        else:
#            if SHOW_PRINT:
#                print(f"[{tracker.count}] No valid past PDF for evaluation.")
#
#    except json.JSONDecodeError:
#        print(f"[{tracker.count}] Error: Could not parse JSON payload.")
#
#    if tracker.count > MAX_TRACKER_COUNT:
#        break
#
# end_time = time.time()
# print(f"Execution Time: {end_time - start_time:.2f} seconds")


def compute_metric_stats(df):
    """Compute and print median, mean and std of metrics"""
    stats = df.agg(["median", "mean", "std"]).round(3)

    for stat_name, values in stats.iterrows():
        print(f"{stat_name.capitalize()}: {values.to_dict()}")

    return stats


# skip_length = 500
# Create history score (skipping first 500 values -> skip warmup of model)
# scores = pd.DataFrame({"pdf_score": pdf_score_history[skip_length:]})
# stats_summary = compute_metric_stats(scores)


# pred_summary = pd.DataFrame(store_pred[skip_length:], columns=["time", "loc", "scale", "dove_location", "pdf_score"])
# pred_summary.round(4)


def plot_dove_predictions(store_pred, start_ind=1000, window_size=200, max_pdf_score=100):
    """
    Plots observed vs. predicted dove locations with uncertainty and PDF scores.

    Parameters:
        store_pred (list of tuples): Stored predictions in the format (time, loc, scale, dove_location, pdf_score).
        start_ind (int): Starting index for slicing data.
        window_size (int): Number of points to plot.
        max_pdf_score (float): Maximum value for clipping PDF scores (to prevent extreme values from dominating).
    """
    end_ind = start_ind + window_size

    # time, dove_location, predictions and metrics
    data_slice = np.array(store_pred[start_ind:end_ind], dtype=np.float64)
    times, predicted_locs, scales, dove_location, pdf_scores = data_slice.T

    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Plot locations (left y-axis)
    ax1.scatter(times, dove_location, color="grey", label="Observed Dove Location", marker="o", alpha=0.9)
    ax1.plot(times, predicted_locs, label="Predicted Mean (loc)", color="red", linestyle="-")
    ax1.fill_between(times, predicted_locs - scales, predicted_locs + scales, color="red", alpha=0.2, label="±1 Std Dev (Scale)")

    # Left y-axis labels
    ax1.set_xlabel("Time")
    ax1.set_ylabel("Dove Location")
    ax1.legend(loc="upper left")
    ax1.grid(True)

    # Create second right y-axis for metric scores
    ax2 = ax1.twinx()
    ax2.scatter(times, np.clip(pdf_scores, 0, max_pdf_score), label="PDF Scores", color="green", marker="|", alpha=0.2)

    # Right y-axis labels
    ax2.set_ylabel("PDF Score")
    ax2.legend(loc="upper right")

    plt.title("Observed vs. Predicted Dove Location with Uncertainty and PDF Scores")
    plt.show()

# start_ind=1000
# window_size=200
# plot_dove_predictions(store_pred, start_ind=start_ind, window_size=window_size)


# start_ind=8000
# window_size=100
# plot_dove_predictions(store_pred, start_ind=start_ind, window_size=window_size)

