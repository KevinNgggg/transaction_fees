import asyncio
import bisect
import datetime
import logging
from typing import Optional, List, Any, Dict, Tuple

import aiohttp


class TransactionFeeTracker:
    """
    Main class for managing transaction fees and storing them in a dictionary
    """

    def __init__(self, api_key: str, logger: Optional[logging.Logger] = None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._api_key = api_key
        self._transaction_hash_to_fee_map = {}
        self._latest_block_seen = 0
        self._latest_price = None
        self._latest_price_last_updated = None
        self._url = "https://api.etherscan.io/api"
        self._binance_url = "https://api.binance.com/api/v3/klines"
        self._logger.info(
            f"TransactionFeeTracker created with url={self._url} binance_url={self._binance_url}"
        )

    async def _make_get_request(
        self, url, params: Dict[Any, Any]
    ) -> Optional[Dict[Any, Any]]:
        """
        Function for making GET requests, given a URL and some params (which can be empty dictionary)
        :param url: URL to send the request
        :param params: params to pass to the query
        :return: Return value of the query
        """
        self._logger.info(f"Making Request: params={params}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    return await response.json()
        except aiohttp.CLientError as e:
            self._logger.error(
                f"Unable to get data for url={url} request_params={params}, error={e}"
            )
        except Exception as e:
            self._logger.error(f"Error {e}")

    def _get_latest_block_params(self) -> Dict[str, Any]:
        """
        Hardcoded and fixed params for getting latest blocks
        :return:
        """
        return {
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": str(int(datetime.datetime.utcnow().timestamp())),
            "closest": "before",
        }

    def _get_historical_transactions_params(
        self, start_block: int, end_block: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Hardcoded and fixed params for getting historical transactions
        :param start_block: block number to start searching
        :param end_block: block number to stop searching
        :return:
        """
        ret = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
            "offset": 0,
            "page": 1,
            "sort": "asc",
            "startblock": start_block,
            "apikey": self._api_key,
        }
        if end_block is not None:
            ret["endblock"] = end_block
        return ret

    def _get_binance_pricing_params(
        self, start_time: datetime.datetime, end_time: datetime.datetime
    ):
        """
        Hardcoded and fixed params for getting binance prices. We get daily prices only
        :param start_time: start time to get prices
        :param end_time: end time to get prices
        :return:
        """
        return {
            "symbol": "ETHUSDT",
            "interval": "1d",
            "startTime": str(int(start_time.timestamp() * 1000)),
            "endTime": str(int(end_time.timestamp() * 1000)),
            "limit": 1000,
        }

    async def get_latest_block(self) -> Optional[int]:
        """
        Function to get the latest block
        :return: integer of latest block or None if query failed
        """
        params = self._get_latest_block_params()
        response = await self._make_get_request(self._url, params)
        if (
            response is None
            or not isinstance(response, dict)
            or "result" not in response
            or response["result"] is None
        ):
            return
        self._logger.info(f"Returned latest block message: {response}")
        latest_block = int(response["result"])
        self._logger.info(f"Latest block: {latest_block}")
        return latest_block

    async def get_historical_transactions(
        self, up_until_block: Optional[int] = None
    ) -> Optional[List[Any]]:
        """
        Function to get historical transactions up until a block (for uniswap v3 USDC/ETH transactions)
        :param up_until_block: which block we want to run till
        :return: A list of transactions
        """
        params = self._get_historical_transactions_params(
            self._latest_block_seen, up_until_block
        )
        response = await self._make_get_request(self._url, params)
        if (
            response is None
            or not isinstance(response, dict)
            or "result" not in response
        ):
            return
        transactions = response["result"]
        return transactions

    def _parse_historical_transactions(self, transactions: List[Dict[Any, Any]]):
        """
        Function to parse a list of transactions and record the fees of the transaction
        :param transactions: list of transactions taken from get_historical_transactions
        :return: None
        """
        for transaction in transactions:
            if transaction["hash"] is None:
                raise Exception("Transaction hash found to be None")
            txn_hash = str(transaction["hash"]).lower()
            gas_fee = (
                int(transaction["gasPrice"]) * int(transaction["gasUsed"]) / 10**18
            )
            if datetime.datetime.fromtimestamp(
                int(transaction["timeStamp"])
            ) - self._latest_price_last_updated > datetime.timedelta(days=1):
                raise Exception("Stale ETH price")
            txn_fee = gas_fee * self._latest_price
            self._transaction_hash_to_fee_map[txn_hash] = txn_fee

    async def poll_transactions(self):
        """
        Function to poll transactions. Main call function in main loop
        :return: None
        """
        latest_block = await self.get_latest_block()
        if latest_block is None:
            self._logger.error(f"Could not get latest block")
            return
        if latest_block > self._latest_block_seen:
            self._logger.info(
                f"Polling transactions... latest_block={latest_block}, latest_block_seen={self._latest_block_seen}"
            )
            historical_transactions = await self.get_historical_transactions(
                latest_block
            )
            self._parse_historical_transactions(historical_transactions)
            self._latest_block_seen = latest_block

    async def startup_polling(self):
        """
        Function to start up the application. Backfills data (with roughly assumed rate limit)
        :return: None
        """
        self._logger.info("Startup Polling")
        latest_block = await self.get_latest_block()
        eth_prices = await self.get_eth_prices(
            datetime.datetime(2021, 5, 1), datetime.datetime.utcnow()
        )
        while self._latest_block_seen < latest_block:
            historical_transactions = await self.get_historical_transactions()
            for transaction in historical_transactions:
                txn_hash = str(transaction["hash"]).lower()
                gas_fee = (
                    int(transaction["gasPrice"]) * int(transaction["gasUsed"]) / 10**18
                )
                timestamp = int(transaction["timeStamp"]) * 1000
                idx = bisect.bisect_left(eth_prices, (timestamp, -1))
                price = eth_prices[idx][1]
                self._transaction_hash_to_fee_map[txn_hash] = gas_fee * price
            self._latest_block_seen = int(historical_transactions[-1]["blockNumber"])
            await asyncio.sleep(1)  # To account for poor rate limits
        self._latest_price = eth_prices[-1][1]
        self._latest_price_last_updated = datetime.datetime.fromtimestamp(
            int(eth_prices[-1][0] / 1000)
        )

    async def get_eth_prices(
        self, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> List[Tuple[int, float]]:
        """
        Function to get ETH prices from start time to end time (daily data)
        :param start_time: start time of prices
        :param end_time: end time of prices
        :return: list of tuples (timestamp, price)
        """
        ret_candles = []
        cur_time = start_time
        while cur_time < end_time:
            cur_end_time = min(end_time, cur_time + datetime.timedelta(days=990))
            binance_params = self._get_binance_pricing_params(cur_time, cur_end_time)
            binance_prices = await self._make_get_request(
                self._binance_url, binance_params
            )
            binance_prices = [
                (prices[0], float(prices[1])) for prices in binance_prices
            ]
            ret_candles.extend(binance_prices)
            cur_time = cur_end_time + datetime.timedelta(days=1)
        return ret_candles

    async def periodic_poll_transactions(self):
        """
        Main loop for polling transaction. Run this coroutine when using this class
        :return:
        """
        self._logger.info("Starting Periodic polling of transactions")
        while True:
            try:
                await self.poll_transactions()
            except Exception as e:
                self._logger.error(f"Unable to poll transactions due to {e}")
            await asyncio.sleep(10)

    async def periodic_poll_eth_prices(self):
        """
        Main loop for polling ETH prices. Run this coroutine when using this class
        :return:
        """
        self._logger.info("Starting Periodic polling of ETH prices")
        while True:
            cur_timestamp = datetime.datetime.utcnow()
            try:
                if (
                    cur_timestamp
                    > self._latest_price_last_updated + datetime.timedelta(days=1)
                ):
                    eth_prices = await self.get_eth_prices(
                        start_time=self._latest_price_last_updated,
                        end_time=cur_timestamp,
                    )
                    self._latest_price = eth_prices[-1][1]
                    self._latest_price_last_updated = cur_timestamp.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
            except Exception as e:
                self._logger.error(f"Unable to get ETH prices due to {e}")

            target = datetime.datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + datetime.timedelta(days=1)
            sleep_duration = (target - cur_timestamp).seconds + 1
            await asyncio.sleep(sleep_duration)

    def coros(self):
        """
        List of coroutines to run.
        :return:
        """
        return [self.periodic_poll_transactions(), self.periodic_poll_eth_prices()]

    def get_transaction_fee(self, transaction_hash: str) -> Optional[float]:
        """
        Main exposed function for application to use to query for transaction fee of a transaction hash
        :param transaction_hash: transaction hash for query
        :return: Transaction fee. none if does not exist
        """
        if self._latest_block_seen == 0 or transaction_hash is None:
            return
        transaction_hash = transaction_hash.lower()
        return self._transaction_hash_to_fee_map.get(transaction_hash)
