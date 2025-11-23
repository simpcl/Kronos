#!/usr/bin/env python3
"""
TinyWeb CLI Tool

A command-line interface for the TinyWeb API that provides Web3-based authentication,
financial data prediction, and file management capabilities.

Usage:
    python3 tinyweb_cli.py [COMMAND] [OPTIONS]

Commands:
    Configuration:
        config               Show current configuration

    Authentication:
        login                 Authenticate with wallet signature
        status               Show authentication status
        logout               Logout current user
        profile              Update user profile

    Invite Codes:
        create-invite        Create new invite code (admin only)
        list-invites         List all invite codes (admin only)
        validate-invite      Validate invite code
        deactivate-invite    Deactivate invite code (admin only)

    Data Management:
        upload               Upload data file (CSV/Feather)
        list-files           List available data files
        load-data            Load and analyze data file

    Predictions:
        predict              Run Kronos model prediction
        predict-all          Run simplified all-in-one prediction

    Model Management:
        list-models          List available models
        model-status         Show current model status
        load-model           Load or change model (admin only)

Examples:
    # Show configuration
    python3 tinyweb_cli.py config

    # Login with wallet (can use environment variables)
    python3 tinyweb_cli.py login

    # Login with command line arguments
    python3 tinyweb_cli.py login --wallet 0x123... --private-key your_key

    # Upload data file
    python3 tinyweb_cli.py upload --file data.csv

    # Run prediction
    python3 tinyweb_cli.py predict --file data.csv --lookback 400 --pred-len 120

    # Create invite code (admin)
    python3 tinyweb_cli.py create-invite --code TEST123 --max-uses 5

Environment Variables:
    TINYWEB_API_URL         API base URL (default: http://localhost:7070)
    TINYWEB_API_TIMEOUT     Request timeout in seconds (default: 300)
    DEFAULT_WALLET_ADDRESS  Default wallet address for login
    PRIVATE_KEY            Default private key for authentication

Configuration File (.env):
    Create a .env file in the same directory to store your settings.
    Example .env file:
        TINYWEB_API_URL=http://localhost:7070
        TINYWEB_API_TIMEOUT=5000
        DEFAULT_WALLET_ADDRESS=0x123...
        PRIVATE_KEY=0xabcdef...

    Install python-dotenv for .env support:
        pip install python-dotenv
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import getpass

# Try to load dotenv for .env file support
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, continue without it

# Import the TinyWeb client
try:
    from tinyweb_client import TinyWebClient, TinyWebError, AuthenticationError
except ImportError:
    print("Error: tinyweb_client.py not found. Please ensure it's in the same directory.")
    sys.exit(1)


class TinyWebCLI:
    """TinyWeb Command Line Interface."""

    def __init__(self):
        self.client = None
        self.load_config()

    def load_config(self):
        """Load configuration from environment variables."""
        try:
            # Get configuration from environment variables
            base_url = os.getenv('TINYWEB_API_URL', 'http://localhost:7070')

            # Parse timeout from environment variable, convert to int if valid
            timeout_str = os.getenv('TINYWEB_API_TIMEOUT', '300')
            try:
                timeout = int(timeout_str)
            except ValueError:
                timeout = 300
                print(f"Warning: Invalid timeout value '{timeout_str}', using default 300")

            # Default values for other parameters
            default_wallet = os.getenv('WALLET_ADDRESS', '')
            default_private_key = os.getenv('PRIVATE_KEY', '')

            self.client = TinyWebClient(base_url=base_url, timeout=timeout)

            # Store default values for convenience
            self.default_wallet = default_wallet
            self.default_private_key = default_private_key

        except Exception as e:
            print(f"Warning: Failed to load config from environment: {e}")
            self.client = TinyWebClient()
            self.default_wallet = ''
            self.default_private_key = ''

    def cmd_config(self, args):
        """Show current configuration."""
        try:
            print("TinyWeb CLI Configuration")
            print("=" * 50)           

            # Client configuration section
            print(f"\nClient Configuration:")
            print(f"Base URL: {self.client.base_url}")
            print(f"Timeout: {self.client.session.timeout}s")

            # Key management section
            print(f"\nKey Management:")
            if self.default_wallet:
                print(f"Wallet Address: {self.default_wallet[:6]}...{self.default_wallet[-4:]}")
            if self.default_private_key:
                print("Private Key: Set (hidden for security)")

        except Exception as e:
            return self.handle_error(e)
        return 0

    def handle_error(self, error: Exception):
        """Handle and format errors nicely."""
        if isinstance(error, AuthenticationError):
            print(f"❌ Authentication Error: {error}")
            print("Please login first using: python3 tinyweb_cli.py login")
        elif isinstance(error, TinyWebError):
            print(f"❌ API Error: {error}")
        else:
            print(f"❌ Error: {error}")
        return 1

    # Authentication Commands

    def cmd_login(self, args):
        """Login with wallet signature."""
        try:
            # Use environment variables as defaults, then command line args, then prompt
            wallet_address = (args.wallet or
                            self.default_wallet or
                            input("Wallet address: ").strip())

            private_key = (args.private_key or
                          self.default_private_key or
                          getpass.getpass("Private key: ").strip())

            invite_code = getattr(args, 'invite_code', None) or (
                input("Invite code (optional): ").strip() or None
            )

            print(f"🔐 Authenticating wallet {wallet_address}...")
            result = self.client.authenticate_wallet(
                wallet_address, private_key, invite_code
            )

            if result.get("success"):
                print("✅ Login successful!")
                user_info = result.get("user", {})
                print(f"Welcome, {user_info.get('nickname', wallet_address)}!")
            else:
                print(f"❌ Login failed: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_status(self, args):
        """Show authentication status."""
        try:
            result = self.client.get_auth_status()

            if result.get("authenticated"):
                user = result.get("user", {})
                print("✅ Authenticated")
                print(f"Wallet: {user.get('wallet_address', 'N/A')}")
                print(f"Nickname: {user.get('nickname', 'N/A')}")
                print(f"Role: {user.get('role', 'user')}")
            else:
                print("❌ Not authenticated")
                print("Please login using: python3 tinyweb_cli.py login")

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_logout(self, args):
        """Logout current user."""
        try:
            result = self.client.logout()
            if result.get("success"):
                print("✅ Logged out successfully")
            else:
                print(f"❌ Logout failed: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_profile(self, args):
        """Update user profile."""
        try:
            nickname = args.nickname or input("New nickname: ").strip()
            result = self.client.update_profile(nickname)

            if result.get("success"):
                print(f"✅ Profile updated successfully")
                print(f"Nickname: {nickname}")
            else:
                print(f"❌ Profile update failed: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    # Invite Code Commands

    def cmd_create_invite(self, args):
        """Create new invite code."""
        try:
            code = args.code or input("Invite code: ").strip()
            max_uses = args.max_uses or int(input("Max uses (0 for unlimited): ").strip() or "1")

            result = self.client.create_invite_code(code, max_uses)

            if result.get("success"):
                print(f"✅ Invite code '{code}' created successfully")
                print(f"Max uses: {max_uses}")
            else:
                print(f"❌ Failed to create invite code: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_list_invites(self, args):
        """List all invite codes."""
        try:
            result = self.client.list_invite_codes()

            if result.get("success"):
                invites = result.get("invite_codes", [])
                if invites:
                    print("📋 Invite Codes:")
                    print("-" * 80)
                    for invite in invites:
                        print(f"Code: {invite.get('code', 'N/A')}")
                        print(f"Max uses: {invite.get('max_uses', 'N/A')}")
                        print(f"Used: {invite.get('used_count', 0)}")
                        print(f"Active: {invite.get('active', 'N/A')}")
                        print("-" * 40)
                else:
                    print("No invite codes found")
            else:
                print(f"❌ Failed to list invite codes: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_validate_invite(self, args):
        """Validate invite code."""
        try:
            code = args.code or input("Invite code to validate: ").strip()
            result = self.client.validate_invite_code(code)

            if result.get("valid"):
                print(f"✅ Invite code '{code}' is valid")
                print(f"Remaining uses: {result.get('remaining_uses', 'N/A')}")
            else:
                print(f"❌ Invite code '{code}' is invalid: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_deactivate_invite(self, args):
        """Deactivate invite code."""
        try:
            code = args.code or input("Invite code to deactivate: ").strip()
            result = self.client.deactivate_invite_code(code)

            if result.get("success"):
                print(f"✅ Invite code '{code}' deactivated successfully")
            else:
                print(f"❌ Failed to deactivate invite code: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    # Data Management Commands

    def cmd_upload(self, args):
        """Upload data file."""
        try:
            file_path = args.file or input("File path: ").strip()

            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                return 1

            print(f"📤 Uploading {file_path}...")
            result = self.client.upload_data_file(file_path)

            if result.get("success"):
                print("✅ File uploaded successfully!")
                print(f"File path: {result.get('file_path', 'N/A')}")
                print(f"File size: {result.get('file_size', 'N/A')} bytes")
            else:
                print(f"❌ Upload failed: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_list_files(self, args):
        """List available data files."""
        try:
            files = self.client.get_data_files()

            if files:
                print("📁 Available Data Files:")
                print("-" * 80)
                for file_info in files:
                    print(f"Name: {file_info.get('name', 'N/A')}")
                    print(f"Path: {file_info.get('path', 'N/A')}")
                    print(f"Size: {file_info.get('size', 'N/A')} bytes")
                    print(f"Modified: {file_info.get('modified', 'N/A')}")
                    print("-" * 40)
            else:
                print("No data files found")

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_load_data(self, args):
        """Load and analyze data file."""
        try:
            file_path = args.file or input("File path: ").strip()

            print(f"📊 Loading data file {file_path}...")
            result = self.client.load_data_file(file_path)

            if result.get("success"):
                print("✅ Data file loaded successfully!")
                print(f"Columns: {', '.join(result.get('columns', []))}")
                print(f"Rows: {result.get('rows', 'N/A')}")
                print(f"Date range: {result.get('date_range', 'N/A')}")
            else:
                print(f"❌ Failed to load data file: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    # Prediction Commands

    def cmd_predict(self, args):
        """Run Kronos model prediction."""
        try:
            file_path = args.file or input("File path: ").strip()
            lookback = args.lookback or 400
            pred_len = args.pred_len or 120
            temperature = args.temperature or 1.0
            top_p = args.top_p or 0.9
            sample_count = args.sample_count or 1
            start_date = getattr(args, 'start_date', None)

            print(f"🔮 Running prediction on {file_path}...")
            print(f"Parameters: lookback={lookback}, pred_len={pred_len}")

            result = self.client.predict(
                file_path=file_path,
                lookback=lookback,
                pred_len=pred_len,
                temperature=temperature,
                top_p=top_p,
                sample_count=sample_count,
                start_date=start_date
            )

            if result.get("success"):
                print("✅ Prediction completed successfully!")
                print(f"Prediction ID: {result.get('prediction_id', 'N/A')}")
                print(f"Chart data: {len(result.get('chart_data', []))} points")

                # Save results if output file specified
                if hasattr(args, 'output') and args.output:
                    self.client.save_results_to_file(result, args.output)
                    print(f"Results saved to: {args.output}")
            else:
                print(f"❌ Prediction failed: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_predict_all(self, args):
        """Run simplified all-in-one prediction."""
        try:
            file_path = args.file or input("File path: ").strip()
            lookback = args.lookback or 400
            pred_len = args.pred_len or 120

            print(f"🚀 Running all-in-one prediction on {file_path}...")

            result = self.client.predict_all_in_one(
                file_path=file_path,
                lookback=lookback,
                pred_len=pred_len
            )

            if result.get("success"):
                print("✅ All-in-one prediction completed successfully!")
                print(f"Results file: {result.get('results_file', 'N/A')}")
            else:
                print(f"❌ Prediction failed: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    # Model Management Commands

    def cmd_list_models(self, args):
        """List available models."""
        try:
            result = self.client.get_available_models()

            if result.get("success"):
                models = result.get("models", {})
                print("🤖 Available Models:")
                print("-" * 80)
                for model_key, model_info in models.items():
                    print(f"Model: {model_key}")
                    print(f"Name: {model_info.get('name', 'N/A')}")
                    print(f"Description: {model_info.get('description', 'N/A')}")
                    print(f"Loaded: {model_info.get('loaded', 'N/A')}")
                    print("-" * 40)
            else:
                print(f"❌ Failed to list models: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_model_status(self, args):
        """Show current model status."""
        try:
            result = self.client.get_model_status()

            if result.get("success"):
                print("📊 Model Status:")
                print(f"Current model: {result.get('current_model', 'N/A')}")
                print(f"Device: {result.get('device', 'N/A')}")
                print(f"Status: {result.get('status', 'N/A')}")
                print(f"Memory usage: {result.get('memory_usage', 'N/A')}")
            else:
                print(f"❌ Failed to get model status: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def cmd_load_model(self, args):
        """Load or change model."""
        try:
            model_key = args.model or input("Model key (kronos-mini/kronos-small/kronos-base): ").strip()
            device = args.device or input("Device (cpu/cuda/mps): ").strip() or "cpu"

            print(f"🔄 Loading model {model_key} on {device}...")
            result = self.client.load_model(model_key, device)

            if result.get("success"):
                print(f"✅ Model {model_key} loaded successfully!")
                print(f"Device: {device}")
                print(f"Status: {result.get('status', 'N/A')}")
            else:
                print(f"❌ Failed to load model: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            return self.handle_error(e)
        return 0

    def run(self):
        """Main CLI entry point."""
        parser = argparse.ArgumentParser(
            description="TinyWeb CLI - Command line interface for TinyWeb API",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python3 tinyweb_cli.py login --wallet 0x123... --private-key your_key
  python3 tinyweb_cli.py upload --file data.csv
  python3 tinyweb_cli.py predict --file data.csv --lookback 400 --pred-len 120
  python3 tinyweb_cli.py create-invite --code TEST123 --max-uses 5
            """
        )

        parser.add_argument(
            '--url',
            default=os.getenv('TINYWEB_API_URL', 'http://localhost:7070'),
            help='TinyWeb API base URL (default: from TINYWEB_API_URL or http://localhost:7070)'
        )

        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Add config command
        config_parser = subparsers.add_parser('config', help='Show current configuration')
        config_parser.add_argument('--show', action='store_true', help='Show configuration details')

        # Authentication commands
        login_parser = subparsers.add_parser('login', help='Authenticate with wallet signature')
        login_parser.add_argument('--wallet', help='Ethereum wallet address (or use DEFAULT_WALLET_ADDRESS env var)')
        login_parser.add_argument('--private-key', help='Private key for signing (or use PRIVATE_KEY env var)')
        login_parser.add_argument('--invite-code', help='Invite code for new users')

        subparsers.add_parser('status', help='Show authentication status')
        subparsers.add_parser('logout', help='Logout current user')

        profile_parser = subparsers.add_parser('profile', help='Update user profile')
        profile_parser.add_argument('--nickname', help='New nickname')

        # Invite code commands
        create_invite_parser = subparsers.add_parser('create-invite', help='Create new invite code (admin only)')
        create_invite_parser.add_argument('--code', help='Invite code string')
        create_invite_parser.add_argument('--max-uses', type=int, default=1, help='Maximum uses (0 for unlimited)')

        subparsers.add_parser('list-invites', help='List all invite codes (admin only)')

        validate_invite_parser = subparsers.add_parser('validate-invite', help='Validate invite code')
        validate_invite_parser.add_argument('--code', help='Invite code to validate')

        deactivate_invite_parser = subparsers.add_parser('deactivate-invite', help='Deactivate invite code (admin only)')
        deactivate_invite_parser.add_argument('--code', help='Invite code to deactivate')

        # Data management commands
        upload_parser = subparsers.add_parser('upload', help='Upload data file')
        upload_parser.add_argument('--file', required=True, help='Path to data file (CSV/Feather)')

        subparsers.add_parser('list-files', help='List available data files')

        load_data_parser = subparsers.add_parser('load-data', help='Load and analyze data file')
        load_data_parser.add_argument('--file', required=True, help='Path to data file')

        # Prediction commands
        predict_parser = subparsers.add_parser('predict', help='Run Kronos model prediction')
        predict_parser.add_argument('--file', required=True, help='Path to data file')
        predict_parser.add_argument('--lookback', type=int, default=400, help='Lookback period (default: 400)')
        predict_parser.add_argument('--pred-len', type=int, default=120, help='Prediction length (default: 120)')
        predict_parser.add_argument('--temperature', type=float, default=1.0, help='Temperature parameter (default: 1.0)')
        predict_parser.add_argument('--top-p', type=float, default=0.9, help='Top-p sampling parameter (default: 0.9)')
        predict_parser.add_argument('--sample-count', type=int, default=1, help='Number of samples (default: 1)')
        predict_parser.add_argument('--start-date', help='Start date for prediction (ISO format)')
        predict_parser.add_argument('--output', help='Save results to file')

        predict_all_parser = subparsers.add_parser('predict-all', help='Run simplified all-in-one prediction')
        predict_all_parser.add_argument('--file', required=True, help='Path to data file')
        predict_all_parser.add_argument('--lookback', type=int, default=400, help='Lookback period (default: 400)')
        predict_all_parser.add_argument('--pred-len', type=int, default=120, help='Prediction length (default: 120)')

        # Model management commands
        subparsers.add_parser('list-models', help='List available models')
        subparsers.add_parser('model-status', help='Show current model status')

        load_model_parser = subparsers.add_parser('load-model', help='Load or change model (admin only)')
        load_model_parser.add_argument('--model', help='Model key (kronos-mini/kronos-small/kronos-base)')
        load_model_parser.add_argument('--device', default='cpu', help='Device (cpu/cuda/mps, default: cpu)')

        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            return 1

        # Update client base URL if provided
        if args.url != self.client.base_url:
            self.client.base_url = args.url.rstrip('/')

        # Map commands to methods
        command_map = {
            'config': self.cmd_config,
            'login': self.cmd_login,
            'status': self.cmd_status,
            'logout': self.cmd_logout,
            'profile': self.cmd_profile,
            'create-invite': self.cmd_create_invite,
            'list-invites': self.cmd_list_invites,
            'validate-invite': self.cmd_validate_invite,
            'deactivate-invite': self.cmd_deactivate_invite,
            'upload': self.cmd_upload,
            'list-files': self.cmd_list_files,
            'load-data': self.cmd_load_data,
            'predict': self.cmd_predict,
            'predict-all': self.cmd_predict_all,
            'list-models': self.cmd_list_models,
            'model-status': self.cmd_model_status,
            'load-model': self.cmd_load_model,
        }

        if args.command in command_map:
            return command_map[args.command](args)
        else:
            print(f"❌ Unknown command: {args.command}")
            parser.print_help()
            return 1


def main():
    """Main entry point."""
    cli = TinyWebCLI()
    try:
        exit_code = cli.run()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()