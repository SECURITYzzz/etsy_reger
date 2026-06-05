import json
import random
import asyncio
import uuid
import re
from typing import Dict, Optional, Tuple, List, Any
from urllib.parse import urlencode

from aiohttp import ClientSession, ClientConnectionError
from loguru import logger
from twocaptcha import TwoCaptcha
from bs4 import BeautifulSoup

from fingerprint import FingerprintEmulator
from utils.headers import *


class EtsyRegerWorker:
    def __init__(
        self,
        mail: str,
        password: str,
        first_name: str,
        proxies_queue: asyncio.Queue,
        rucaptcha_api_key: str
    ):
        self.mail = mail
        self.password = password
        self.first_name = first_name
        self.proxies = proxies_queue
        self.proxy: Optional[str] = None
        self.proxy_alive = True
        self.proxy_lock = asyncio.Lock()
        self.rucaptcha_api_key = rucaptcha_api_key
        self.solver = TwoCaptcha(rucaptcha_api_key)
        self.fingerprint_emulator: Optional[FingerprintEmulator] = None
        self.headers: Dict[str, str] = {}
        self.datadome_api_key: Optional[str] = None
        self.go_server_url = "http://localhost:8080/fetch"
        self.session_id: Optional[str] = None
        self.session_cookies: Dict[str, str] = {}
        self.client: Optional[ClientSession] = None
        logger.info(f"Initialized worker for {self.mail}")

    async def register_mainloop(self) -> bool:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Registration {self.mail} attempt {attempt}/{max_attempts}")
            try:
                if not await self.new_session():
                    continue

                main_data = await self.process_main_page()
                if not main_data:
                    continue
                sitekey, page_guid, csrf_nonce, datadome_api_key = main_data

                ua = await self.parse_ua()
                if not ua:
                    continue

                if not await self.fetch_tags_js_get():
                    continue

                self.datadome_api_key = datadome_api_key
                datadome_cookie = await self.generate_datadome_cookies(self.datadome_api_key)
                if not datadome_cookie:
                    continue

                recaptcha_token = await self.solve_recaptcha_enterprise(
                    sitekey=sitekey,
                    url="https://www.etsy.com/",
                    score=True
                )
                if not recaptcha_token:
                    continue

                result = await self.register(
                    enterprise_recaptcha_token=recaptcha_token,
                    csrf_nonce=csrf_nonce,
                    page_guid=page_guid,
                    enterprise_recaptcha_token_key_type="score"
                )
                if isinstance(result, dict) and result.get("status") == 200:
                    logger.success(f"Account {self.mail} registered successfully")
                    return True
                elif result is False:
                    logger.error(f"Registration {self.mail} failed with permanent error")
                    return False

            except Exception as e:
                logger.error(f"Unexpected error in register_mainloop for {self.mail}: {e}")

        logger.error(f"Failed to register {self.mail} after {max_attempts} attempts")
        return False

    def _initialize_fingerprint(self) -> None:
        locale, timezone = "en-US", "America/New_York"
        self.fingerprint_emulator = FingerprintEmulator(locale=locale, timezone=timezone)

    def _update_cookies(self, cookies: Dict[str, str]) -> None:
        self.session_cookies.update(cookies)

    def _get_cookie_header(self) -> str:
        if not self.session_cookies:
            return ""
        cookie_order = ["uaid", "user_prefs", "fve", "utm_lps", "last_browse_page", "_fbp", "exp_ebid", "datadome", "ua"]
        return "; ".join(f"{k}={self.session_cookies[k]}" for k in cookie_order if k in self.session_cookies)

    async def parse_ua(self) -> Optional[str]:
        resp = await self.fetch_index()
        if not resp:
            return None
        text = resp.get("text", "")
        if not text:
            logger.warning(f"Empty index.js response for {self.mail}")
            return None

        match = re.search(r'"ua=([^";]+)', text)
        if not match:
            logger.error(f"Could not find ua cookie in index.js for {self.mail}")
            return None

        ua = match.group(1)
        self.session_cookies['ua'] = ua
        return ua

    async def fetch_index(self) -> Optional[Dict[str, Any]]:
        url = "https://www.etsy.com/ac/evergreenVendor/js/en-US/app-shell/globals/index.b1cab868a7d612338168.js"
        headers = self._generate_headers(UA_HEADERS)
        logger.debug(f"Fetching index.js for {self.mail}")
        await asyncio.sleep(random.uniform(1, 3))
        return await self.fetch(url=url, method="GET", headers=headers)

    async def fetch_tags_js_get(self) -> Optional[Dict[str, Any]]:
        url = "https://www.etsy.com/include/tags.js"
        headers = self._generate_headers(TAGS_GET_HEADERS)
        logger.debug(f"Fetching tags.js (GET) for {self.mail}")
        await asyncio.sleep(random.uniform(1, 3))
        return await self.fetch(url=url, method="GET", headers=headers)

    async def fetch_tags_js(self, datadome_api_key: str) -> Optional[Dict[str, Any]]:
        url = "https://www.etsy.com/include/tags.js"
        headers = self._generate_headers(TAGS_POST_HEADERS)
        cid = self.session_cookies.get("datadome", "")
        payload = {
            "jsData": json.dumps(self.fingerprint_emulator.get_js_data()),
            "eventCounters": json.dumps(self.fingerprint_emulator.get_event_counters()),
            "jsType": "ch",
            "cid": cid,
            "ddk": datadome_api_key,
            "Referer": "https://www.etsy.com/",
            "request": "%2F",
            "responsePage": "origin",
            "ddv": "4.46.0",
        }
        logger.debug(f"Fetching tags.js (POST) for {self.mail}")
        await asyncio.sleep(random.uniform(1, 3))
        return await self.fetch(url=url, method="POST", headers=headers, data=payload)

    async def process_main_page(self) -> Optional[Tuple[str, str, str, str]]:
        url = "https://www.etsy.com/"
        headers = self._generate_headers(PAGE_HEADERS)
        logger.debug(f"Loading main page for {self.mail}")
        await asyncio.sleep(random.uniform(1, 3))
        resp = await self.fetch(url=url, method="GET", headers=headers)
        if not resp:
            logger.error(f"Failed to load main page for {self.mail}")
            return None

        text = resp.get("text", "")
        if not text:
            logger.warning(f"Empty main page response for {self.mail}")
            return None

        sitekey_match = re.search(r'data-sitekey="([^"]+)"', text)
        page_guid_match = re.search(r'"page_guid":"([^"]+)"', text)
        csrf_nonce_match = re.search(r'"csrf_nonce":"([^"]+)"', text)
        datadome_key_match = re.search(r'"https://www\.etsy\.com/include/tags\.js", "([^"]+)"', text)

        if not all([sitekey_match, page_guid_match, csrf_nonce_match, datadome_key_match]):
            logger.error(f"Missing required data on main page for {self.mail}")
            return None

        sitekey = sitekey_match.group(1)
        page_guid = page_guid_match.group(1)
        csrf_nonce = csrf_nonce_match.group(1)
        datadome_api_key = datadome_key_match.group(1)

        logger.info(f"Main page processed for {self.mail}")
        return sitekey, page_guid, csrf_nonce, datadome_api_key

    async def generate_datadome_cookies(self, datadome_api_key: str) -> Optional[str]:
        logger.debug(f"Generating DataDome cookies for {self.mail}")
        resp = await self.fetch_tags_js(datadome_api_key)
        if not resp:
            logger.error(f"No response from tags.js for {self.mail}")
            return None

        try:
            cookie_str = resp["json"].get("cookie", "")
            if not cookie_str:
                logger.error(f"No cookie field in tags.js response for {self.mail}")
                return None
            datadome_value = cookie_str.split('=')[1].split(';')[0]
        except (KeyError, IndexError, AttributeError):
            logger.error(f"Malformed tags.js response for {self.mail}: {resp.get('text', '')[:200]}")
            return None

        self._update_cookies({"datadome": datadome_value})
        logger.info(f"DataDome cookie generated for {self.mail}: {datadome_value}")
        return datadome_value

    async def change_proxy(self) -> None:
        async with self.proxy_lock:
            if self.proxies.empty():
                self.proxy = None
                self.proxy_alive = False
                logger.warning(f"No proxies left for {self.mail}")
                return
            self.proxy = await self.proxies.get()
            self.proxy_alive = True
            logger.info(f"Switched to proxy {self.proxy} for {self.mail}")

    async def confirm_account(self, confirm_url: str) -> bool:
        headers = self._generate_headers(PAGE_HEADERS)
        resp = await self.fetch(url=confirm_url, method="GET", headers=headers)
        if resp and resp.get("status") == 200:
            logger.info(f"Account {self.mail} confirmed")
            return True
        logger.error(f"Failed to confirm account {self.mail}")
        return False

    def get_cookies(self, domains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        domains = domains or ["www.etsy.com", "etsy.com"]
        cookies_list = []
        for key, value in self.session_cookies.items():
            cookie = {
                "name": key,
                "value": value,
                "domain": ".etsy.com",
                "path": "/",
                "expires": -1,
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax"
            }
            if cookie["domain"] in domains:
                cookies_list.append(cookie)
        logger.debug(f"Extracted {len(cookies_list)} cookies for {self.mail}")
        return cookies_list

    def get_client_data(self) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        cookies = self.get_cookies()
        headers = self.fingerprint_emulator.generate_base_headers()
        cookie_header = self._get_cookie_header()
        if cookie_header:
            headers["Cookie"] = cookie_header
        return cookies, headers

    async def solve_recaptcha_enterprise(self, sitekey: str, url: str, score: bool = True) -> Optional[str]:
        version = 'v3' if score else 'v2'
        invisible = 1 if score else 0
        action = 'public_email_subscribe' if score else 'register'
        logger.debug(f"Solving reCAPTCHA for {self.mail}: version={version}, action={action}")
        try:
            result = self.solver.recaptcha(
                sitekey=sitekey,
                url=url,
                enterprise=1,
                version=version,
                invisible=invisible,
                action=action,
                score=0.3 if score else None,
            )
            token = result.get('code') if isinstance(result, dict) else str(result)
            if not token:
                logger.error(f"No token received from 2captcha for {self.mail}")
                return None
            logger.info(f"reCAPTCHA solved for {self.mail}: {sitekey}")
            return token
        except Exception as e:
            logger.error(f"reCAPTCHA solving error for {self.mail}: {e}")
            return None

    async def register(
        self,
        enterprise_recaptcha_token: str,
        csrf_nonce: str,
        page_guid: str,
        enterprise_recaptcha_token_key_type: str
    ) -> Optional[Dict[str, Any]] | bool:
        url = "https://www.etsy.com/api/v3/ajax/bespoke/member/neu/specs/Join_Neu_Controller"
        payload = {
            "log_performance_metrics": False,
            "runtime_analysis": False,
            "specs": {
                "Join_Neu_Controller": [
                    "Join_Neu_ApiSpec_Page",
                    {
                        "state": {
                            "with_action_context": False,
                            "initial_state": "register",
                            "persistent": "true",
                            "from_page": "https://www.etsy.com/",
                            "from_action": "register-header",
                            "form_action": "",
                            "workflow": {"identifier": "", "type": ""},
                            "view_type": "overlay",
                            "password": self.password,
                            "show_social_sign_in": False,
                            "login_only": False,
                            "is_from_etsyapp": False,
                            "submit_attempt": "register",
                            "should_use_new_password_skin": False,
                            "should_show_order_tracking": False,
                            "workflow_identifier": "",
                            "workflow_type": "",
                            "third_party_authenticator": "",
                            "_nnc": csrf_nonce,
                            "email": self.mail,
                            "first_name": self.first_name,
                            "email_marketing_opt_in": "true",
                            "enterprise_recaptcha_token": enterprise_recaptcha_token,
                            "enterprise_recaptcha_token_key_type": enterprise_recaptcha_token_key_type,
                            "google_user_id": "",
                            "google_code": "",
                            "facebook_user_id": "",
                            "facebook_access_token": "",
                        }
                    }
                ]
            }
        }
        if enterprise_recaptcha_token_key_type == "checkbox_difficult":
            payload['specs']['Join_Neu_Controller'][1]['state']['g-recaptcha-response'] = enterprise_recaptcha_token

        headers = self._generate_headers(REGISTER_HEADERS)
        headers['X-Csrf-Token'] = csrf_nonce
        headers['X-Page-Guid'] = page_guid

        logger.debug(f"Registering {self.mail}")
        await asyncio.sleep(random.uniform(1, 3))
        resp = await self.fetch(url=url, method="POST", json=payload, headers=headers)
        if not resp:
            logger.error(f"Registration request failed for {self.mail}")
            return None

        if enterprise_recaptcha_token_key_type == "score" and resp.get("status") == 200:
            try:
                output = resp["json"].get("output", {}).get("Join_Neu_Controller")
                if output:
                    soup = BeautifulSoup(output, 'lxml')
                    nnc_input = soup.find('input', attrs={'name': '_nnc'})
                    recaptcha_div = soup.find('div', id='g-recaptcha-etsy-register-checkbox_difficult')
                    if nnc_input and recaptcha_div:
                        new_csrf_nonce = nnc_input.get('value')
                        new_sitekey = recaptcha_div.get('data-sitekey')
                        logger.info(f"Additional reCAPTCHA required for {self.mail}")
                        new_token = await self.solve_recaptcha_enterprise(
                            sitekey=new_sitekey,
                            url="https://www.etsy.com/",
                            score=False
                        )
                        if not new_token:
                            return None
                        return await self.register(
                            enterprise_recaptcha_token=new_token,
                            csrf_nonce=new_csrf_nonce,
                            page_guid=page_guid,
                            enterprise_recaptcha_token_key_type="checkbox_difficult"
                        )
            except Exception as e:
                logger.error(f"Error parsing registration response for {self.mail}: {e}")

        return resp if resp.get("status") == 200 else False

    async def new_session(self) -> bool:
        try:
            if self.client and not self.client.closed:
                await self.client.close()

            await self.change_proxy()
            if not self.proxy:
                logger.error(f"No proxy available for {self.mail}")
                self.client = None
                return False

            self.client = ClientSession()
            self.session_id = str(uuid.uuid4())
            self.session_cookies.clear()
            self._initialize_fingerprint()
            logger.debug(f"New session created for {self.mail} (id: {self.session_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to create new session for {self.mail}: {e}")
            self.client = None
            return False

    def _generate_headers(self, headers_form: dict) -> Dict[str, str]:
        headers = self.fingerprint_emulator.generate_headers(headers_form)
        cookie_header = self._get_cookie_header()
        if cookie_header:
            headers["Cookie"] = cookie_header
        return headers

    async def fetch(
        self,
        url: str,
        method: str,
        max_attempts: int = 5,
        timeout: int = 100,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        if not self.proxy:
            logger.error(f"No proxy available for {self.mail}")
            return None

        proxy_url = f"http://{self.proxy}"
        headers = kwargs.get('headers', self.headers)
        request_config = {
            "url": url,
            "method": method,
            "headers": headers,
            "proxy": proxy_url,
            "session_id": self.session_id,
        }
        if 'data' in kwargs:
            if isinstance(kwargs['data'], dict):
                request_config["data"] = urlencode(kwargs['data'])
            else:
                request_config["data"] = str(kwargs['data'])
        elif 'json' in kwargs:
            request_config["json"] = json.dumps(kwargs['json'])

        for attempt in range(1, max_attempts + 1):
            try:
                if not self.client or self.client.closed:
                    if not await self.new_session():
                        return None

                async with self.client.post(self.go_server_url, json=request_config, timeout=timeout) as resp:
                    response = await resp.json()
                    if "error" in response:
                        raise Exception(response["error"])

                    status = response.get("status_code")
                    body = response.get("body", "")
                    if status in (200, 201):
                        logger.debug(f"Request successful: {method} {url} status {status}")
                        if "cookies" in response:
                            self._update_cookies(response["cookies"])
                        try:
                            json_body = json.loads(body) if body else {}
                        except json.JSONDecodeError:
                            json_body = {}
                        return {
                            "status": status,
                            "text": body,
                            "json": json_body,
                            "cookies": response.get("cookies", {})
                        }
                    elif status == 403 and "geo.captcha-delivery.com" in body:
                        logger.info(f"DataDome captcha triggered for {self.mail}, resetting session")
                        await self.new_session()
                        continue
                    else:
                        logger.warning(f"Bad status {status} for {method} {url} | {self.mail}")
                        return None

            except asyncio.TimeoutError:
                logger.warning(f"Timeout {url} (proxy {self.proxy}), attempt {attempt}/{max_attempts}")
                await asyncio.sleep(5)
            except ClientConnectionError as e:
                logger.warning(f"Connection error {url} (proxy {self.proxy}): {e}, attempt {attempt}/{max_attempts}")
                await self.new_session()
            except Exception as e:
                logger.error(f"Unexpected error fetching {url} for {self.mail}: {e}")
                return None

        logger.error(f"All {max_attempts} attempts exhausted for {method} {url} | {self.mail}")
        await self.new_session()
        return None

    async def close(self) -> None:
        if self.client and not self.client.closed:
            await self.client.close()
            logger.info(f"Session closed for {self.mail}")
