import asyncio
import datetime
import logging
from typing import Optional, List, Any, Dict

import aiohttp


class TransactionFeeTracker:
    def __init__(self, api_key: str, logger: Optional[logging.Logger] = None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._api_key = api_key
        self._transaction_hash_to_fee_map = {}
        self._latest_block_seen = 0
        self._url = 'https://api.etherscan.io/api'
        self._logger.info(f"TransactionFeeTracker created with url={self._url}")

    async def _make_get_request(self, params: Dict[Any, Any]) -> Optional[Dict[Any, Any]]:
        print("AM BEING CALLED")
        self._logger.info(f"Making Request: params={params}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self._url, params=params) as response:
                    return await response.json()
        except aiohttp.CLientError as e:
            self._logger.error(f"Unable to get data for request_params={params}")

    def _get_latest_block_params(self) -> Dict[str, Any]:
        return {
            'module': 'block',
            'action': 'getblocknobytime',
            'timestamp': datetime.datetime.utcnow().timestamp(),
            'closest': 'after'
        }

    def _get_historical_transactions_params(self) -> Dict[str, Any]:
        return {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'address': '0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640',
            'offset': 0,
            'page': 1,
            'sort': 'asc',
            'startblock': self._latest_block_seen,
            'apikey': self._api_key
        }

    async def get_latest_block(self):
        params = self._get_latest_block_params()
        response = await self._make_get_request(params)
        if response is None or not isinstance(response, dict) or 'result' not in response:
            return
        latest_block = response['result']
        self._logger.info(f"Latest block: {latest_block}")
        return latest_block

    async def get_historical_transactions(self):
        params = self._get_historical_transactions_params()
        response = await self._make_get_request(params)
        if response is None or not isinstance(response, dict) or 'result' not in response:
            return
        transactions = response['result']
        return transactions

    def _parse_historical_transactions(self, transactions: List[Dict[Any, Any]]):
        for transaction in transactions:
            txn_hash = transaction['hash']
            txn_fee = transaction['gasPrice'] * transaction['gasUsed'] / 10 ** 18
            if txn_hash is None:
                raise Exception('Transaction hash found to be None')
            self._transaction_hash_to_fee_map[txn_hash] = txn_fee

    async def poll_transactions(self):
        latest_block = await self.get_latest_block()
        if latest_block > self._latest_block_seen:
            self._logger.info(
                f"Polling transactions... latest_block={latest_block}, latest_block_seen={self._latest_block_seen}")
            historical_transactions = await self.get_historical_transactions()
            self._parse_historical_transactions(historical_transactions)
            self._latest_block_seen = latest_block

    async def periodic_poll_transactions(self):
        self._logger.info('Starting Periodic polling of transactions')
        while True:
            try:
                await self.poll_transactions()
            except Exception as e:
                self._logger.error(f"Unable to poll transactions due to {e}")
            await asyncio.sleep(1)

    def coros(self):
        return [self.periodic_poll_transactions()]

    def get_transaction_fee(self, transaction_hash: str) -> Optional[float]:
        if self._latest_block_seen == 0 or transaction_hash not in self._transaction_hash_to_fee_map:
            return
        return self._transaction_hash_to_fee_map[transaction_hash]
