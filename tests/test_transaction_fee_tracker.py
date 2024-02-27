from typing import Dict, Any, Optional, List
from unittest.mock import AsyncMock, patch

import pytest
from src.transaction_fee_tracker import TransactionFeeTracker


class MockTransactionFeeTracker(TransactionFeeTracker):
    _responses = []
    _num_api_calls = 0

    def set_request_responses(self, responses: List[Any]):
        self._responses = responses

    async def _make_get_request(self, params: Dict[Any, Any]) -> Optional[Dict[Any, Any]]:
        ret = self._responses[self._num_api_calls]
        self._num_api_calls += 1
        return ret


class TestTransactionFeeTracker:

    def test_get_transaction_fee_empty(self):
        transaction_fee_tracker = MockTransactionFeeTracker('fake_api_key')
        actual_txn_fee = transaction_fee_tracker.get_transaction_fee('0x12345')
        assert actual_txn_fee is None

    @pytest.mark.parametrize("gas_price, gas_used, txn_hash", [(None, 10**18, '0x12345'), (1, None, '12345'), (1, -10**18, None)])
    def test_parse_historical_transactions_with_bad_messages(self, gas_price, gas_used, txn_hash):
        transaction_fee_tracker = MockTransactionFeeTracker('fake_api_key')
        with pytest.raises(Exception):
            transaction_fee_tracker._parse_historical_transactions(
                [{'gasPrice': gas_price, 'gasUsed': gas_used, 'hash': txn_hash}])

    @pytest.mark.asyncio
    async def test_poll_transactions_with_no_new_transactions(self):
        transaction_fee_tracker = MockTransactionFeeTracker('fake_api_key')
        transaction_fee_tracker.set_request_responses([
            {'result': 100},
            {'result': []}
        ])
        await transaction_fee_tracker.poll_transactions()
        assert transaction_fee_tracker._num_api_calls == 2

    @pytest.mark.asyncio
    async def test_poll_transactions_with_no_new_blocks(self):
        transaction_fee_tracker = MockTransactionFeeTracker('fake_api_key')
        transaction_fee_tracker._latest_block_seen = 100
        transaction_fee_tracker.set_request_responses([
            {'result': 100},
            {'result': []}
        ])
        await transaction_fee_tracker.poll_transactions()
        assert transaction_fee_tracker._num_api_calls == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("gas_price, gas_used, txn_hash, expected_txn_fee",
                             [(100, 10**18, '0x12345', 100),
                              (-1, 10**18, '12345', -1),
                              (1, -10**18, 'abcde', -1)])
    async def test_get_transaction_fee(self, gas_price, gas_used, txn_hash, expected_txn_fee):
        transaction_fee_tracker = MockTransactionFeeTracker('fake_api_key')
        transaction_fee_tracker.set_request_responses([
            {'result': 100},
            {'result': [{'gasPrice': gas_price, 'gasUsed': gas_used, 'hash': txn_hash}]}
        ])
        await transaction_fee_tracker.poll_transactions()
        assert transaction_fee_tracker._num_api_calls == 2

        actual_txn_fee = transaction_fee_tracker.get_transaction_fee(txn_hash)
        assert actual_txn_fee == expected_txn_fee
        actual_txn_fee = transaction_fee_tracker.get_transaction_fee('wrong_hash')
        assert actual_txn_fee is None
