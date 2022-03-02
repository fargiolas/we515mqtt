#!/usr/bin/python3 -u

"""A MQTT to InfluxDB Bridge

This script receives MQTT data and saves those to InfluxDB.

"""

import re
import logging
import json
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient
from datetime import datetime
from datetime import timezone

INFLUXDB_ADDRESS = 'localhost'
INFLUXDB_PORT = 8086
INFLUXDB_USER = 'root'
INFLUXDB_PASSWORD = 'root'
INFLUXDB_DATABASE = 'home_db'

MQTT_ADDRESS = 'localhost'
MQTT_PORT = 1883
MQTT_TOPIC = '/dommu/#'
MQTT_CLIENT_ID = 'MQTTInfluxDBBridge'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mqttinfluxbridge")


class MQTTInfluxBridge(object):
    def __init__(self):
        self.delay = 1

        return

    def _init_influxdb_database(self):
        databases = self.influx.get_list_database()
        if len(list(filter(lambda x: x['name'] == INFLUXDB_DATABASE, databases))) == 0:
            logger.info(f'initializing {INFLUXDB_DATABASE} database')
            self.influx.create_database(INFLUXDB_DATABASE)

        logger.info(f'opening {INFLUXDB_DATABASE} database')
        self.influx.switch_database(INFLUXDB_DATABASE)

    def _on_connect(self, client, userdata, flags, rc):
        logger.info(f'connected to mqtt broker {MQTT_ADDRESS}:{MQTT_PORT}')
        logger.info(f'subscribing to topic: {MQTT_TOPIC}')
        self.mqtt.subscribe(MQTT_TOPIC)

    def _on_message(self, client, userdata, msg):
        self._parse_mqtt_message(msg.topic, msg.payload.decode('utf-8'))

    def _parse_mqtt_message(self, topic, payload):
        match = re.match('/(\w+)/(\w+)/(\w+)', topic)

        if match:
            _, location, measurement = match.groups()
            payload_dict = json.loads(payload)
            timestamp = payload_dict.pop('timestamp')
            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            points  = [{
                'measurement': measurement,
                'tags': {
                    'location': location
                },
                'time': timestamp,
                'fields': payload_dict
                }]

            self.influx.write_points(points)

    def run(self):
        self.mqtt = mqtt.Client(MQTT_CLIENT_ID)
        logger.info(f'connecting to influxdb server {INFLUXDB_ADDRESS}:{INFLUXDB_PORT}')
        self.influx = InfluxDBClient(INFLUXDB_ADDRESS, INFLUXDB_PORT,
                                     INFLUXDB_USER, INFLUXDB_PASSWORD, None)

        self._init_influxdb_database()

        self.mqtt = mqtt.Client(MQTT_CLIENT_ID)
        self.mqtt.on_connect = self._on_connect
        self.mqtt.on_message = self._on_message

        logger.info('connecting to mqtt broker')
        self.mqtt.connect(MQTT_ADDRESS, MQTT_PORT)
        self.mqtt.loop_forever()

if __name__ == '__main__':
    bridge = MQTTInfluxBridge()
    bridge.run()
