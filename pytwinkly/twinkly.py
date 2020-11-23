import base64, os
import asyncio
import aiohttp

class TwinklyClient:
    def __init__(self, ipaddress):
        self.ipaddress = ipaddress
        self.baseUrl = "http://{}/xled/v1/".format(self.ipaddress)
        self.loginUrl = "{}login".format(self.baseUrl)
        self.verifyUrl = "{}verify".format(self.baseUrl)
        self.modeUrl = "{}led/mode".format(self.baseUrl)
        self.deviceUrl = "{}gestalt".format(self.baseUrl)
        self.brightnessUrl = "{}led/out/brightness".format(self.baseUrl)

        # populated after first request
        self.challenge = None
        self.challenge_response = None
        self.authentication_token = None
        self.headers = None
    
    def generate_challenge(self):
        """
        Generates random challenge string
        :rtype: str
        """
        return os.urandom(32)

    async def send_challenge(self, session):
        b64_challenge = base64.b64encode(self.challenge).decode("utf-8")
        body = {"challenge": b64_challenge}
        _r = await session.post(self.loginUrl, json=body)
        if _r.status != 200:
            return False
        content = await _r.json()
        if content[u"code"] != 1000:
            return False
        self.challenge_response = content["challenge-response"]
        self.authentication_token = content["authentication_token"]
        return True

    async def send_challenge_response(self, session):
        headers = {"X-Auth-Token": self.authentication_token}
        body = {u"challenge-response": self.challenge_response}
        _r = await session.post(self.verifyUrl, headers=headers, json=body)
        if _r.status != 200:
            return False
        return True
        
    async def authenticate(self):
        """Handles user authentication with challenge-response"""
        async with aiohttp.ClientSession() as session:
            self.challenge = self.generate_challenge()
            #log.debug("authenticate(): Challenge: %s", repr(self.challenge))
            login_successful = await self.send_challenge(session)
            if not login_successful:
                return False

            verify_successful = await self.send_challenge_response(session)
            if not verify_successful:
                return False

            self.headers = {"X-Auth-Token": self.authentication_token}
            return True
        
    async def get_device_info(self):
        async with aiohttp.ClientSession() as session:
            response = await session.get(self.deviceUrl, headers=self.headers)
            return await response.json()
        
    async def get_mode(self):       
        async with aiohttp.ClientSession() as session:
            response = await session.get(self.modeUrl, headers=self.headers)
            result = await response.json()
            return result ["mode"]

    async def set_mode(self, mode):
        async with aiohttp.ClientSession() as session:
            assert mode in ("movie", "demo", "off")
            json_payload = {"mode": mode}
            response = await session.post(self.modeUrl, json=json_payload, headers=self.headers)
            return await response.json()

    async def get_brightness(self):       
        async with aiohttp.ClientSession() as session:
            response = await session.get(self.brightnessUrl, headers=self.headers)
            result = await response.json()
            if result[u"mode"] == "disabled":
                return 100
            return int(result[u"value"])

    async def set_brightness(self, brightness):
        async with aiohttp.ClientSession() as session:
            assert brightness <= 100
            assert brightness >= 0
            if brightness < 100:
                json_payload = {"mode": "enabled", "type": "A", "value": str(brightness)}
            else:
                json_payload = {"mode": "disabled", "type": "A"}
            response = await session.post(self.brightnessUrl, json=json_payload, headers=self.headers)
            result = await response.json()
            return result[u"code"] == 1000

    async def turn_on(self):
        result = await self.set_mode("movie")
        return result[u"code"] == 1000

    async def turn_off(self):
        result = await self.set_mode("off")
        return result[u"code"] == 1000

    async def is_on(self):
        """
        Returns True if device is on
        """
        return await self.get_mode() != "off"
