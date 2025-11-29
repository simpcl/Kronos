"""
Web3 Wallet Authentication Module
Handles blockchain wallet signature verification and authentication logic
"""
import secrets
import datetime
from typing import Optional, Tuple
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.exceptions import InvalidAddress


class WalletAuth:
    """Wallet authentication class"""
    
    def __init__(self):
        """Initialize authentication module"""
        self.w3 = Web3()
    
    def verify_signature(self, message: str, signature: str, address: str) -> bool:
        """
        Verify Ethereum signature

        Args:
            message: Original message
            signature: Signature (hex string starting with 0x)
            address: Wallet address

        Returns:
            Whether verification is successful
        """
        try:
            # Check address format
            if not self.w3.is_address(address):
                return False
            
            # Encode message (EIP-191 standard)
            message_hash = encode_defunct(text=message)
            
            # Recover signer address
            recovered_address = self.w3.eth.account.recover_message(
                message_hash, 
                signature=signature
            )
            
            # Compare addresses (case insensitive)
            return recovered_address.lower() == address.lower()
            
        except (ValueError, InvalidAddress) as e:
            print(f"Signature verification error: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error in signature verification: {e}")
            return False
    
    def generate_challenge_message(self, address: str) -> Tuple[str, str]:
        """
        Generate authentication challenge message

        Args:
            address: Wallet address

        Returns:
            (challenge message, nonce) tuple
        """
        timestamp = datetime.datetime.now().isoformat()
        nonce = secrets.token_hex(16)
        
        message = (
            f"Kronos Wallet Authentication\n\n"
            f"Wallet: {address}\n"
            f"Timestamp: {timestamp}\n"
            f"Nonce: {nonce}\n\n"
            f"Please sign this message to authenticate your wallet."
        )
        
        return message, nonce
    
    def validate_address(self, address: str) -> bool:
        """
        Validate wallet address format

        Args:
            address: Wallet address

        Returns:
            Whether address format is valid
        """
        try:
            return self.w3.is_address(address)
        except Exception:
            return False


# Global authentication instance
_auth_instance = None


def get_wallet_auth() -> WalletAuth:
    """
    Get global authentication instance (singleton pattern)

    Returns:
        WalletAuth instance
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = WalletAuth()
    return _auth_instance

