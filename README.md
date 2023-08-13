# CCU-Jack to HomeAssistant

This script is providing two functions to connect [HomeMatic](https://homematic-ip.com) CCU to [HomeAssistant](https://www.home-assistant.io/) by [CCU-Jack](https://github.com/mdzio/ccu-jack) MQTT functionality. Other Add-Ons, HACS Integrations are not necessary.

Functions of hass_discovery_ccu.py:
- Send all CCU devices/channels to MQTT to provide all states immediately to HomeAssistant. If not, a CCU device state is published to MQTT if the state has changed.
- Send MQTT discovery topics for HomeAssistant to MQTT broker. HomeAssistant will create Devices and Entities immediately.

# Supported HomeMatic Devices

|Device|Type|Integration status|
|------|----|------------------|
|HM-Sec-SCo|Optischer Tür-/Fenster Sensor|Full|
|HM-WDS10-TH-O|Außenthermometer|Full|
|HmIP-BROLL|Rollladen Aktor|Show status, partly control due to different control channels on CCU side|
|HmIP-BSM|Unterputz Lichtschalter|Full|
|HmIP-PSM|Zwischenstecker|Full|
|HmIP-RFUSB|CCU Zentrale||
|HmIP-SMI|Bewegungsmelder|Full|
|HmIP-SRH|Tür-/Fenster Drehgriff Sensor|Full|

# Pre-Requirements
- CCU-Jack is installed on CCU
- MQTT Integration is installed on HomeAssistant (only one MQTT broker could be configured on HomeAssistant, so both CCU-Jack and HomeAssistant must use the same)
- Tool 'mosquitto_pub' is installed to publish messages to broker by hass_discovery_ccu.py, e.g. Ubuntu: apt-get install mosquitto-clients

# Configuration
HomeAssistant subscribes topics with auto-discovery data (published by hass_discovery_ccu.py) from "homeassistant".

CCU-Jack publishes CCU states (subscribed by HomeAssistant's auto-discovery information) to "ccu-jack/device/status".

CCU-Jack subscribes control data (published by HomeAssistant) from "ccu-jack/device/set", e.g. to switch a light.

![MQTT-Explorer](/pics/mqtt-explorer-small.png "MQTT Explorer")

## CCU-Jack
In my case I use MQTT broker [EMQX](https://www.emqx.io/) that is already connected to HomeAssistant. CCU-Jack publishes to MQTT broker for HomeAssistant (Outgoing) and subscribes topics to control CCU (Incoming) by using CCU-Jack's [MQTT-Bridge](https://github.com/mdzio/ccu-jack/wiki/MQTT-Bridge) functionally.

    "Bridge": {
      "Enable": true,
      "Address": "<IP-Address of MQTT broker>",
      "Port": <Port of MQTT broker>,
      "BufferSize": 0,
      "UseTLS": false,
      "CACertFile": "",
      "Insecure": false,
      "Username": "<user>",
      "Password": "<password>",
      "ClientID": "<client>",
      "CleanSession": true,
      "Incoming": [
        {
          "Pattern": "device/set/#",
          "LocalPrefix": "",
          "RemotePrefix": "ccu-jack/",
          "QoS": 1
        }
      ],
      "Outgoing": [
        {
          "Pattern": "device/status/#",
          "LocalPrefix": "",
          "RemotePrefix": "ccu-jack/",
          "QoS": 1
        }
      ]
    }

## hass_discovery_ccu.py
Before using the script to publish the auto-discovery to MQTT broker, connection details and other data needs to be set in configuration file "hass_discovery_ccu.json"

    "config": {
       "hass_mqtt_host": "<IP-Address of MQTT broker>",
       "hass_mqtt_port": "<Port of MQTT broker>",
       "hass_mqtt_user": "<user>",
       "hass_mqtt_pass": "<password>",
       "hass_mqtt_qos": 1,
       "hass_mqtt_retain": true,
       "hass_mqtt_topic_prefix": "homeassistant",
       "ccu_mqtt_topic_prefix": "ccu-jack/device",
       "url_ccu_jack": "http://<IP-Address of CCU-Jack>:<Port of CCU-Jack>",
       "use_ccu_device_title": true,
       "use_ccu_channel_title": false
    },

Usage:

    user@host:~$ python3 hass_discovery_ccu.py
    usage: hass_discovery_ccu.py [-h] [-d] [-a]

    options:
      -h, --help       show this help message and exit
      -d, --discovery  send HomeAssistant auto-discovery data to MQTT broker
      -a, --all        send all CCU channels/states to MQTT broker

## HomeAssistant
When auto-discovery data are pushed to topic "homeassistant", HomeAssistant creates the devices and entities immediately.

HomeMatic Device List in HomeAssistant:
![Device list](/pics/hass_devices.png "HomeAssistant Device List")

HomeMatic Device type "HmIP-BSM" details with entities:
![Device details](/pics/hass_device_details.png "HomeAssistant Device details")
