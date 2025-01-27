import logging
import aiohttp
import asyncio
import async_timeout
from datetime import datetime, timedelta

from .const import APPLICATION_ID

_LOGGER = logging.getLogger(__name__)

class GlowmarktAPI:
    BASE_URL = "https://api.glowmarkt.com/api/v0-1"

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None
        self.session = None
        self.initial_load_completed = False  # Add this flag

    async def authenticate(self):
        """Authenticate with the Glowmarkt API."""
        _LOGGER.debug("Authenticating with Glowmarkt API")
        url = f"{self.BASE_URL}/auth"
        headers = {
            "applicationId": APPLICATION_ID,
            "Content-Type": "application/json"
        }
        data = {"username": self.username, "password": self.password}

        async with aiohttp.ClientSession() as session:
            try:
                async with async_timeout.timeout(10):
                    async with session.post(url, headers=headers, json=data) as response:
                        response.raise_for_status()
                        result = await response.json()
                        self.token = result["token"]
                _LOGGER.debug("Authentication successful")
            except aiohttp.ClientError as err:
                _LOGGER.error("Error authenticating with Glowmarkt API: %s", err)
                raise

    async def send_catchup_request(self):
        _LOGGER.debug("Fetching hourly readings for the last 24 hours from Glowmarkt API")
        if not self.token:
            await self.authenticate()

        url = f"{self.BASE_URL}/virtualentity"
        headers = {
            "applicationId": APPLICATION_ID,
            "token": self.token,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with async_timeout.timeout(10):
                    async with session.get(url, headers=headers) as response:
                        response.raise_for_status()
                        virtual_entities = await response.json()
                        _LOGGER.debug(f"Retrieved virtual entities: {virtual_entities}")

                readings = {"gas": [], "electricity": []}

                for entity in virtual_entities:
                    _LOGGER.debug(f"Processing entity: {entity}")
                    if "resources" not in entity:
                        _LOGGER.warning(f"Unexpected entity structure: {entity}")
                        continue

                    for resource in entity["resources"]:
                        _LOGGER.debug(f"Processing resource: {resource}")
                        resource_id = resource.get("resourceId")
                        resource_name = resource.get("name", "").lower()

                        readings_url = f"{self.BASE_URL}/resource/{resource_id}/catchup"
                        _LOGGER.debug(f"Sending Catchup to URL: {readings_url}")

                        try:
                            async with async_timeout.timeout(10):
                                async with session.get(readings_url, headers=headers) as readings_response:
                                    readings_response.raise_for_status()
                                    await readings_response.json()
                        except aiohttp.ClientResponseError as err:
                            _LOGGER.error(f"Error fetching readings for resource {resource_id}: {err}")
                            continue
            except aiohttp.ClientError as err:
                _LOGGER.error(f"Error fetching data from Glowmarkt API: {err}")
                raise

        # Need to wait 2 minutes for the catchup requests to complete
        await asyncio.sleep(120)

    async def get_hourly_readings(self):
        """Get hourly readings for the last 24 hours from the Glowmarkt API."""
        _LOGGER.debug("Fetching hourly readings for the last 24 hours from Glowmarkt API")
        if not self.token:
            await self.authenticate()

        if self.initial_load_completed:
            await self.send_catchup_request()

        url = f"{self.BASE_URL}/virtualentity"
        headers = {
            "applicationId": APPLICATION_ID,
            "token": self.token,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with async_timeout.timeout(10):
                    async with session.get(url, headers=headers) as response:
                        response.raise_for_status()
                        virtual_entities = await response.json()
                        _LOGGER.debug(f"Retrieved virtual entities: {virtual_entities}")

                readings = {"gas": [], "electricity": []}

                for entity in virtual_entities:
                    _LOGGER.debug(f"Processing entity: {entity}")
                    if "resources" not in entity:
                        _LOGGER.warning(f"Unexpected entity structure: {entity}")
                        continue

                    for resource in entity["resources"]:
                        _LOGGER.debug(f"Processing resource: {resource}")
                        resource_id = resource.get("resourceId")
                        resource_name = resource.get("name", "").lower()

                        if not resource_id:
                            _LOGGER.warning(f"Resource missing resourceId: {resource}")
                            continue

                        if "electricity" in resource_name or "gas" in resource_name:
                            resource_type = "electricity" if "electricity" in resource_name else "gas"
                            data_type = "cost" if "cost" in resource_name else "consumption"
                            _LOGGER.debug(f"Identified resource type: {resource_type}, data type: {data_type}")
                        else:
                            _LOGGER.debug(f"Skipping resource with name: {resource_name}")
                            continue

                        readings_url = f"{self.BASE_URL}/resource/{resource_id}/readings"
                        end_date = datetime.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
                        start_date = end_date - timedelta(hours=23)
                        params = {
                            "period": "PT1H",
                            "function": "sum",
                            "from": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                            "to": end_date.strftime("%Y-%m-%dT%H:%M:%S")
                        }
                        _LOGGER.debug(f"Fetching readings from URL: {readings_url} with params: {params}")

                        try:
                            async with async_timeout.timeout(10):
                                async with session.get(readings_url, headers=headers, params=params) as readings_response:
                                    readings_response.raise_for_status()
                                    data = await readings_response.json()
                                    _LOGGER.debug(f"Retrieved data for resource {resource_id}: {data}")
                                    if data.get("data"):
                                        for reading in data["data"]:
                                            end_time = datetime.fromtimestamp(reading[0]) + timedelta(hours=0)
                                            timestamp = end_time.strftime("%Y-%m-%d %H:%M:%S")
                                            value = reading[1]
                                            entry = next((item for item in readings[resource_type] if item["datetime"] == timestamp), None)
                                            if not entry:
                                                entry = {"datetime": timestamp, "consumption": 0, "cost": 0}
                                                readings[resource_type].append(entry)
                                            entry[data_type] += value
                                        _LOGGER.debug(f"Added readings for {resource_type} {data_type}")
                                    else:
                                        _LOGGER.warning(f"No data retrieved for resource {resource_id}")
                        except aiohttp.ClientResponseError as err:
                            _LOGGER.error(f"Error fetching readings for resource {resource_id}: {err}")
                            continue

                _LOGGER.debug(f"Final readings data passed to HA: {readings}")
                self.initial_load_completed = True
                return readings

            except aiohttp.ClientError as err:
                _LOGGER.error(f"Error fetching data from Glowmarkt API: {err}")
                raise

_LOGGER.debug("GlowmarktAPI class loaded")
