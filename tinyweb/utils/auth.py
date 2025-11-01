"""
Web3 钱包认证模块
处理区块链钱包签名验证和认证逻辑
"""
import secrets
import datetime
from typing import Optional, Tuple
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.exceptions import InvalidAddress


class WalletAuth:
    """钱包认证类"""
    
    def __init__(self):
        """初始化认证模块"""
        self.w3 = Web3()
    
    def verify_signature(self, message: str, signature: str, address: str) -> bool:
        """
        验证以太坊签名
        
        Args:
            message: 原始消息
            signature: 签名（十六进制字符串，0x开头）
            address: 钱包地址
            
        Returns:
            验证是否成功
        """
        try:
            # 检查地址格式
            if not self.w3.is_address(address):
                return False
            
            # 编码消息（EIP-191 标准）
            message_hash = encode_defunct(text=message)
            
            # 恢复签名者地址
            recovered_address = self.w3.eth.account.recover_message(
                message_hash, 
                signature=signature
            )
            
            # 比较地址（不区分大小写）
            return recovered_address.lower() == address.lower()
            
        except (ValueError, InvalidAddress) as e:
            print(f"Signature verification error: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error in signature verification: {e}")
            return False
    
    def generate_challenge_message(self, address: str) -> Tuple[str, str]:
        """
        生成认证挑战消息
        
        Args:
            address: 钱包地址
            
        Returns:
            (挑战消息, nonce) 元组
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
        验证钱包地址格式
        
        Args:
            address: 钱包地址
            
        Returns:
            地址格式是否有效
        """
        try:
            return self.w3.is_address(address)
        except Exception:
            return False


# 全局认证实例
_auth_instance = None


def get_wallet_auth() -> WalletAuth:
    """
    获取全局认证实例（单例模式）
    
    Returns:
        WalletAuth 实例
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = WalletAuth()
    return _auth_instance

