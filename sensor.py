"""Sensor platform for Glowmarkt integration."""
from datetime import datetime, timedelta
import logging
import traceback

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    StatisticData,
    StatisticMetaData,
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
import homeassistant.util.dt as dt_util

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
        update_interval=timedelta(minutes=30),
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
            await inject_historical_data(hass, sensor)

    # Run immediately and then every 30 minutes
    await update_historical_data(None)
    async_track_time_interval(
        hass, update_historical_data, timedelta(minutes=30)
    )

async def inject_historical_data(hass, sensor):
    """Inject historical data for all available readings."""
    _LOGGER.debug(f"Injecting historical data for {sensor.name}")

    if not sensor.coordinator or not sensor.coordinator.data:
        _LOGGER.error(f"No coordinator data available for {sensor.name}")
        return

    data = sensor.coordinator.data

    statistics = []
    resource_type = sensor._sensor_type.split('_')[0]
    data_type = sensor._sensor_type.split('_')[1]

    cumulative_sum = 0
    last_reset = None

    # Sort readings by datetime
    sorted_readings = sorted(data[resource_type], key=lambda x: x["datetime"])

    for reading in sorted_readings:
        timestamp = dt_util.as_utc(datetime.strptime(reading["datetime"], "%Y-%m-%d %H:%M:%S"))
        value = reading.get(data_type)
        if value is not None and value > 0:
            if data_type == "cost":
                value = value / 100  # Convert pence to pounds

            cumulative_sum += value

            statistics.append(
                StatisticData(
                    start=timestamp,
                    state=value,
                    sum=cumulative_sum,
                    last_reset=timestamp
                )
            )

            _LOGGER.debug(f"Inserting: {statistics}")

    if not statistics:
        _LOGGER.warning(f"No valid statistics generated for {sensor.name}")
        return

    _LOGGER.debug(f"Inserting {len(statistics)} historical records for {sensor.name}")

    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name=sensor._attr_name,
        source="recorder",
        statistic_id=f"sensor.{DOMAIN}_{resource_type}_{data_type}",
        unit_of_measurement=sensor._attr_native_unit_of_measurement,
    )

    try:
        async_import_statistics(hass, metadata, statistics)
    except Exception as e:
        _LOGGER.error(f"Error inserting historical data for {sensor.name}: {str(e)}")

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
