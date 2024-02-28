import asyncio
import logging
import os

import yaml
from aiohttp import web

from transaction_fee_tracker import TransactionFeeTracker


async def transaction_fee_handler(req: web.Request):
    """
    Handle transaction fee endpoint (GET request). Query param (txn_hash) must be provided.
    :param req: Request object from aiohttp specifying user request
    :return: A web response specifying the results of the request
    """
    txn_hash = req.query.get("txn_hash", None)
    if txn_hash is None:
        return web.json_response({"error": "Missing parameter txn_hash"}, status=400)

    transaction_fee_tracker = req.app["transaction_fee_tracker"]
    txn_fee = transaction_fee_tracker.get_transaction_fee(txn_hash)
    if txn_fee is None:
        return web.json_response(
            {
                "error": f"txn_hash={txn_hash} not found. This is not a valid transaction."
            },
            status=400,
        )
    return web.json_response({"message": txn_fee}, status=200)


async def startup(app: web.Application) -> None:
    """
    Startup coroutine to instantiate a TransactionFeeTracker, run its background tasks, and parse configs.
    :param app: app object from aiohttp
    :return:
    """
    config_file = os.environ.get("CONFIG_FILE")
    if config_file is None:
        raise Exception(f"No config file provided.")
    with open(config_file, "r") as f:
        config = yaml.load(f, Loader=yaml.Loader)

    transaction_fee_tracker = TransactionFeeTracker(config.get("api_key"))
    app["transaction_fee_tracker"] = transaction_fee_tracker
    tasks = []
    for coro in transaction_fee_tracker.coros():
        tasks.append(asyncio.create_task(coro))
    app["background_tasks"] = tasks


async def on_shutdown(app) -> None:
    """
    Shutdown coroutine to kill background tasks
    :param app: app object from aiohttp
    :return:
    """
    app["logger"].info("Shutting down")
    for task in app["background_tasks"]:
        task.cancel()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [ %(name)s ] - %(message)s",
    )
    web_app = web.Application()
    web_app["logger"] = logging.getLogger("HTTP-SERVER")
    web_app.add_routes([web.get("/transaction_fee", transaction_fee_handler)])

    web_app.on_startup.append(startup)
    web_app.on_shutdown.append(on_shutdown)
    web.run_app(web_app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
