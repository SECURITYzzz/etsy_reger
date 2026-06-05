import asyncio
import json
import random
from typing import Optional, Tuple, Dict, Any

from aiohttp import ClientSession, TCPConnector, ClientResponse, ClientError, ClientConnectionError
import ssl
import certifi
from loguru import logger

from functions import generate_password, create_resource_in_executable_dir
from worker import EtsyRegerWorker
from utils.names import NAMES


class EtsyReger:
    def __init__(
        self,
        proxies: list[str],
        anymessage_api_key: str,
        rucaptcha_api_key: str,
        threads_num: int = 10
    ):
        self.proxies = {proxy: 0 for proxy in proxies}
        self.proxies_queue = asyncio.Queue()
        for proxy in proxies:
            self.proxies_queue.put_nowait(proxy)
        self.proxy_lock = asyncio.Lock()
        self.anymessage_api_key = anymessage_api_key
        self.rucaptcha_api_key = rucaptcha_api_key
        self.threads_num = threads_num
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = TCPConnector(ssl=ssl_context)
        self.client = ClientSession(connector=connector)
        self.accounts_num = 0
        self.accounts_lock = asyncio.Lock()

    async def mainloop(self) -> None:
        threads_num = min(self.threads_num, self.proxies_queue.qsize())
        if threads_num == 0:
            logger.warning("No proxies available")
            return
        logger.info(f"Starting {threads_num} registration threads")
        tasks = [self.register_loop() for _ in range(threads_num)]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def register_loop(self) -> None:
        while True:
            etsy = None
            try:
                mail_data = await self.order_mail()
                if not mail_data:
                    continue
                mail, order_id = mail_data
                logger.info(f"Email purchased: {mail} (order_id: {order_id})")

                password = generate_password()
                first_name = random.choice(NAMES)

                etsy = EtsyRegerWorker(
                    mail=mail,
                    password=password,
                    first_name=first_name,
                    proxies_queue=self.proxies_queue,
                    rucaptcha_api_key=self.rucaptcha_api_key,
                )

                success = await etsy.register_mainloop()
                if not success:
                    continue

                message_data = await self.get_message(order_id)
                if not message_data:
                    continue
                _, confirm_url = message_data
                logger.info(f"Confirmation link received: {confirm_url}")

                confirmed = await etsy.confirm_account(confirm_url)
                if not confirmed:
                    continue
                logger.success(f"Account {mail} confirmed")

                cookies, headers = etsy.get_client_data()
                if not cookies:
                    logger.error(f"Failed to extract cookies for {mail}")
                    continue

                account_data = {
                    "email": mail,
                    "password": password,
                    "cookies": cookies,
                    "headers": headers
                }

                account_filepath = create_resource_in_executable_dir(f"output/{mail}.txt")
                with open(account_filepath, 'w', encoding='utf-8') as file:
                    json.dump(account_data, file, indent=2, ensure_ascii=False)

                cookies_filepath = create_resource_in_executable_dir(f"output_json/{mail}_cookies.json")
                with open(cookies_filepath, 'w', encoding='utf-8') as file:
                    json.dump(cookies, file, indent=2, ensure_ascii=False)

                async with self.accounts_lock:
                    self.accounts_num += 1
                    logger.success(f"Total accounts: {self.accounts_num}")

            except Exception as e:
                logger.error(f"Error in registration loop: {e}")
            finally:
                if etsy is not None:
                    await etsy.close()

    async def order_mail(self) -> Optional[Tuple[str, str]]:
        url = "https://api.anymessage.shop/email/order"
        params = {
            "token": self.anymessage_api_key,
            "site": "https://www.etsy.com",
            "domain": "hotmail"
        }
        resp = await self.fetch(url=url, method="GET", params=params, timeout=30)
        if not resp:
            logger.error("Failed to order email")
            return None

        try:
            resp_json = await resp.json()
        except Exception as e:
            logger.error(f"Invalid JSON in order response: {e}")
            return None

        if resp_json.get('status') == "error":
            logger.error(f"Email order error: {resp_json.get('value')}")
            return None

        email = resp_json.get('email')
        order_id = resp_json.get('id')
        if not email or not order_id:
            logger.error("Missing email or id in response")
            return None
        return email, order_id

    async def get_message(self, email_id: str) -> Optional[Tuple[str, str]]:
        url = "https://api.anymessage.shop/email/getmessage"
        params = {
            "token": self.anymessage_api_key,
            "id": email_id,
            "previes": 0
        }
        max_attempts = 12
        for attempt in range(max_attempts):
            resp = await self.fetch(url=url, method="GET", params=params, timeout=30)
            if not resp:
                logger.warning(f"No response from server, attempt {attempt+1}")
                continue

            try:
                resp_json = await resp.json()
            except Exception:
                logger.warning(f"Invalid JSON response, attempt {attempt+1}")
                continue

            if resp_json.get('status') == "error":
                value = resp_json.get("value")
                if value == "wait message":
                    logger.info(f"Waiting for message for {email_id}, attempt {attempt+1}")
                    await asyncio.sleep(5)
                    continue
                logger.error(f"Get message error for {email_id}: {value}")
                return None

            message = resp_json.get('message')
            value = resp_json.get('value')
            if message and value:
                return message, value
            logger.warning("Incomplete message data")
            return None

        logger.error(f"Failed to get message after {max_attempts} attempts")
        return None

    async def fetch(
        self,
        url: str,
        method: str,
        max_attempts: int = 5,
        timeout: int = 100,
        **kwargs
    ) -> Optional[ClientResponse]:
        proxy = await self.random_proxy()
        if not proxy:
            logger.error("No proxy available for request")
            return None
        proxy_url = 'http://' + proxy

        for attempt in range(max_attempts):
            try:
                async with self.client.request(method, url, proxy=proxy_url, timeout=timeout, **kwargs) as response:
                    status = response.status
                    if status in (200, 201):
                        async with self.proxy_lock:
                            self.proxies[proxy] = 0
                        logger.debug(f"Successful request to {url}: status {status}")
                        return response
                    else:
                        try:
                            body = await response.text()
                        except:
                            body = ""
                        logger.warning(
                            f"Bad response {status} from {url} | proxy: {proxy} | body: {body[:200]}"
                        )
                        return None

            except (asyncio.TimeoutError, ClientConnectionError, ClientError) as e:
                logger.warning(f"Attempt {attempt+1}/{max_attempts} for {url} | proxy: {proxy} | error: {e}")
                await asyncio.sleep(2 ** attempt)
                async with self.proxy_lock:
                    if proxy in self.proxies:
                        self.proxies[proxy] += 1
                        if self.proxies[proxy] >= 3:
                            del self.proxies[proxy]
                            logger.info(f"Proxy {proxy} removed after 3 failures")
                            return None
            except Exception as e:
                logger.error(f"Unexpected error during request to {url}: {e}")
                return None

        logger.error(f"All {max_attempts} attempts failed for {url}")
        return None

    async def random_proxy(self) -> Optional[str]:
        async with self.proxy_lock:
            if not self.proxies:
                logger.warning("Proxy pool is empty")
                return None
            return random.choice(list(self.proxies.keys()))

    async def close(self) -> None:
        if self.client and not self.client.closed:
            await self.client.close()
            logger.info("Client session closed")
