#!/usr/bin/env python3
"""
TinyWeb Client SDK

A Python SDK for the TinyWeb API that provides Web3-based authentication,
financial data prediction, and file management capabilities.

Features:
- Web3 wallet signature authentication
- Data file upload and management
- Kronos model predictions
- Session management
- Comprehensive error handling

Example usage:
    from tinyweb_client import TinyWebClient

    client = TinyWebClient(base_url="http://localhost:7070")

    # Authenticate with wallet
    client.authenticate_wallet("0x...", private_key)

    # Upload data file
    file_info = client.upload_data_file("data.csv")

    # Run prediction
    results = client.predict(
        file_path=file_info["path"],
        lookback=400,
        pred_len=120
    )
"""

import requests
import json
from typing import Optional, Dict, Any, List, Union, BinaryIO
from datetime import datetime
import os
from pathlib import Path
import time


class TinyWebError(Exception):
    """Base exception for TinyWeb API errors."""
    pass


class AuthenticationError(TinyWebError):
    """Authentication related errors."""
    pass


class FileNotFoundError(TinyWebError):
    """File not found errors."""
    pass


class PredictionError(TinyWebError):
    """Prediction related errors."""
    pass


class TinyWebClient:
    """
    TinyWeb API Client SDK

    Provides a Python interface to interact with the TinyWeb API for
    financial data prediction using Web3 authentication.
    """

    def __init__(self, base_url: str = "http://localhost:7070", timeout: int = 300):
        """
        Initialize TinyWeb client.

        Args:
            base_url: Base URL of the TinyWeb API server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = timeout
        self._authenticated = False
        self._wallet_address = None
        self._user_info = None

        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            **kwargs: Additional arguments passed to requests

        Returns:
            Response JSON as dictionary

        Raises:
            TinyWebError: For API errors
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()

            # Handle empty response
            if response.text.strip():
                return response.json()
            return {"success": True}

        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    if e.response.text.strip():
                        error_data = e.response.json()
                        if 'error' in error_data:
                            error_msg = error_data['error']
                    else:
                        error_msg = f"{e.response.status_code} {e.response.reason}: Empty response body"
                except json.JSONDecodeError:
                    error_msg = f"{e.response.status_code} {e.response.reason}: Failed to decode JSON object: Expecting value: line 1 column 1 (char 0)"
                except:
                    pass
            raise TinyWebError(error_msg)

    # Authentication Methods

    def get_challenge(self, wallet_address: str) -> Dict[str, Any]:
        """
        Get authentication challenge message for wallet signature.

        Args:
            wallet_address: Ethereum wallet address

        Returns:
            Challenge message and nonce
        """
        data = {"wallet_address": wallet_address}
        return self._make_request("POST", "/api/auth/challenge", json=data)

    def verify_signature(self, wallet_address: str, signature: str,
                        message: str, invite_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify wallet signature and complete authentication.

        Args:
            wallet_address: Ethereum wallet address
            signature: Signed challenge message
            message: Original challenge message
            invite_code: Optional invite code for new users

        Returns:
            Authentication result and user information
        """
        data = {
            "wallet_address": wallet_address,
            "signature": signature,
            "message": message
        }

        if invite_code:
            data["invite_code"] = invite_code

        result = self._make_request("POST", "/api/auth/verify", json=data)

        if result.get("success"):
            self._authenticated = True
            self._wallet_address = wallet_address
            self._user_info = result.get("user", {})

        return result

    def authenticate_wallet(self, wallet_address: str, private_key: str,
                          invite_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Authenticate using wallet signature (requires web3 library for signing).

        Note: This is a placeholder. You need to implement the actual signing
        logic using web3.py or similar library to sign the challenge message.

        Args:
            wallet_address: Ethereum wallet address
            private_key: Private key for signing (or use external signer)
            invite_code: Optional invite code for new users

        Returns:
            Authentication result and user info
        """
        try:
            # Get challenge
            challenge_result = self.get_challenge(wallet_address)
            message = challenge_result["message"]

            # implement signature generation
            from web3 import Web3
            from eth_account.messages import encode_defunct
            w3 = Web3()
            message_encoded = encode_defunct(text=message)
            signed_message = w3.eth.account.sign_message(message_encoded, private_key)
            signature = signed_message.signature.hex()

            return self.verify_signature(wallet_address, signature, message, invite_code)
        except TinyWebError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    def get_auth_status(self) -> Dict[str, Any]:
        """
        Get current authentication status.

        Returns:
            Authentication status and user information
        """
        result = self._make_request("GET", "/api/auth/status")

        if result.get("authenticated"):
            self._authenticated = True
            self._user_info = result.get("user", {})
            self._wallet_address = self._user_info.get("wallet_address")
        else:
            self._authenticated = False
            self._user_info = None
            self._wallet_address = None

        return result

    def update_profile(self, nickname: str) -> Dict[str, Any]:
        """
        Update user profile information.

        Args:
            nickname: New nickname

        Returns:
            Update result
        """
        if not self._authenticated:
            raise AuthenticationError("Authentication required")

        data = {"nickname": nickname}
        result = self._make_request("POST", "/api/auth/profile", json=data)

        if result.get("success"):
            if self._user_info:
                self._user_info["nickname"] = nickname

        return result

    def logout(self) -> Dict[str, Any]:
        """
        Logout current user.

        Returns:
            Logout result
        """
        result = self._make_request("POST", "/api/auth/logout")

        self._authenticated = False
        self._wallet_address = None
        self._user_info = None

        return result

    # Invite Code Management

    def create_invite_code(self, code: str, max_uses: int = 1) -> Dict[str, Any]:
        """
        Create new invite code (admin only).

        Args:
            code: Invite code string to create
            max_uses: Maximum number of uses (0 for unlimited, default: 1)

        Returns:
            Created invite code information
        """
        data = {
            "code": code,
            "max_uses": max_uses
        }
        return self._make_request("POST", "/api/auth/invite/create", json=data)

    def validate_invite_code(self, invite_code: str) -> Dict[str, Any]:
        """
        Validate invite code.

        Args:
            invite_code: Invite code to validate

        Returns:
            Validation result
        """
        data = {"invite_code": invite_code}
        return self._make_request("POST", "/api/auth/invite/validate", json=data)

    def list_invite_codes(self) -> Dict[str, Any]:
        """
        List all invite codes (admin only).

        Returns:
            List of invite codes
        """
        return self._make_request("GET", "/api/auth/invite/list")

    def deactivate_invite_code(self, invite_code: str) -> Dict[str, Any]:
        """
        Deactivate invite code (admin only).

        Args:
            invite_code: Invite code to deactivate

        Returns:
            Deactivation result
        """
        data = {"invite_code": invite_code}
        return self._make_request("POST", "/api/auth/invite/deactivate", json=data)

    # Data Management Methods

    def get_data_files(self) -> List[Dict[str, Any]]:
        """
        Get list of available data files.

        Returns:
            List of data files with metadata
        """
        if not self._authenticated:
            raise AuthenticationError("Authentication required")

        return self._make_request("GET", "/api/data-files")

    def upload_data_file(self, file_path: str, file_obj: Optional[BinaryIO] = None) -> Dict[str, Any]:
        """
        Upload data file (CSV or Feather format).

        Args:
            file_path: Path to file or filename if file_obj is provided
            file_obj: File-like object (optional, if not provided will read from file_path)

        Returns:
            Upload result with file information
        """
        if not self._authenticated:
            raise AuthenticationError("Authentication required")

        # Prepare file for upload
        if file_obj is None:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            filename = os.path.basename(file_path)
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, 'application/octet-stream')}
                return self._make_request("POST", "/api/upload-data", files=files)
        else:
            filename = os.path.basename(file_path)
            files = {'file': (filename, file_obj, 'application/octet-stream')}
            return self._make_request("POST", "/api/upload-data", files=files)

    def load_data_file(self, file_path: str) -> Dict[str, Any]:
        """
        Load and analyze data file.

        Args:
            file_path: Path to the data file

        Returns:
            Data analysis information
        """
        if not self._authenticated:
            raise AuthenticationError("Authentication required")

        data = {"file_path": file_path}
        return self._make_request("POST", "/api/load-data", json=data)

    # Prediction Methods

    def predict(self, file_path: str, lookback: int = 400, pred_len: int = 120,
                temperature: float = 1.0, top_p: float = 0.9,
                sample_count: int = 1, start_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Run Kronos model prediction.

        Args:
            file_path: Path to the data file
            lookback: Number of historical data points to consider
            pred_len: Number of future prediction points
            temperature: Temperature parameter for sampling
            top_p: Top-p sampling parameter
            sample_count: Number of prediction samples
            start_date: Start date for prediction (ISO format)

        Returns:
            Prediction results with chart data
        """
        if not self._authenticated:
            raise AuthenticationError("Authentication required")

        data = {
            "file_path": file_path,
            "lookback": lookback,
            "pred_len": pred_len,
            "temperature": temperature,
            "top_p": top_p,
            "sample_count": sample_count
        }

        if start_date:
            data["start_date"] = start_date

        return self._make_request("POST", "/api/predict", json=data)

    def predict_only(self, file_path: str, lookback: int = 400, pred_len: int = 120,
                          temperature: float = 1.0, top_p: float = 0.9,
                          sample_count: int = 1, start_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Run simplified only prediction.

        Args:
            file_path: Path to the data file
            lookback: Number of historical data points to consider
            pred_len: Number of future prediction points
            temperature: Temperature parameter for sampling
            top_p: Top-p sampling parameter
            sample_count: Number of prediction samples
            start_date: Start date for prediction (ISO format)

        Returns:
            Prediction results file path
        """
        if not self._authenticated:
            raise AuthenticationError("Authentication required")

        data = {
            "file_path": file_path,
            "lookback": lookback,
            "pred_len": pred_len,
            "temperature": temperature,
            "top_p": top_p,
            "sample_count": sample_count
        }

        if start_date:
            data["start_date"] = start_date

        return self._make_request("POST", "/api/only-predict", json=data)

    # Model Management Methods

    def get_available_models(self) -> Dict[str, Any]:
        """
        Get list of available Kronos models.

        Returns:
            Available models information
        """
        return self._make_request("GET", "/api/available-models")

    def get_model_status(self) -> Dict[str, Any]:
        """
        Get current model status.

        Returns:
            Model status information
        """
        return self._make_request("GET", "/api/model-status")

    def load_model(self, model_key: str, device: str = "cpu") -> Dict[str, Any]:
        """
        Load or change Kronos model (admin only).

        Args:
            model_key: Model identifier (kronos-mini, kronos-small, kronos-base)
            device: Device to load model on (cpu, cuda, mps)

        Returns:
            Model loading result
        """
        data = {
            "model_key": model_key,
            "device": device
        }
        return self._make_request("POST", "/api/load-model", json=data)

    # Utility Methods

    def is_authenticated(self) -> bool:
        """
        Check if client is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        return self._authenticated

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current user information.

        Returns:
            User information or None if not authenticated
        """
        return self._user_info

    def get_wallet_address(self) -> Optional[str]:
        """
        Get authenticated wallet address.

        Returns:
            Wallet address or None if not authenticated
        """
        return self._wallet_address

    def wait_for_prediction(self, prediction_id: str, timeout: int = 600,
                           poll_interval: int = 5) -> Dict[str, Any]:
        """
        Wait for prediction completion (for async operations).

        Note: This is a placeholder implementation. The actual API
        may have different async prediction handling.

        Args:
            prediction_id: Prediction identifier
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Final prediction results
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # This would need to be implemented based on actual API
                # result = self.get_prediction_status(prediction_id)
                # if result.get("completed"):
                #     return result

                time.sleep(poll_interval)
            except Exception as e:
                raise PredictionError(f"Error waiting for prediction: {str(e)}")

        raise PredictionError("Prediction timeout exceeded")

    def save_results_to_file(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Save prediction results to file.

        Args:
            results: Prediction results dictionary
            output_path: Path to save results
        """
        try:
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
        except Exception as e:
            raise TinyWebError(f"Failed to save results: {str(e)}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup if needed."""
        if self._authenticated:
            try:
                self.logout()
            except:
                pass  # Ignore logout errors in cleanup


# Example usage and helper functions
def create_client_with_web3(base_url: str = "http://localhost:7070",
                          wallet_address: str = None,
                          private_key: str = None) -> TinyWebClient:
    """
    Helper function to create and authenticate client using web3.py.

    Note: Requires web3.py to be installed.

    Args:
        base_url: API base URL
        wallet_address: Ethereum wallet address
        private_key: Private key for signing

    Returns:
        Authenticated TinyWebClient instance
    """
    client = TinyWebClient(base_url)

    if wallet_address and private_key:
        try:
            client.authenticate_wallet(wallet_address, private_key)
        except Exception as e:
            raise AuthenticationError(f"Failed to create authenticated client: {str(e)}")

    return client


if __name__ == "__main__":
    # Example usage
    print("TinyWeb Client SDK")
    print("=" * 50)

    # Example workflow
    try:
        # Create client
        client = create_client_with_web3(
            base_url = "http://localhost:7070",
            wallet_address=os.environ.get("WALLET_ADDRESS"),
            private_key=os.environ.get("PRIVATE_KEY"))

        # Check authentication status
        status = client.get_auth_status()
        print(f"Authentication status: {status}")

        if not client.is_authenticated():
            print("Please authenticate using wallet signature")
            print("1. Get challenge with get_challenge(wallet_address)")
            print("2. Sign message with your private key")
            print("3. Verify signature with verify_signature()")

        # List available models
        models = client.get_available_models()
        print(f"Available models: {models}")

        # Get model status
        model_status = client.get_model_status()
        print(f"Model status: {model_status}")

    except TinyWebError as e:
        print(f"Error: {e}")