#!/usr/bin/env python3

import argparse
import os
import json
import requests
import sys
from datetime import datetime

class Ccu2Hass:
   def __init__(self):
      config_file = os.path.realpath(__file__).replace(".py", ".json")
      try:
         config_handle = open(config_file)
         config_dict   = json.load(config_handle)
      except Exception as e:
         print(f"Failed to open config file {config_file} as JSON:\nError: {e}")
         sys.exit(1)

      # General config
      config_general = config_dict.get("config", {})
      self.hass_mqtt_pub_opt  = f"-h '{config_general.get('hass_mqtt_host', '')}' -p '{config_general.get('hass_mqtt_port', '1883')}'"
      self.hass_mqtt_pub_opt += f" -u '{config_general.get('hass_mqtt_user')}'" if config_general.get('hass_mqtt_user', False) else ""
      self.hass_mqtt_pub_opt += f" -P '{config_general.get('hass_mqtt_pass')}'" if config_general.get('hass_mqtt_pass', False) else ""
      self.hass_mqtt_pub_opt += f" -i 'hass_discovery_ccu'"
      self.hass_mqtt_pub_opt += f" -r" if config_general.get('hass_mqtt_retain', False) else ""
      self.hass_mqtt_pub_opt += f" -q {config_general.get('hass_mqtt_qos', '1')}"
      self.hass_mqtt_topic_prefix = config_general.get("hass_mqtt_topic_prefix", "homeassistant")
      self.ccu_mqtt_topic_prefix = config_general.get("ccu_mqtt_topic_prefix", "homeassistant")
      self.use_ccu_device_title = config_general.get("use_ccu_device_title", True)
      self.use_ccu_channel_title = config_general.get("use_ccu_channel_title", False)
      self.url_ccu_jack = config_general.get("url_ccu_jack", "")

      # Mandatory for devices: type, entity_type, entity_name
      config_parameter = config_dict.get("parameter", {})
      self.paramater_all_devices = config_parameter.get("paramater_all_devices", {})
      self.parameter_per_device  = config_parameter.get("parameter_per_device", {})

   def SendDiscovery(self):
      devices_dict = self._http_request(f"{self.url_ccu_jack}/device")
      devices_list = devices_dict.get('~links', [])
      for device_info_dict in devices_list:
         if device_info_dict.get('rel', 'type_unknown') != 'device':
            continue

         device_id   = device_info_dict.get('href')
         device_dict = self._http_request(f"{self.url_ccu_jack}/device/{device_id}")
         device_type = device_dict.get('type')
         if device_type in self.parameter_per_device:
            timestamp = datetime.today().strftime('%s') + '000'
            device_name = f"{device_type}_{device_id}"
            if self.use_ccu_device_title:
               device_name = device_dict.get('title')
            device_firmware_current = device_dict.get('firmware')
            device_firmware_available = device_dict.get('availableFirmware')

            # store metadata for every device
            os.system("mosquitto_pub %s -t %s/status/%s/metadata/name -m '{ \"ts\": %s, \"v\": \"%s\"}'" % (self.hass_mqtt_pub_opt, self.ccu_mqtt_topic_prefix, device_id, timestamp, device_name))
            os.system("mosquitto_pub %s -t %s/status/%s/metadata/current_version -m '{ \"ts\": %s, \"v\": \"%s\"}'" % (self.hass_mqtt_pub_opt, self.ccu_mqtt_topic_prefix, device_id, timestamp, device_firmware_current))
            os.system("mosquitto_pub %s -t %s/status/%s/metadata/available_version -m '{ \"ts\": %s, \"v\": \"%s\"}'" % (self.hass_mqtt_pub_opt, self.ccu_mqtt_topic_prefix, device_id, timestamp, device_firmware_available))

            mqtt_device_info = {
               'device': {
                  'identifiers': [
                     f'ccujack_{device_id}'
                  ],
                  'name': device_name,
                  'model': device_type,
                  'sw_version': device_firmware_current,
                  'manufacturer': 'eQ-3',
               }
            }
            mqtt_device_availability = {
               'availability_topic': f'{self.ccu_mqtt_topic_prefix}/status/{device_id}/0/UNREACH',
               'availability_template': '{{ value_json.v }}',
               'payload_available': 'False',
               'payload_not_available': 'True',
            }
            mqtt_device_base = {
               'value_template': '{{ value_json.v }}',
               'retain': True,
               'qos': 1,
            }

            if device_type != 'HmIP-RFUSB':
               for channel in self.paramater_all_devices:
                  for channel_template in self.paramater_all_devices[channel]:
                     self._progress_channel_template(
                        channel_template = channel_template,
                        channel = channel,
                        device_type = device_type,
                        device_id = device_id,
                        mqtt_device_discovery_data = mqtt_device_info | mqtt_device_availability | mqtt_device_base,
                     )

            for channel in self.parameter_per_device[device_type]:
               for channel_template in self.parameter_per_device[device_type][channel]:
                  self._progress_channel_template(
                     channel_template = channel_template,
                     channel = channel,
                     device_type = device_type,
                     device_id = device_id,
                     mqtt_device_discovery_data = mqtt_device_info | mqtt_device_availability | mqtt_device_base,
                  )

   def _http_request(self, url: str):
      return_dict = {}
      try:
         request = requests.get(url)
         return_dict = request.json()
      except:
         pass

      return return_dict

   def _progress_channel_template(self, channel_template: dict, device_id: str, device_type: str, channel: str, mqtt_device_discovery_data: dict):
      channel_type = channel_template['type']
      entity_type  = channel_template['entity_type']
      entity_name  = channel_template['entity_name']
      # mqtt_device_name = device_name + ' ' + entity_name.capitalize() # "entity name beginning with device name" not supported for HASS >=2024.2
      mqtt_device_name = entity_name.capitalize()
      if self.use_ccu_channel_title:
         device_channel_dict = self._http_request(f"{self.url_ccu_jack}/device/{device_id}/{channel}/{channel_type}")
         mqtt_device_name    = device_channel_dict.get('title', mqtt_device_name)

      if 'availability_check' in channel_template and channel_template['availability_check'] == False:
         del mqtt_device_discovery_data['availability_topic']
         del mqtt_device_discovery_data['availability_template']
         del mqtt_device_discovery_data['payload_available']
         del mqtt_device_discovery_data['payload_not_available']

      if channel_type == "STATE":
         # main topic that is shown in homeassistant gui should shown without appendix 'Switch' etc.
         mqtt_device_discovery_data['name'] = ""
      else:
         mqtt_device_discovery_data['name'] = mqtt_device_name
      mqtt_device_discovery_data['unique_id'] = f"{device_id}_ccu_{entity_name}_{entity_type}"
      mqtt_device_discovery_data['object_id'] = f"{device_id}_ccu_{entity_name}"

      if entity_type == 'switch':
         mqtt_device_discovery_data['state_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['state_on'] = 'True'
         mqtt_device_discovery_data['state_off'] = 'False'
         mqtt_device_discovery_data['command_topic'] = f"{self.ccu_mqtt_topic_prefix}/set/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['payload_on'] = 'true'
         mqtt_device_discovery_data['payload_off'] = 'false'
      elif entity_type == 'light':
         del mqtt_device_discovery_data['value_template']
         mqtt_device_discovery_data['state_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['command_topic'] = f"{self.ccu_mqtt_topic_prefix}/set/{device_id}/{channel}/{channel_type}"
         if channel_template.get('schema') == 'default' or not 'schema' in channel_template:
            #mqtt_device_discovery_data['schema'] = 'default'
            mqtt_device_discovery_data['payload_on'] = 'true'
            mqtt_device_discovery_data['payload_off'] = 'false'
            mqtt_device_discovery_data['state_value_template'] = '{% if value_json.v %}on{% else %}off{% endif %}'
         elif channel_template.get('schema') == 'template':
            mqtt_device_discovery_data['schema'] = 'template'
            mqtt_device_discovery_data['state_template'] = '{% if value_json.v %}on{% else %}off{% endif %}'
            mqtt_device_discovery_data['command_on_template'] = 'true'
            mqtt_device_discovery_data['command_off_template'] = 'false'
         elif channel_template.get('schema') == 'json':
            mqtt_device_discovery_data['json_attributes_template'] = 'ToDo'
      elif entity_type == 'sensor':
         mqtt_device_discovery_data['state_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['state_class'] = channel_template.get('state_class', 'measurement')
      elif entity_type == 'binary_sensor':
         mqtt_device_discovery_data['state_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['payload_on'] = 'True'
         mqtt_device_discovery_data['payload_off'] = 'False'
      elif entity_type == 'update':
         mqtt_device_discovery_data['state_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/metadata/current_version"
         mqtt_device_discovery_data['latest_version_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/metadata/available_version"
         mqtt_device_discovery_data['latest_version_template'] = '{{ value_json.v }}'
      elif entity_type == 'number':
         mqtt_device_discovery_data['state_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['value_template'] = '{{ value_json.v * 100 }}'
         mqtt_device_discovery_data['command_topic'] = f"{self.ccu_mqtt_topic_prefix}/set/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['command_template'] = '{ "v": {{ value|int / 100}} }'
         mqtt_device_discovery_data['mode'] = 'box'
         mqtt_device_discovery_data['min'] = 0
         mqtt_device_discovery_data['max'] = 100
         mqtt_device_discovery_data['unit_of_measurement'] = "%"
      elif entity_type == 'cover':
         mqtt_device_discovery_data['state_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['value_template'] = '{% if value_json.v > 0.50 %} open {% else %} closed {% endif %}'
         mqtt_device_discovery_data['position_topic'] = f"{self.ccu_mqtt_topic_prefix}/status/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['position_template'] = '{{ value_json.v * 100 }}'
         mqtt_device_discovery_data['command_topic'] = f"{self.ccu_mqtt_topic_prefix}/set/{device_id}/{channel}/{channel_type}"
         mqtt_device_discovery_data['payload_open']  = '{ "v": 1.00 }'
         mqtt_device_discovery_data['payload_close'] = '{ "v": 0.9 }'
         #mqtt_device_discovery_data['payload_stop']  = ''

      # overwrite determined data with given data
      if 'state_class' in channel_template and channel_template['state_class'] == '-':
         del mqtt_device_discovery_data['state_class']

      if 'device_class' in channel_template:
         mqtt_device_discovery_data['device_class'] = channel_template['device_class']

      if 'value_template' in channel_template:
         mqtt_device_discovery_data['value_template'] = channel_template['value_template']

      if 'enabled' in channel_template:
         mqtt_device_discovery_data['enabled_by_default'] = channel_template['enabled']

      if 'category' in channel_template:
         mqtt_device_discovery_data['entity_category'] = channel_template['category']

      if 'unit' in channel_template:
         mqtt_device_discovery_data['unit_of_measurement'] = channel_template['unit']

      if 'icon' in channel_template:
         mqtt_device_discovery_data['icon'] = channel_template['icon']

      # Send HomeAssistant Discovery MQTT Message
      mqtt_topic = f"{self.hass_mqtt_topic_prefix}/{entity_type}/0x{device_id}/{entity_name}/config"
      mqtt_message = json.dumps(mqtt_device_discovery_data)
      os.system("mosquitto_pub %s -t %s -m '%s'" % (self.hass_mqtt_pub_opt, mqtt_topic, mqtt_message))
      print(f"Published {mqtt_topic}")

   def SendAll(self):
      devices_dict = self._http_request(f"{self.url_ccu_jack}/device")
      devices_list = devices_dict.get('~links', [])
      for device_info_dict in devices_list:
         if device_info_dict.get('rel', 'type_unknown') != 'device':
            continue

         # Send CCU-Jack device metadata MQTT Message
         device_dict = self._http_request(f"{self.url_ccu_jack}/device/{device_info_dict['href']}")
         timestamp   = datetime.today().strftime('%s') + '000'
         mqtt_topic  = f"{self.ccu_mqtt_topic_prefix}/status/{device_info_dict['href']}/metadata/name"
         os.system("mosquitto_pub %s -t %s -m '{ \"ts\": %s, \"v\": \"%s\"}'" % (self.hass_mqtt_pub_opt, mqtt_topic, timestamp, device_dict.get('title', 'title_unknown')))

         channel_list = device_dict.get('~links', [])
         for channel_info_dict in channel_list:
            if channel_info_dict.get('rel', 'unknown') != 'channel':
               continue

            channel_dict   = self._http_request(f"{self.url_ccu_jack}/device/{device_info_dict['href']}/{channel_info_dict['href']}")
            parameter_list = channel_dict.get('~links', [])
            for parameter_info_dict in parameter_list:
               if parameter_info_dict.get('rel', 'unknown') != 'parameter':
                  continue
               if parameter_info_dict.get('href', 'unknown') == '$MASTER':
                  continue

               # Send CCU-Jack device channel info MQTT Message
               value_dict   = self._http_request(f"{self.url_ccu_jack}/device/{device_info_dict['href']}/{channel_info_dict['href']}/{parameter_info_dict['href']}/~pv")
               mqtt_message = json.dumps(value_dict)
               mqtt_topic   = f"{self.ccu_mqtt_topic_prefix}/status/{device_info_dict['href']}/{channel_info_dict['href']}/{parameter_info_dict['href']}"
               os.system("mosquitto_pub %s -t %s -m '%s'" % (self.hass_mqtt_pub_opt, mqtt_topic, mqtt_message))
               print(f"Published {mqtt_topic}")


if __name__ == '__main__':
   if len(sys.argv) == 1:
      sys.argv.append("-h")
   parser = argparse.ArgumentParser()
   parser.add_argument('-d', '--discovery', help="send HomeAssistant auto-discovery data to MQTT broker", action='store_true')
   parser.add_argument('-a', '--all', help="send all CCU channels/states to MQTT broker", action='store_true')
   args = parser.parse_args()

   ccujack_hass_discovery = Ccu2Hass()
   if args.discovery:
      ccujack_hass_discovery.SendDiscovery()
   elif args.all:
      ccujack_hass_discovery.SendAll()
