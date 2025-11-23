import os
import pandas as pd
import numpy as np
import json
import plotly.graph_objects as go
import plotly.utils
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import sys
import warnings
import datetime
import secrets
from utils.auth_routes import require_auth, require_admin_auth
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

# Add project root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import authentication modules
from utils.auth_routes import auth_bp


try:
    from model import Kronos, KronosTokenizer, KronosPredictor

    MODEL_AVAILABLE = True
except ImportError:
    MODEL_AVAILABLE = False
    sys.exit(
        "Error: Kronos model cannot be imported, will use simulated data for demonstration"
    )

# Available model configurations
AVAILABLE_MODELS = {
    "kronos-mini": {
        "name": "Kronos-mini",
        "model_id": "NeoQuasar/Kronos-mini",
        "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-2k",
        "context_length": 2048,
        "params": "4.1M",
        "description": "Lightweight model, suitable for fast prediction",
    },
    "kronos-small": {
        "name": "Kronos-small",
        "model_id": "NeoQuasar/Kronos-small",
        "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-base",
        "context_length": 512,
        "params": "24.7M",
        "description": "Small model, balanced performance and speed",
    },
    "kronos-base": {
        "name": "Kronos-base",
        "model_id": "NeoQuasar/Kronos-base",
        "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-base",
        "context_length": 512,
        "params": "102.3M",
        "description": "Base model, provides better prediction quality",
    },
}

load_dotenv()  # 加载 .env 文件中的变量

KRONOS_MODEL_KEY = os.environ.get("KRONOS_MODEL_KEY", "kronos-base")
KRONOS_MODEL_DEVICE = os.environ.get("KRONOS_MODEL_DEVICE", "cpu")
# DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_DIR = os.environ.get("DATA_DIR", "data")
DATA_DIR = os.path.abspath(DATA_DIR)
MAX_UPLOAD_FILES = int(os.environ.get("MAX_UPLOAD_FILES", "3"))  # Maximum upload files per user
MAX_RESULT_FILES = int(os.environ.get("MAX_RESULT_FILES", "3"))  # Maximum result files per user
print(f"KRONOS_MODEL_KEY: {KRONOS_MODEL_KEY}")
print(f"KRONOS_MODEL_DEVICE: {KRONOS_MODEL_DEVICE}")
print(f"DATA_DIR: {DATA_DIR}")
print(f"MAX_UPLOAD_FILES: {MAX_UPLOAD_FILES}")
print(f"MAX_RESULT_FILES: {MAX_RESULT_FILES}")

# Global variables to store models
tokenizer = None
model = None
predictor = None

def _load_model(model_key=KRONOS_MODEL_KEY, device=KRONOS_MODEL_DEVICE):
    """Load Kronos model"""
    global tokenizer, model, predictor

    if not MODEL_AVAILABLE:
        raise Exception("Kronos model library not available")

    if model_key not in AVAILABLE_MODELS:
        raise Exception(f"Unsupported model: {model_key}")

    model_config = AVAILABLE_MODELS[model_key]

    # Load tokenizer and model
    tokenizer = KronosTokenizer.from_pretrained(model_config["tokenizer_id"])
    model = Kronos.from_pretrained(model_config["model_id"])

    # Create predictor
    predictor = KronosPredictor(
        model, tokenizer, device=device, max_context=model_config["context_length"]
    )
    return model_config


try:
    _load_model()
except Exception as e:
    sys.exit(f"Error: Model loading failed: {str(e)}")

ALLOWED_EXTENSIONS = {"csv", "feather"}
app = Flask(__name__)
CORS(app)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["DATA_DIR"] = DATA_DIR
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # Max 100MB

# Register authentication blueprint
app.register_blueprint(auth_bp)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_user_data_dir(wallet_address):
    """Get user-specific data directory path"""
    # Create user directory based on wallet address
    user_dir = os.path.join(app.config["DATA_DIR"], wallet_address.lower())
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def _to_safe_relative_path(file_path):
    """Convert absolute file path to safe relative path based on DATA_DIR"""
    if not file_path:
        return file_path

    try:
        # Normalize path
        abs_path = os.path.abspath(file_path)
        data_dir_abs = os.path.abspath(app.config["DATA_DIR"])

        # Check if file is within DATA_DIR
        if abs_path.startswith(data_dir_abs):
            # Convert to relative path
            rel_path = os.path.relpath(abs_path, data_dir_abs)
            # Normalize path separators and ensure no path traversal
            rel_path = rel_path.replace('\\', '/').strip('/')
            # Additional security check
            if '..' in rel_path or rel_path.startswith('/'):
                raise ValueError("Invalid path")
            return rel_path
        else:
            raise ValueError("File path outside DATA_DIR")

    except Exception:
        # If conversion fails, return None for security
        return None


def _to_absolute_path(relative_path):
    """Convert safe relative path to absolute path"""
    if not relative_path:
        return None

    try:
        # Security check: ensure no path traversal
        if '..' in relative_path or relative_path.startswith('/'):
            raise ValueError("Invalid relative path")

        # Convert to absolute path
        abs_path = os.path.abspath(os.path.join(app.config["DATA_DIR"], relative_path))

        # Security check: ensure path is within DATA_DIR
        data_dir_abs = os.path.abspath(app.config["DATA_DIR"])
        if not abs_path.startswith(data_dir_abs):
            raise ValueError("Path outside DATA_DIR")

        return abs_path

    except Exception:
        return None


def _is_safe_file_path(file_path, wallet_address=None):
    """Check if file path is safe for the given user"""
    if not file_path:
        return False

    abs_path = _to_absolute_path(file_path)
    if not abs_path:
        return False

    data_dir_abs = os.path.abspath(app.config["DATA_DIR"])
    if abs_path == os.path.join(data_dir_abs, os.path.basename(abs_path)):
        return True

    # If wallet address is provided, ensure file is in user directory
    if wallet_address:
        user_dir = _get_user_data_dir(wallet_address)
        return abs_path.startswith(user_dir)

    return False


def _cleanup_old_files(user_dir, suffixes, max_files=MAX_UPLOAD_FILES):
    """Clean up oldest files if exceed maximum limit"""
    print(f"Cleaning up old files {suffixes} in {user_dir}...if exceeding {max_files}")
    if not os.path.exists(user_dir):
        return

    # Get all data files in user directory
    files = []
    for file in os.listdir(user_dir):
        if file.endswith(suffixes):
            file_path = os.path.join(user_dir, file)
            file_stat = os.stat(file_path)
            files.append({
                "name": file,
                "path": file_path,
                "mtime": file_stat.st_mtime
            })

    # Sort by modification time (oldest first)
    files.sort(key=lambda x: x["mtime"])

    # Remove oldest files if exceed limit
    if len(files) > max_files:
        files_to_remove = files[:-max_files]  # All except the newest max_files
        for file_info in files_to_remove:
            try:
                os.remove(file_info["path"])
                print(f"Removed old file: {file_info['name']}")
            except Exception as e:
                print(f"Failed to remove old file {file_info['name']}: {e}")

        return len(files_to_remove)

    return 0


def _get_data_files(data_dir):
    """Scan data directory and return available data files"""
    data_files = []

    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith((".csv", ".feather")):
                file_path = os.path.join(data_dir, file)
                file_size = os.path.getsize(file_path)

                # Convert absolute path to safe relative path
                safe_relative_path = _to_safe_relative_path(file_path)
                if safe_relative_path is None:
                    # Skip files that cannot be safely converted
                    continue

                data_files.append(
                    {
                        "name": file,
                        "path": safe_relative_path,
                        "size": (
                            f"{file_size / 1024:.1f} KB"
                            if file_size < 1024 * 1024
                            else f"{file_size / (1024*1024):.1f} MB"
                        ),
                    }
                )

    return data_files


def load_data_file(file_path):
    """Load data file"""
    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith(".feather"):
            df = pd.read_feather(file_path)
        else:
            return None, "Unsupported file format"

        # Check required columns
        required_cols = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            return None, f"Missing required columns: {required_cols}"

        # Process timestamp column
        if "timestamps" in df.columns:
            df["timestamps"] = pd.to_datetime(df["timestamps"])
        elif "timestamp" in df.columns:
            df["timestamps"] = pd.to_datetime(df["timestamp"])
        elif "date" in df.columns:
            # If column name is 'date', rename it to 'timestamps'
            df["timestamps"] = pd.to_datetime(df["date"])
        else:
            # If no timestamp column exists, create one
            df["timestamps"] = pd.date_range(
                start="2024-01-01", periods=len(df), freq="1H"
            )

        # Ensure numeric columns are numeric type
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Process volume column (optional)
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

        # Process amount column (optional, but not used for prediction)
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

        # Remove rows containing NaN values
        df = df.dropna()

        return df, None

    except Exception as e:
        return None, f"Failed to load file: {str(e)}"


def save_prediction_results(
    results_dir,
    file_path,
    prediction_type,
    prediction_results,
    actual_data,
    input_data,
    prediction_params,
):
    """Save prediction results to file"""
    try:
        # Generate filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"prediction_{timestamp}.json"
        filepath = os.path.join(results_dir, filename)

        # Convert absolute file path to relative path for storage
        relative_file_path = _to_safe_relative_path(file_path)
        if not relative_file_path:
            relative_file_path = "unknown_file"

        # Prepare data for saving
        save_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "file_path": relative_file_path,
            "prediction_type": prediction_type,
            "prediction_params": prediction_params,
            "input_data_summary": {
                "rows": len(input_data),
                "columns": list(input_data.columns),
                "price_range": {
                    "open": {
                        "min": float(input_data["open"].min()),
                        "max": float(input_data["open"].max()),
                    },
                    "high": {
                        "min": float(input_data["high"].min()),
                        "max": float(input_data["high"].max()),
                    },
                    "low": {
                        "min": float(input_data["low"].min()),
                        "max": float(input_data["low"].max()),
                    },
                    "close": {
                        "min": float(input_data["close"].min()),
                        "max": float(input_data["close"].max()),
                    },
                },
                "last_values": {
                    "open": float(input_data["open"].iloc[-1]),
                    "high": float(input_data["high"].iloc[-1]),
                    "low": float(input_data["low"].iloc[-1]),
                    "close": float(input_data["close"].iloc[-1]),
                },
            },
            "prediction_results": prediction_results,
            "actual_data": actual_data,
            "analysis": {},
        }

        # If actual data exists, perform comparison analysis
        if actual_data and len(actual_data) > 0:
            # Calculate continuity analysis
            if len(prediction_results) > 0 and len(actual_data) > 0:
                last_pred = prediction_results[0]  # First prediction point
            first_actual = actual_data[0]  # First actual point

            save_data["analysis"]["continuity"] = {
                "last_prediction": {
                    "open": last_pred["open"],
                    "high": last_pred["high"],
                    "low": last_pred["low"],
                    "close": last_pred["close"],
                },
                "first_actual": {
                    "open": first_actual["open"],
                    "high": first_actual["high"],
                    "low": first_actual["low"],
                    "close": first_actual["close"],
                },
                "gaps": {
                    "open_gap": abs(last_pred["open"] - first_actual["open"]),
                    "high_gap": abs(last_pred["high"] - first_actual["high"]),
                    "low_gap": abs(last_pred["low"] - first_actual["low"]),
                    "close_gap": abs(last_pred["close"] - first_actual["close"]),
                },
                "gap_percentages": {
                    "open_gap_pct": (
                        abs(last_pred["open"] - first_actual["open"])
                        / first_actual["open"]
                    )
                    * 100,
                    "high_gap_pct": (
                        abs(last_pred["high"] - first_actual["high"])
                        / first_actual["high"]
                    )
                    * 100,
                    "low_gap_pct": (
                        abs(last_pred["low"] - first_actual["low"])
                        / first_actual["low"]
                    )
                    * 100,
                    "close_gap_pct": (
                        abs(last_pred["close"] - first_actual["close"])
                        / first_actual["close"]
                    )
                    * 100,
                },
            }

        # Save to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        print(f"Prediction results saved to: {filepath}")
        return filepath

    except Exception as e:
        print(f"Failed to save prediction results: {e}")
        return None


def create_prediction_chart(
    df, pred_df, lookback, pred_len, actual_df=None, historical_start_idx=0
):
    """Create prediction chart"""
    # Use specified historical data start position, not always from the beginning of df
    if historical_start_idx + lookback + pred_len <= len(df):
        # Display lookback historical points + pred_len prediction points starting from specified position
        historical_df = df.iloc[historical_start_idx : historical_start_idx + lookback]
        prediction_range = range(
            historical_start_idx + lookback, historical_start_idx + lookback + pred_len
        )
    else:
        # If data is insufficient, adjust to maximum available range
        available_lookback = min(lookback, len(df) - historical_start_idx)
        available_pred_len = min(
            pred_len, max(0, len(df) - historical_start_idx - available_lookback)
        )
        historical_df = df.iloc[
            historical_start_idx : historical_start_idx + available_lookback
        ]
        prediction_range = range(
            historical_start_idx + available_lookback,
            historical_start_idx + available_lookback + available_pred_len,
        )

    # Create chart
    fig = go.Figure()

    # Add historical data (candlestick chart)
    fig.add_trace(
        go.Candlestick(
            x=(
                historical_df["timestamps"]
                if "timestamps" in historical_df.columns
                else historical_df.index
            ),
            open=historical_df["open"],
            high=historical_df["high"],
            low=historical_df["low"],
            close=historical_df["close"],
            name="Historical Data (400 data points)",
            increasing_line_color="#26A69A",
            decreasing_line_color="#EF5350",
        )
    )

    # Add prediction data (candlestick chart)
    if pred_df is not None and len(pred_df) > 0:
        # Calculate prediction data timestamps - ensure continuity with historical data
        if "timestamps" in df.columns and len(historical_df) > 0:
            # Start from the last timestamp of historical data, create prediction timestamps with the same time interval
            last_timestamp = historical_df["timestamps"].iloc[-1]
            time_diff = (
                df["timestamps"].iloc[1] - df["timestamps"].iloc[0]
                if len(df) > 1
                else pd.Timedelta(hours=1)
            )

            pred_timestamps = pd.date_range(
                start=last_timestamp + time_diff, periods=len(pred_df), freq=time_diff
            )
        else:
            # If no timestamps, use index
            pred_timestamps = range(
                len(historical_df), len(historical_df) + len(pred_df)
            )

        fig.add_trace(
            go.Candlestick(
                x=pred_timestamps,
                open=pred_df["open"],
                high=pred_df["high"],
                low=pred_df["low"],
                close=pred_df["close"],
                name="Prediction Data (120 data points)",
                increasing_line_color="#66BB6A",
                decreasing_line_color="#FF7043",
            )
        )

    # Add actual data for comparison (if exists)
    if actual_df is not None and len(actual_df) > 0:
        # Actual data should be in the same time period as prediction data
        if "timestamps" in df.columns:
            # Actual data should use the same timestamps as prediction data to ensure time alignment
            if "pred_timestamps" in locals():
                actual_timestamps = pred_timestamps
            else:
                # If no prediction timestamps, calculate from the last timestamp of historical data
                if len(historical_df) > 0:
                    last_timestamp = historical_df["timestamps"].iloc[-1]
                    time_diff = (
                        df["timestamps"].iloc[1] - df["timestamps"].iloc[0]
                        if len(df) > 1
                        else pd.Timedelta(hours=1)
                    )
                    actual_timestamps = pd.date_range(
                        start=last_timestamp + time_diff,
                        periods=len(actual_df),
                        freq=time_diff,
                    )
                else:
                    actual_timestamps = range(
                        len(historical_df), len(historical_df) + len(actual_df)
                    )
        else:
            actual_timestamps = range(
                len(historical_df), len(historical_df) + len(actual_df)
            )

        fig.add_trace(
            go.Candlestick(
                x=actual_timestamps,
                open=actual_df["open"],
                high=actual_df["high"],
                low=actual_df["low"],
                close=actual_df["close"],
                name="Actual Data (120 data points)",
                increasing_line_color="#FF9800",
                decreasing_line_color="#F44336",
            )
        )

    # Update layout
    fig.update_layout(
        title="Kronos Financial Prediction Results - 400 Historical Points + 120 Prediction Points vs 120 Actual Points",
        xaxis_title="Time",
        yaxis_title="Price",
        template="plotly_white",
        height=600,
        showlegend=True,
    )

    # Ensure x-axis time continuity
    if "timestamps" in historical_df.columns:
        # Get all timestamps and sort them
        all_timestamps = []
        if len(historical_df) > 0:
            all_timestamps.extend(historical_df["timestamps"])
        if "pred_timestamps" in locals():
            all_timestamps.extend(pred_timestamps)
        if "actual_timestamps" in locals():
            all_timestamps.extend(actual_timestamps)

        if all_timestamps:
            all_timestamps = sorted(all_timestamps)
            fig.update_xaxes(
                range=[all_timestamps[0], all_timestamps[-1]],
                rangeslider_visible=False,
                type="date",
            )

    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


@app.route("/")
def index():
    """Home page"""
    return render_template("index.html")


@app.route("/api/data-files")
def get_data_files():
    """Get available data file list"""
    data_files = []

    data_dir = app.config["DATA_DIR"]

    data_files += _get_data_files(data_dir)

    # Get wallet address from session
    wallet_address = session.get("wallet_address")
    if wallet_address and wallet_address != "":
        # Get files for specific user
        user_dir = _get_user_data_dir(wallet_address)
        data_files += _get_data_files(user_dir)

    return jsonify(data_files)


@app.route("/api/upload-data", methods=["POST"])
@require_auth
def upload_data():
    """Upload CSV or feather data file"""
    try:
        # Get wallet address from session
        wallet_address = session.get("wallet_address")
        if not wallet_address:
            return jsonify({"error": "Authentication required"}), 401

        # Check if file is present in request
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]

        # Check if file is selected
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Check if file extension is allowed
        if not allowed_file(file.filename):
            return (
                jsonify(
                    {
                        "error": f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
                    }
                ),
                400,
            )

        # Create user-specific upload folder
        user_upload_folder = _get_user_data_dir(wallet_address)

        # Generate secure filename
        filename = secure_filename(file.filename)
        file_path = os.path.join(user_upload_folder, filename)

        # Check if file already exists
        if os.path.exists(file_path):
            # Generate unique filename by adding timestamp
            base, ext = os.path.splitext(filename)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{base}_{timestamp}{ext}"
            file_path = os.path.join(user_upload_folder, filename)

        # Save file
        file.save(file_path)

        # Verify file was saved successfully
        if not os.path.exists(file_path):
            return jsonify({"error": "Failed to save file"}), 500

        # Clean up old files if exceed maximum limit
        removed_count = _cleanup_old_files(user_upload_folder, (".csv", ".feather"), MAX_UPLOAD_FILES)

        # Get file size
        file_size = os.path.getsize(file_path)

        # Build response message
        message_parts = [f"File uploaded successfully: {filename}"]
        if removed_count > 0:
            message_parts.append(f"Removed {removed_count} old file(s) to maintain limit of {MAX_UPLOAD_FILES} files")

        message = ". ".join(message_parts)

        # Convert absolute path to safe relative path for return
        safe_relative_path = _to_safe_relative_path(file_path)

        return jsonify(
            {
                "success": True,
                "message": message,
                "file_info": {
                    "name": filename,
                    "path": safe_relative_path,
                    "size": (
                        f"{file_size / 1024:.1f} KB"
                        if file_size < 1024 * 1024
                        else f"{file_size / (1024*1024):.1f} MB"
                    ),
                    "user_dir": wallet_address.lower(),
                },
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to upload file: {str(e)}"}), 500


@app.route("/api/load-data", methods=["POST"])
@require_auth
def load_data():
    """Load data file"""
    try:
        data = request.get_json()
        file_path = data.get("file_path")

        if not file_path:
            return jsonify({"error": "File path cannot be empty"}), 400

        # Convert relative path to absolute path and check security
        abs_file_path = _to_absolute_path(file_path)
        if not abs_file_path:
            return jsonify({"error": "Invalid file path"}), 400

        # Additional security check: ensure user can access this file
        wallet_address = session.get("wallet_address")
        if wallet_address and not _is_safe_file_path(file_path, wallet_address):
            return jsonify({"error": "Access to this file is not allowed"}), 403

        df, error = load_data_file(abs_file_path)
        if error:
            return jsonify({"error": error}), 400

        # Detect data time frequency
        def detect_timeframe(df):
            if len(df) < 2:
                return "Unknown"

            time_diffs = []
            for i in range(1, min(10, len(df))):  # Check first 10 time differences
                diff = df["timestamps"].iloc[i] - df["timestamps"].iloc[i - 1]
                time_diffs.append(diff)

            if not time_diffs:
                return "Unknown"

            # Calculate average time difference
            avg_diff = sum(time_diffs, pd.Timedelta(0)) / len(time_diffs)

            # Convert to readable format
            if avg_diff < pd.Timedelta(minutes=1):
                return f"{avg_diff.total_seconds():.0f} seconds"
            elif avg_diff < pd.Timedelta(hours=1):
                return f"{avg_diff.total_seconds() / 60:.0f} minutes"
            elif avg_diff < pd.Timedelta(days=1):
                return f"{avg_diff.total_seconds() / 3600:.0f} hours"
            else:
                return f"{avg_diff.days} days"

        # Return data information
        data_info = {
            "rows": len(df),
            "columns": list(df.columns),
            "start_date": (
                df["timestamps"].min().isoformat()
                if "timestamps" in df.columns
                else "N/A"
            ),
            "end_date": (
                df["timestamps"].max().isoformat()
                if "timestamps" in df.columns
                else "N/A"
            ),
            "price_range": {
                "min": float(df[["open", "high", "low", "close"]].min().min()),
                "max": float(df[["open", "high", "low", "close"]].max().max()),
            },
            "prediction_columns": ["open", "high", "low", "close"]
            + (["volume"] if "volume" in df.columns else []),
            "timeframe": detect_timeframe(df),
        }

        return jsonify(
            {
                "success": True,
                "data_info": data_info,
                "message": f"Successfully loaded data, total {len(df)} rows",
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to load data: {str(e)}"}), 500


@app.route("/api/predict", methods=["POST"])
@require_auth
def predict():
    """Perform prediction"""
    wallet_address = session.get("wallet_address")
    if wallet_address is None or wallet_address == "":
        return jsonify({"error": "Invalid auth"}), 401
    results_dir = _get_user_data_dir(wallet_address)
    try:
        data = request.get_json()
        file_path = data.get("file_path")
        lookback = int(data.get("lookback", 400))
        pred_len = int(data.get("pred_len", 120))

        # Get prediction quality parameters
        temperature = float(data.get("temperature", 1.0))
        top_p = float(data.get("top_p", 0.9))
        sample_count = int(data.get("sample_count", 1))

        if not file_path:
            return jsonify({"error": "File path cannot be empty"}), 400

        # Convert relative path to absolute path and check security
        abs_file_path = _to_absolute_path(file_path)
        if not abs_file_path:
            return jsonify({"error": "Invalid file path"}), 400

        # Additional security check: ensure user can access this file
        if not _is_safe_file_path(file_path, wallet_address):
            return jsonify({"error": "Access to this file is not allowed"}), 403

        # Load data
        df, error = load_data_file(abs_file_path)
        if error:
            return jsonify({"error": error}), 400

        if len(df) < lookback:
            return (
                jsonify(
                    {
                        "error": f"Insufficient data length, need at least {lookback} rows"
                    }
                ),
                400,
            )

        # Perform prediction
        if MODEL_AVAILABLE and predictor is not None:
            try:
                # Use real Kronos model
                # Only use necessary columns: OHLCV, excluding amount
                required_cols = ["open", "high", "low", "close"]
                if "volume" in df.columns:
                    required_cols.append("volume")

                # Process time period selection
                start_date = data.get("start_date")

                if start_date:
                    # Custom time period - fix logic: use data within selected window
                    start_dt = pd.to_datetime(start_date)

                    # Find data after start time
                    mask = df["timestamps"] >= start_dt
                    time_range_df = df[mask]

                    # Ensure sufficient data: lookback + pred_len
                    if len(time_range_df) < lookback + pred_len:
                        return (
                            jsonify(
                                {
                                    "error": f'Insufficient data from start time {start_dt.strftime("%Y-%m-%d %H:%M")}, need at least {lookback + pred_len} data points, currently only {len(time_range_df)} available'
                                }
                            ),
                            400,
                        )

                    # Use first lookback data points within selected window for prediction
                    x_df = time_range_df.iloc[:lookback][required_cols]
                    x_timestamp = time_range_df.iloc[:lookback]["timestamps"]

                    # Use last pred_len data points within selected window as actual values
                    y_timestamp = time_range_df.iloc[lookback : lookback + pred_len][
                        "timestamps"
                    ]

                    # Calculate actual time period length
                    start_timestamp = time_range_df["timestamps"].iloc[0]
                    end_timestamp = time_range_df["timestamps"].iloc[
                        lookback + pred_len - 1
                    ]
                    time_span = end_timestamp - start_timestamp

                    prediction_type = f"Kronos model prediction (within selected window: first {lookback} data points for prediction, last {pred_len} data points for comparison, time span: {time_span})"
                else:
                    # Use latest data
                    x_df = df.iloc[:lookback][required_cols]
                    x_timestamp = df.iloc[:lookback]["timestamps"]
                    y_timestamp = df.iloc[lookback : lookback + pred_len]["timestamps"]
                    prediction_type = "Kronos model prediction (latest data)"

                # Ensure timestamps are Series format, not DatetimeIndex, to avoid .dt attribute error in Kronos model
                if isinstance(x_timestamp, pd.DatetimeIndex):
                    x_timestamp = pd.Series(x_timestamp, name="timestamps")
                if isinstance(y_timestamp, pd.DatetimeIndex):
                    y_timestamp = pd.Series(y_timestamp, name="timestamps")

                pred_df = predictor.predict(
                    df=x_df,
                    x_timestamp=x_timestamp,
                    y_timestamp=y_timestamp,
                    pred_len=pred_len,
                    T=temperature,
                    top_p=top_p,
                    sample_count=sample_count,
                )

            except Exception as e:
                return (
                    jsonify({"error": f"Kronos model prediction failed: {str(e)}"}),
                    500,
                )
        else:
            return (
                jsonify({"error": "Kronos model not loaded, please load model first"}),
                400,
            )

        # Prepare actual data for comparison (if exists)
        actual_data = []
        actual_df = None

        if start_date:  # Custom time period
            # Fix logic: use data within selected window
            # Prediction uses first 400 data points within selected window
            # Actual data should be last 120 data points within selected window
            start_dt = pd.to_datetime(start_date)

            # Find data starting from start_date
            mask = df["timestamps"] >= start_dt
            time_range_df = df[mask]

            if len(time_range_df) >= lookback + pred_len:
                # Get last 120 data points within selected window as actual values
                actual_df = time_range_df.iloc[lookback : lookback + pred_len]

                for i, (_, row) in enumerate(actual_df.iterrows()):
                    actual_data.append(
                        {
                            "timestamp": row["timestamps"].isoformat(),
                            "open": float(row["open"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "close": float(row["close"]),
                            "volume": float(row["volume"]) if "volume" in row else 0,
                            "amount": float(row["amount"]) if "amount" in row else 0,
                        }
                    )
        else:  # Latest data
            # Prediction uses first 400 data points
            # Actual data should be 120 data points after first 400 data points
            if len(df) >= lookback + pred_len:
                actual_df = df.iloc[lookback : lookback + pred_len]
                for i, (_, row) in enumerate(actual_df.iterrows()):
                    actual_data.append(
                        {
                            "timestamp": row["timestamps"].isoformat(),
                            "open": float(row["open"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "close": float(row["close"]),
                            "volume": float(row["volume"]) if "volume" in row else 0,
                            "amount": float(row["amount"]) if "amount" in row else 0,
                        }
                    )

        # Create chart - pass historical data start position
        if start_date:
            # Custom time period: find starting position of historical data in original df
            start_dt = pd.to_datetime(start_date)
            mask = df["timestamps"] >= start_dt
            historical_start_idx = df[mask].index[0] if len(df[mask]) > 0 else 0
        else:
            # Latest data: start from beginning
            historical_start_idx = 0

        chart_json = create_prediction_chart(
            df, pred_df, lookback, pred_len, actual_df, historical_start_idx
        )

        # Prepare prediction result data - fix timestamp calculation logic
        if "timestamps" in df.columns:
            if start_date:
                # Custom time period: use selected window data to calculate timestamps
                start_dt = pd.to_datetime(start_date)
                mask = df["timestamps"] >= start_dt
                time_range_df = df[mask]

                if len(time_range_df) >= lookback:
                    # Calculate prediction timestamps starting from last time point of selected window
                    last_timestamp = time_range_df["timestamps"].iloc[lookback - 1]
                    time_diff = df["timestamps"].iloc[1] - df["timestamps"].iloc[0]
                    future_timestamps = pd.date_range(
                        start=last_timestamp + time_diff,
                        periods=pred_len,
                        freq=time_diff,
                    )
                else:
                    future_timestamps = []
            else:
                # Latest data: calculate from last time point of entire data file
                last_timestamp = df["timestamps"].iloc[-1]
                time_diff = df["timestamps"].iloc[1] - df["timestamps"].iloc[0]
                future_timestamps = pd.date_range(
                    start=last_timestamp + time_diff, periods=pred_len, freq=time_diff
                )
        else:
            future_timestamps = range(len(df), len(df) + pred_len)

        prediction_results = []
        for i, (_, row) in enumerate(pred_df.iterrows()):
            prediction_results.append(
                {
                    "timestamp": (
                        future_timestamps[i].isoformat()
                        if i < len(future_timestamps)
                        else f"T{i}"
                    ),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]) if "volume" in row else 0,
                    "amount": float(row["amount"]) if "amount" in row else 0,
                }
            )

        # Save prediction results to file
        try:
            save_prediction_results(
                results_dir=results_dir,
                file_path=abs_file_path,
                prediction_type=prediction_type,
                prediction_results=prediction_results,
                actual_data=actual_data,
                input_data=x_df,
                prediction_params={
                    "lookback": lookback,
                    "pred_len": pred_len,
                    "temperature": temperature,
                    "top_p": top_p,
                    "sample_count": sample_count,
                    "start_date": start_date if start_date else "latest",
                },
            )
            _cleanup_old_files(results_dir, (".json"), MAX_RESULT_FILES)
        except Exception as e:
            print(f"Failed to save prediction results: {e}")

        return jsonify(
            {
                "success": True,
                "prediction_type": prediction_type,
                "chart": chart_json,
                "prediction_results": prediction_results,
                "actual_data": actual_data,
                "has_comparison": len(actual_data) > 0,
                "message": f"Prediction completed, generated {pred_len} prediction points"
                + (
                    f", including {len(actual_data)} actual data points for comparison"
                    if len(actual_data) > 0
                    else ""
                ),
            }
        )

    except Exception as e:
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500


@app.route("/api/load-model", methods=["POST"])
@require_admin_auth
def load_model():
    """Load Kronos model"""
    global tokenizer, model, predictor

    try:
        if not MODEL_AVAILABLE:
            return jsonify({"error": "Kronos model library not available"}), 400

        data = request.get_json()
        model_key = data.get("model_key", "kronos-small")
        device = data.get("device", "cpu")

        model_config = _load_model(model_key, device)

        return jsonify(
            {
                "success": True,
                "message": f'Model loaded successfully: {model_config["name"]} ({model_config["params"]}) on {device}',
                "model_info": {
                    "name": model_config["name"],
                    "params": model_config["params"],
                    "context_length": model_config["context_length"],
                    "description": model_config["description"],
                },
            }
        )

    except Exception as e:
        return jsonify({"error": f"Model loading failed: {str(e)}"}), 500


@app.route("/api/available-models")
def get_available_models():
    """Get available model list"""
    return jsonify({"models": AVAILABLE_MODELS, "model_available": MODEL_AVAILABLE})


@app.route("/api/model-status")
def get_model_status():
    """Get model status"""
    if MODEL_AVAILABLE:
        if predictor is not None:
            return jsonify(
                {
                    "available": True,
                    "loaded": True,
                    "message": "Kronos model loaded and available",
                    "current_model": {
                        "name": predictor.model.__class__.__name__,
                        "key": KRONOS_MODEL_KEY,
                        "device": str(next(predictor.model.parameters()).device),
                    },
                }
            )
        else:
            return jsonify(
                {
                    "available": True,
                    "loaded": False,
                    "message": "Kronos model available but not loaded",
                }
            )
    else:
        return jsonify(
            {
                "available": False,
                "loaded": False,
                "message": "Kronos model library not available, please install related dependencies",
            }
        )


@app.route("/api/only-predict", methods=["POST"])
# @require_auth
def only_predict():
    """Predict only, not analysis"""
    wallet_address = session.get("wallet_address")
    if wallet_address is None or wallet_address == "":
        return jsonify({"error": "Invalid auth"}), 401
    results_dir = _get_user_data_dir(wallet_address)
    try:
        data = request.get_json()
        file_path = data.get("file_path")
        lookback = int(data.get("lookback", 400))
        pred_len = int(data.get("pred_len", 120))

        # Get prediction quality parameters
        temperature = float(data.get("temperature", 1.0))
        top_p = float(data.get("top_p", 0.9))
        sample_count = int(data.get("sample_count", 1))

        if not file_path:
            return jsonify({"error": "File path cannot be empty"}), 400

        # Convert relative path to absolute path and check security
        abs_file_path = _to_absolute_path(file_path)
        if not abs_file_path:
            return jsonify({"error": "Invalid file path"}), 400

        # Additional security check: ensure user can access this file
        if not _is_safe_file_path(file_path, wallet_address):
            return jsonify({"error": "Access to this file is not allowed"}), 403

        # Load data
        df, error = load_data_file(abs_file_path)
        if error:
            return jsonify({"error": error}), 400

        if len(df) < lookback:
            return (
                jsonify(
                    {
                        "error": f"Insufficient data length, need at least {lookback} rows"
                    }
                ),
                400,
            )

        # Perform prediction
        try:
            # Use real Kronos model
            # Only use necessary columns: OHLCV, excluding amount
            required_cols = ["open", "high", "low", "close"]
            if "volume" in df.columns:
                required_cols.append("volume")

            # Process time period selection
            start_date = data.get("start_date")

            if start_date:
                # Custom time period - fix logic: use data within selected window
                start_dt = pd.to_datetime(start_date)

                # Find data after start time
                mask = df["timestamps"] >= start_dt
                time_range_df = df[mask]

                # Ensure sufficient data: lookback + pred_len
                if len(time_range_df) < lookback + pred_len:
                    return (
                        jsonify(
                            {
                                "error": f'Insufficient data from start time {start_dt.strftime("%Y-%m-%d %H:%M")}, need at least {lookback + pred_len} data points, currently only {len(time_range_df)} available'
                            }
                        ),
                        400,
                    )

                # Use first lookback data points within selected window for prediction
                x_df = time_range_df.iloc[:lookback][required_cols]
                x_timestamp = time_range_df.iloc[:lookback]["timestamps"]

                # Use last pred_len data points within selected window as actual values
                y_timestamp = time_range_df.iloc[lookback : lookback + pred_len][
                    "timestamps"
                ]

                # Calculate actual time period length
                start_timestamp = time_range_df["timestamps"].iloc[0]
                end_timestamp = time_range_df["timestamps"].iloc[
                    lookback + pred_len - 1
                ]
                time_span = end_timestamp - start_timestamp

                prediction_type = f"Kronos model prediction (within selected window: first {lookback} data points for prediction, last {pred_len} data points for comparison, time span: {time_span})"
            else:
                # Use latest data
                x_df = df.iloc[:lookback][required_cols]
                x_timestamp = df.iloc[:lookback]["timestamps"]
                y_timestamp = df.iloc[lookback : lookback + pred_len]["timestamps"]
                prediction_type = "Kronos model prediction (latest data)"

            # Ensure timestamps are Series format, not DatetimeIndex, to avoid .dt attribute error in Kronos model
            if isinstance(x_timestamp, pd.DatetimeIndex):
                x_timestamp = pd.Series(x_timestamp, name="timestamps")
            if isinstance(y_timestamp, pd.DatetimeIndex):
                y_timestamp = pd.Series(y_timestamp, name="timestamps")

            pred_df = predictor.predict(
                df=x_df,
                x_timestamp=x_timestamp,
                y_timestamp=y_timestamp,
                pred_len=pred_len,
                T=temperature,
                top_p=top_p,
                sample_count=sample_count,
            )

            file_name = os.path.basename(abs_file_path)
            pred_file_path = os.path.join(results_dir, f"{file_name}_pred.json")
            # pred_df.to_csv(f"{abs_file_path}_pred.csv", index=False)
            pred_df.to_json(pred_file_path, orient="records")
            _cleanup_old_files(results_dir, (".json"), MAX_RESULT_FILES)

        except Exception as e:
            return (
                jsonify({"error": f"Kronos model prediction failed: {str(e)}"}),
                500,
            )

        # Convert absolute prediction file path to relative path for return
        pred_relative_path = _to_safe_relative_path(pred_file_path)
        if not pred_relative_path:
            return jsonify({"error": "Failed to save prediction results"}), 500

        return jsonify(
            {
                "success": True,
                "prediction_type": prediction_type,
                "prediction_result_file": pred_relative_path,
            }
        )
    except Exception as e:
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("Starting Kronos Web UI...")
    print(f"Model availability: {MODEL_AVAILABLE}")
    if MODEL_AVAILABLE:
        print("Tip: You can load Kronos model through /api/load-model endpoint")
    else:
        print("Tip: Will use simulated data for demonstration")

    app.run(debug=True, host="0.0.0.0", port=7070)
