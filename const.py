"""Constants for the Glowmarkt integration."""

DOMAIN = "glowmarkt"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Hardcoded application ID
APPLICATION_ID = "b0f1b774-a586-4f72-9edd-27ead8aa7a8d"

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
