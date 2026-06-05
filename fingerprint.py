import random
import time
import base64
import pendulum
from typing import Dict, Any

from browserforge.fingerprints import Screen, FingerprintGenerator
from loguru import logger


class FingerprintEmulator:
    def __init__(self, locale: str = "en-US", timezone: str = "America/New_York"):
        self.locale = locale
        self.timezone = timezone
        try:
            self.screen = Screen(min_width=1280, max_width=2560, min_height=720, max_height=1440)
            self.generator = FingerprintGenerator(
                browser="chrome",
                os="windows",
                device="desktop",
                locale=locale,
                screen=self.screen,
                http_version=2,
                strict=True,
                mock_webrtc=True,
            )
            self.fingerprint = self.generator.generate()
            self.fingerprint.headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            )
            self.fingerprint.headers["Sec-Ch-Ua"] = (
                '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"'
            )
            self.fingerprint.headers["Sec-Ch-Ua-Full-Version-List"] = (
                '"Not(A:Brand";v="99.0.0.0", "Google Chrome";v="133.0.6943.142", '
                '"Chromium";v="133.0.6943.142"'
            )
            self.network_params = self._generate_network_params()
            self.fingerprint.headers.update(self.network_params)
            self.js_data = self._generate_js_data()
            self.event_counters = self._generate_event_counters()
        except Exception as e:
            logger.error(f"FingerprintEmulator initialization failed: {e}")
            raise

    def _generate_network_params(self) -> Dict[str, str]:
        try:
            downlink = round(random.uniform(1.0, 10.0), 2)
            rtt = random.randint(50, 300)
            ect = random.choice(["4g", "3g"])
            return {"Downlink": str(downlink), "Rtt": str(rtt), "Ect": ect}
        except Exception as e:
            logger.error(f"Network params generation failed: {e}")
            return {"Downlink": "5.0", "Rtt": "100", "Ect": "4g"}

    def generate_headers(self, headers_form: dict) -> Dict[Any, Any]:
        for key, value in headers_form.items():
            headers_form[key] = self.fingerprint.headers.get(key, "") or headers_form[key]
        return headers_form

    def generate_base_headers(self) -> Dict[str, str]:
        return self.fingerprint.headers

    def _generate_js_data(self) -> Dict[str, Any]:
        try:
            tz_info = pendulum.timezone(self.timezone)
            now = pendulum.now(tz_info)
            tz_offset_seconds = now.utcoffset().total_seconds()
            tz = int(tz_offset_seconds / 60)

            js_data = {}
            js_data["ttst"] = round(random.uniform(20, 40), 12)
            js_data["ifov"] = False
            js_data["hc"] = self.fingerprint.navigator.hardwareConcurrency
            js_data["br_oh"] = self.fingerprint.screen.outerHeight
            js_data["br_ow"] = self.fingerprint.screen.outerWidth
            js_data["ua"] = self.fingerprint.headers.get("User-Agent")
            js_data["wbd"] = False
            js_data["dp0"] = True
            js_data["tagpu"] = round(random.uniform(0.5, 1.0), 15)
            js_data["wdif"] = False
            js_data["wdifrm"] = False
            js_data["npmtm"] = False
            js_data["br_h"] = self.fingerprint.screen.height
            js_data["br_w"] = self.fingerprint.screen.width
            js_data["isf"] = False
            js_data["nddc"] = 1
            js_data["rs_h"] = self.fingerprint.screen.availHeight
            js_data["rs_w"] = self.fingerprint.screen.availWidth
            js_data["rs_cd"] = 24
            js_data["phe"] = False
            js_data["nm"] = False
            js_data["jsf"] = False
            js_data["lg"] = self.fingerprint.navigator.language
            js_data["pr"] = self.fingerprint.screen.devicePixelRatio
            js_data["ars_h"] = self.fingerprint.screen.availHeight
            js_data["ars_w"] = self.fingerprint.screen.availWidth
            js_data["tz"] = tz
            js_data["str_ss"] = True
            js_data["str_ls"] = True
            js_data["str_idb"] = True
            js_data["str_odb"] = False
            js_data["plgod"] = False
            js_data["plg"] = 5
            js_data["plgne"] = True
            js_data["plgre"] = True
            js_data["plgof"] = False
            js_data["plggt"] = False
            js_data["pltod"] = False
            js_data["hcovdr"] = False
            js_data["hcovdr2"] = False
            js_data["plovdr"] = False
            js_data["plovdr2"] = False
            js_data["ftsovdr"] = False
            js_data["ftsovdr2"] = False
            js_data["lb"] = False
            js_data["eva"] = 33
            js_data["lo"] = False
            js_data["ts_mtp"] = 0
            js_data["ts_tec"] = False
            js_data["ts_tsa"] = False
            js_data["vnd"] = self.fingerprint.navigator.vendor
            js_data["bid"] = "NA"
            js_data["mmt"] = "application/pdf,text/pdf"
            js_data["plu"] = "PDF Viewer,Chrome PDF Viewer,Chromium PDF Viewer,Microsoft Edge PDF Viewer,WebKit built-in PDF"
            js_data["hdn"] = False
            js_data["awe"] = False
            js_data["geb"] = False
            js_data["dat"] = False
            js_data["med"] = "defined"
            js_data["aco"] = "probably"
            js_data["acots"] = False
            js_data["acmp"] = "probably"
            js_data["acmpts"] = True
            js_data["acw"] = "probably"
            js_data["acwts"] = False
            js_data["acma"] = "maybe"
            js_data["acmats"] = False
            js_data["acaa"] = "probably"
            js_data["acaats"] = True
            js_data["ac3"] = ""
            js_data["ac3ts"] = False
            js_data["acf"] = "probably"
            js_data["acfts"] = False
            js_data["acmp4"] = "maybe"
            js_data["acmp4ts"] = False
            js_data["acmp3"] = "probably"
            js_data["acmp3ts"] = False
            js_data["acwm"] = "maybe"
            js_data["acwmts"] = False
            js_data["ocpt"] = False
            js_data["vco"] = ""
            js_data["vcots"] = False
            js_data["vch"] = "probably"
            js_data["vchts"] = True
            js_data["vcw"] = "probably"
            js_data["vcwts"] = True
            js_data["vc3"] = "maybe"
            js_data["vc3ts"] = False
            js_data["vcmp"] = ""
            js_data["vcmpts"] = False
            js_data["vcq"] = ""
            js_data["vcqts"] = False
            js_data["vc1"] = "probably"
            js_data["vc1ts"] = True
            js_data["dvm"] = self.fingerprint.navigator.deviceMemory
            js_data["sqt"] = False
            js_data["so"] = "landscape-primary"
            js_data["wdw"] = True
            js_data["cokys"] = base64.b64encode("loadTimescsiapp".encode()).decode()
            js_data["ecpc"] = False
            js_data["lgs"] = True
            js_data["lgsod"] = False
            js_data["psn"] = True
            js_data["edp"] = True
            js_data["addt"] = True
            js_data["wsdc"] = True
            js_data["ccsr"] = True
            js_data["nuad"] = True
            js_data["bcda"] = False
            js_data["idn"] = True
            js_data["capi"] = False
            js_data["svde"] = False
            js_data["vpbq"] = True
            js_data["ucdv"] = False
            js_data["spwn"] = False
            js_data["emt"] = False
            js_data["bfr"] = False
            js_data["dbov"] = False
            js_data["cfpfe"] = base64.b64encode(
                "function(e,t,r){var n,o;if(!e)return this;r=r||C;if("
                "\"string\"===typeof e)n=\"<\"===e[0]&&\">\"===e["
                "e.length-1]&&e.length>=3?Wnull,e,null]:j.exec(e);"
                "if(!n|".encode()
            ).decode()
            js_data["stcfp"] = base64.b64encode(
                "43029.js:2:187835)\n    at XMLHttpRequest.<anonymous> ("
                "https://www.etsy.com/ac/evergreenVendor/js/en-US/vendor_bundle.de439cd03f5b2cb43029.js:2:191457"
                ")".encode()
            ).decode()
            js_data["ckwa"] = True
            js_data["prm"] = True
            js_data["cvs"] = True
            js_data["usb"] = "defined"
            js_data["emd"] = "k:ai,vi,ao"
            js_data["glvd"] = self.fingerprint.videoCard.vendor
            js_data["glrd"] = self.fingerprint.videoCard.renderer
            js_data["wwl"] = False
            js_data["jset"] = int(time.time())
            return js_data
        except Exception as e:
            logger.error(f"js_data generation failed: {e}")
            return {}

    def _generate_event_counters(self) -> list:
        return []

    def get_js_data(self) -> Dict[str, Any]:
        return self.js_data

    def get_event_counters(self) -> list:
        return self.event_counters
