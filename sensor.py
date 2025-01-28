"""Sensor platform for Glowmarkt integration."""
import logging
import traceback
import homeassistant.util.dt as dt_util

from datetime import datetime, timedelta
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    StatisticData,
    StatisticMetaData,
    get_last_statistics,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .glowmarkt_api import GlowmarktAPI

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "electricity_consumption": {
        "name": "Electricity Consumption",
        "icon": "mdi:flash",
        "device_class": "energy",
        "unit": "kWh",
        "state_class": "total",
    },
    "electricity_cost": {
        "name": "Electricity Cost",
        "icon": "mdi:cash",
        "device_class": "monetary",
        "unit": "GBP",
        "state_class": "total",
    },
    "gas_consumption": {
        "name": "Gas Consumption",
        "icon": "mdi:fire",
        "device_class": "gas",
        "unit": "m³",
        "state_class": "total",
    },
    "gas_cost": {
        "name": "Gas Cost",
        "icon": "mdi:cash",
        "device_class": "monetary",
        "unit": "GBP",
        "state_class": "total",
    },
}

KWH_TO_CUBIC_METERS = 0.0923

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Glowmarkt sensor platform."""
    api = GlowmarktAPI(config_entry.data["username"], config_entry.data["password"])

    async def async_update_data():
        return await api.get_hourly_readings()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="glowmarkt_sensor",
        update_method=async_update_data,
        update_interval=timedelta(minutes=20),
    )

    await coordinator.async_config_entry_first_refresh()

    readings = coordinator.data

    if not readings:
        _LOGGER.error("No readings data available")
        return

    entities = []
    for resource_type in ["gas", "electricity"]:
        if resource_type in readings:
            for data_type in ["consumption", "cost"]:
                sensor_type = f"{resource_type}_{data_type}"
                sensor_info = SENSOR_TYPES.get(sensor_type)
                if sensor_info:
                    sensor = GlowmarktSensor(coordinator, sensor_type, sensor_info)
                    entities.append(sensor)

    async_add_entities(entities)

    # Schedule the inject_historical_data function to run periodically
    async def update_historical_data(now):
        """Update historical data for all sensors."""
        for sensor in entities:
            await inject_historical_data(hass, sensor, now)

    # Run immediately and then every 30 minutes
    await update_historical_data(None)
    async_track_time_interval(
        hass, update_historical_data, timedelta(minutes=20)
    )

from datetime import datetime
import time

from datetime import datetime
import time

from datetime import datetime
import time

from datetime import datetime
import time

from datetime import datetime
import time

async def inject_historical_data(hass, sensor, timestamp):
    """Inject historical data for all available readings."""

    if not sensor.coordinator or not sensor.coordinator.data:
        _LOGGER.error(f"No coordinator data available for {sensor.name}")
        return

    data = sensor.coordinator.data

    resource_type = sensor._sensor_type.split('_')[0]
    data_type = sensor._sensor_type.split('_')[1]

    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name=sensor._attr_name,
        source="recorder",
        statistic_id=f"sensor.{DOMAIN}_{resource_type}_{data_type}",
        unit_of_measurement=sensor._attr_native_unit_of_measurement,
    )

    statistic_id = f"sensor.{DOMAIN}_{resource_type}_{data_type}"

    # Fetch all existing statistics
    existing_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1000, statistic_id, False, {"state", "sum", "start"}
    )

    last_known_sum = 0
    last_processed_timestamp = None

    if existing_stats and statistic_id in existing_stats:
        existing_stats_list = existing_stats[statistic_id]
        if existing_stats_list:
            last_stat = existing_stats_list[-1]
            last_known_sum = round(last_stat["sum"], 3)
            last_processed_timestamp = last_stat["start"]

    _LOGGER.debug(f"Starting with last known sum: {last_known_sum}")

    # Sort readings by datetime
    sorted_readings = sorted(data[resource_type], key=lambda x: x["datetime"])

    statistics = []

    for reading in sorted_readings:
        timestamp = dt_util.as_utc(datetime.strptime(reading["datetime"], "%Y-%m-%d %H:%M:%S"))
        timestamp_float = timestamp.timestamp()
        value = reading.get(data_type)

        if value is not None:
            if data_type == "cost":
                value = round(value / 100, 3)  # Convert pence to pounds and round
            elif data_type == "consumption":
                value = round(float(value), 3)  # Round to 3 decimal places

            # Only add if it's a new reading
            if last_processed_timestamp is None or timestamp_float > last_processed_timestamp:
                new_sum = round(last_known_sum + value, 3)  # Round to 3 decimal places

                statistics.append(
                    StatisticData(
                        start=timestamp,
                        state=value,
                        sum=new_sum,
                        last_reset=None
                    )
                )
                _LOGGER.debug(f"Added: Timestamp: {timestamp}, Value: {value}, New Sum: {new_sum}")

                # Update last known sum and timestamp
                last_known_sum = new_sum
                last_processed_timestamp = timestamp_float

    if statistics:
        try:
            async_import_statistics(hass, metadata, statistics)
            _LOGGER.debug(f"Successfully added {len(statistics)} new statistic entries for {sensor.name}")
        except Exception as e:
            _LOGGER.error(f"Error inserting historical data for {sensor.name}: {str(e)}")
    else:
        _LOGGER.debug(f"No new statistics to add for {sensor.name}")

    _LOGGER.info(f"Completed processing data for {sensor.name}")

class GlowmarktSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Glowmarkt sensor."""

    def __init__(self, coordinator, sensor_type, sensor_info):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_device_class = sensor_info["device_class"]
        self._attr_icon = sensor_info["icon"]
        self._attr_state_class = sensor_info["state_class"]
        self._attr_name = f"Glowmarkt {sensor_info['name']}"
        self._attr_unique_id = f"glowmarkt_{sensor_type}"

        if "_cost" in self._sensor_type:
            self._attr_native_unit_of_measurement = "GBP"
        else:
            self._attr_native_unit_of_measurement = sensor_info["unit"]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        resource_type = self._sensor_type.split('_')[0]
        data_type = self._sensor_type.split('_')[1]

        latest_reading = max(self.coordinator.data[resource_type], key=lambda x: x["datetime"])
        value = latest_reading.get(data_type)

        if value is None:
            return None

        if data_type == "cost":
            return round(value / 100, 2)  # Convert pence to pounds
        else:
            return round(value, 3)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self.coordinator.data is None:
            return {}

        attributes = {}
        total_consumption = 0
        total_cost = 0
        resource_type = self._sensor_type.split('_')[0]

        for reading in self.coordinator.data[resource_type]:
            if "consumption" in self._sensor_type:
                total_consumption += reading.get("consumption", 0)
            if "cost" in self._sensor_type:
                total_cost += reading.get("cost", 0)

        if total_consumption > 0 and total_cost > 0:
            cost_per_unit = (total_cost / 100) / total_consumption  # pence to pounds
            attributes["cost_per_unit"] = round(cost_per_unit, 4)

            if 'gas' in self._sensor_type:
                attributes["cost_per_unit_unit"] = f"GBP/{UnitOfVolume.CUBIC_METERS}"
            else:
                attributes["cost_per_unit_unit"] = f"GBP/{UnitOfEnergy.KILO_WATT_HOUR}"

        return attributes

_LOGGER.debug("Sensor platform module loaded")
