"""LSTM forecasting model for commodities."""

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


def quantile_loss(y_true, y_pred, quantile=0.5):
    """Custom quantile loss for regression."""
    error = y_true - y_pred
    return keras.backend.mean(
        keras.backend.maximum(quantile * error, (quantile - 1) * error),
        axis=-1
    )


def build_lstm_model(input_shape, output_shape, learning_rate=0.001):
    """
    Build LSTM model for multi-output forecasting.

    input_shape: (lookback, n_features)
    output_shape: n_targets (point forecasts)
    """
    model = keras.Sequential([
        layers.LSTM(64, activation="relu", input_shape=input_shape, return_sequences=True),
        layers.Dropout(0.2),
        layers.LSTM(32, activation="relu"),
        layers.Dropout(0.2),
        layers.Dense(16, activation="relu"),
        layers.Dense(output_shape)  # Output: targets (point forecasts)
    ])

    # Use mean squared error for simplicity; quantile loss would be custom
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss="mse",
        metrics=["mae"]
    )

    logger.info(f"Built LSTM model: {model.summary()}")
    return model


def train_lstm(X_train, y_train, epochs=50, batch_size=32, validation_split=0.2):
    """
    Train LSTM model.

    X_train: (n_samples, lookback, n_features)
    y_train: (n_samples, n_targets)
    """
    n_targets = y_train.shape[1]
    input_shape = (X_train.shape[1], X_train.shape[2])
    output_shape = n_targets  # Point forecasts

    model = build_lstm_model(input_shape, output_shape)

    # Early stopping
    early_stop = keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True
    )

    history = model.fit(
        X_train,
        y_train,  # Will expand to quantiles internally
        epochs=epochs,
        batch_size=batch_size,
        validation_split=validation_split,
        callbacks=[early_stop],
        verbose=1
    )

    logger.info(f"Training complete. Final loss: {history.history['loss'][-1]:.4f}")
    return model, history


def forecast_future(model, X_recent, n_steps=90):
    """
    Forecast future values.

    model: Trained LSTM model
    X_recent: Recent data to start forecasting from (lookback length)
    n_steps: Number of steps to forecast

    Returns DataFrame with forecasts for each target.
    """
    forecasts = []
    current_sequence = X_recent.copy()

    for _ in range(n_steps):
        # Predict next step
        pred = model.predict(current_sequence[np.newaxis, :], verbose=0)
        forecasts.append(pred[0])

        # Shift sequence (simple approach; more sophisticated would retrain)
        current_sequence = np.vstack([current_sequence[1:], pred[0][:current_sequence.shape[1]]])

    return np.array(forecasts)


def save_model(model, name="lstm_model"):
    """Save trained model."""
    path = MODELS_DIR / f"{name}_{pd.Timestamp.now().strftime('%Y%m%d')}.h5"
    model.save(path)
    logger.info(f"Model saved to {path}")
    return path


def load_model(name="lstm_model", date=None):
    """Load trained model."""
    if date is None:
        # Load latest
        models = list(MODELS_DIR.glob(f"{name}_*.h5"))
        if not models:
            raise FileNotFoundError(f"No models found for {name}")
        path = sorted(models)[-1]
    else:
        path = MODELS_DIR / f"{name}_{date}.h5"

    model = keras.models.load_model(path)
    logger.info(f"Model loaded from {path}")
    return model


def backtest_model(model, X_test, y_test, target_cols):
    """
    Backtest model on test data.

    Returns DataFrame with predictions vs actual, and metrics.
    """
    predictions = model.predict(X_test)

    # Calculate simple metrics
    mse = np.mean((y_test - predictions) ** 2, axis=0)
    mae = np.mean(np.abs(y_test - predictions), axis=0)
    rmse = np.sqrt(mse)

    metrics_df = pd.DataFrame({
        "Target": target_cols,
        "MSE": mse,
        "RMSE": rmse,
        "MAE": mae
    })

    logger.info(f"Backtest metrics:\n{metrics_df}")

    return metrics_df, predictions
