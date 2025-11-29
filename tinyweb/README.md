# TinyWeb Installation, Configuration & Startup Guide

TinyWeb is a Flask-based financial prediction web application that integrates the Kronos time series prediction model.

## System Requirements

- Python 3.8+
- Operating System: Linux, macOS, or Windows
- Memory: 8GB+ recommended (if using GPU for prediction)
- Disk Space: At least 2GB available space

## Installation Steps

### 1. Clone the Project

```bash
# Clone from Git repository
git clone <repository-url>
cd Kronos/tinyweb

# Or directly navigate to tinyweb directory
cd /path/to/Kronos/tinyweb
```

### 2. Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Make sure virtual environment is activated
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Environment Configuration File

Copy the configuration template and create a `.env` file:

```bash
cp config.env.example .env
```

Edit the `.env` file and configure the following parameters:

```bash
# Kronos Model Configuration
KRONOS_MODEL_KEY=kronos-base          # Options: kronos-mini, kronos-small, kronos-base
KRONOS_MODEL_DEVICE=cpu               # Device: cpu, cuda, mps

# Flask Configuration
SECRET_KEY=your-secret-key-here       # Flask secret key (optional, auto-generated)

# Data Directory Configuration
DATA_DIR=./data                       # Data storage directory

# File Upload Limits
MAX_UPLOAD_FILES=3                    # Max upload files per user
MAX_RESULT_FILES=3                    # Max result files per user

# Admin Configuration
ADMIN_WALLET_ADDRESS=0x...            # Admin wallet address
```

### 2. Create Required Directories

```bash
# Create data directories
mkdir -p data

# Ensure write permissions
chmod 755 data
```

### 3. Model Configuration

TinyWeb supports three Kronos models:

- **kronos-mini**: 4.1M parameters, lightweight model with fast prediction speed
- **kronos-small**: 24.7M parameters, balanced performance and speed
- **kronos-base**: 102.3M parameters, base model with better prediction quality

On first startup, the application will automatically download model files from HuggingFace.

## Starting the Application

### Method 1: Using Startup Script (Recommended)

```bash
# Ensure virtual environment is activated
chmod +x start.sh
./start.sh
```

### Method 2: Manual Startup

```bash
# Ensure virtual environment is activated
python3 app.py
```

### Method 3: Development Mode

```bash
# Development mode with debugging and hot reload
export FLASK_ENV=development
python3 app.py
```

## Accessing the Application

After successful startup, visit:

- Web Interface: http://localhost:7070
- API Documentation: http://localhost:7070 (embedded in application)

## Usage Instructions

### 1. Data Upload

Supported data formats:
- CSV files (.csv)
- Feather files (.feather)

Data files must contain the following columns:
- `open`: Open price
- `high`: High price
- `low`: Low price
- `close`: Close price

Optional columns:
- `volume`: Trading volume
- `timestamps`/`timestamp`/`date`: Timestamp

### 2. Prediction Features

- **Historical Data Points**: Default uses 400 historical data points
- **Prediction Data Points**: Default predicts 120 future data points
- **Quality Parameters**:
  - Temperature: Controls prediction randomness (default 1.0)
  - Top P: Nucleus sampling parameter (default 0.9)
  - Sample Count: Number of samples (default 1)

### 3. Wallet Authentication

The application uses wallet addresses for user authentication:
- First-time access requires wallet connection
- Each user has independent data storage space
- Admin wallet address is configured in the `.env` file

## Production Deployment

### 1. Using Gunicorn

```bash
# Install Gunicorn
pip install gunicorn

# Start application
gunicorn -w 4 -b 0.0.0.0:7070 app:app
```

### 2. Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN python3 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 7070

CMD ["python", "app.py"]
```

Build and run:

```bash
docker build -t tinyweb .
docker run -p 7070:7070 -v $(pwd)/data:/app/data tinyweb
```

### 3. Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:7070;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## API Endpoints

Main API endpoints:

- `GET /`: Homepage
- `GET /api/data-files`: Get data file list
- `POST /api/upload-data`: Upload data file
- `POST /api/load-data`: Load data file
- `POST /api/predict`: Execute prediction
- `POST /api/only-predict`: Prediction without analysis
- `GET /api/available-models`: Get available model list
- `GET /api/model-status`: Get model status
- `POST /api/load-model`: Load model (admin only)
- `GET /api/download/<file_path>`: Download file

## License

Please refer to the LICENSE file in the project root directory.