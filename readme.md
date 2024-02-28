# What this Repository contains
This repository stores a service that exposes an endpoint to query for the transaction fee of any
transaction hash involved in the Uniswap V3 USDC/ETH pool (0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640).

After running the code, it should be as simple as querying the `/transaction_fee` endpoint with a txn_hash parameter 
in the header.

# How to run the code
1. Ensure you have Docker installed
2. Update configurations in `/transaction_fees/configs/config.yaml` (add api_key at least)
3. cd into the root directory of this repo, and run `docker-compose up --build`
3. Make queries using curl or postman to `http://localhost:5000/transaction_fee?txn_hash=<txn_hash>`

# How to test
1. Create a virtual environment (or use your global python environment)
2. Ensure `pytest` and `pytest-asyncio` are installed (e.g. `pip install pytest pytest-asyncio`)
3. In the root directory, run `PYTHONPATH=:./src:. pytest`

# Architecture and Comments
## Memory Management vs Speed
- Best way to do this would be to have the data persisted somewhere for O(1) retrieval. Given this is a take home assignment, I did not do up a database as this might take up abit of time. Instead, I loaded everything in a dictionary in RAM.
  - Trade off for my implementation is that the ramp up of data is extremely slow, and will take up too much RAM.
  - Benefit is that queries are completed in O(1)
- If we want to do it without persistent memory like a server hosted DB instance, a better way would be to only load up data required when queried, and store it in a LRU cache.
  - Trade off for this is that each request will have extra latency because it will have to first get the block number, and then make another query for the fees. This is at least 2 network calls.
  - Benefit is that we do not wait too long
## Server Implementation
- A simple server is sufficient, as there is minimal CPU computations here. If we expect high loads, we would implement a queue and load balance the work across multiple instances
