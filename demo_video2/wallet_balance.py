"""Print the service wallet ADDRESS and Sepolia balance (never the key or the RPC URL).
Run with the backend venv from the repo root:  PYTHONPATH=backend backend/.venv/Scripts/python.exe demo_video2/wallet_balance.py
"""
from web3 import Web3

from app.core.config import get_settings

s = get_settings()
w3 = Web3(Web3.HTTPProvider(s.SEPOLIA_RPC_URL, request_kwargs={"timeout": 20}))
acct = w3.eth.account.from_key(s.SERVICE_WALLET_PRIVATE_KEY)
print(f"chain_id={w3.eth.chain_id} address={acct.address} balance_eth={w3.from_wei(w3.eth.get_balance(acct.address), 'ether')}")
