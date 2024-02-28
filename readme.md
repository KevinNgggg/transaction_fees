# What this Repository contains
This repository stores a service that exposes an endpoint to query for the transaction fee of any
transaction hash involved in the Uniswap V3 USDC/ETH pool (0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640).

After running the code, it should be as simple as querying the `/transaction_fee` endpoint with a txn_hash parameter 
in the header.

# How to run the code
1. Ensure you have Docker installed
2. cd into the root directory of this repo, and run `docker-compose up --build`
3. Make queries using curl or postman to `http://localhost:5000/transaction_fee?txn_hash=<txn_hash>`

# How to test
1. Create a virtual environment (or use your global python environment)
2. Ensure `pytest` and `pytest-asyncio` are installed (e.g. `pip install pytest pytest-asyncio`)
3. In the root directory, run `PYTHONPATH=:./src:. pytest`
