# Orno WE-515 to MQTT

A couple of services to read data from a OR-WE-515 Energy meter and broadcast it to my local MQTT broker and to Grafana for visualization.

### `we515mqtt.py`
The main service, reads data WE515 from Modbus RTU over TCP and publish it to a MQTT broker.

To interact with the device over wifi I'm using a Protoss PW11-H.

### `mqttinfluxbridge.py`
Subscribes to MQTT data and write it to a InfluxDB database

## sample Grafana dashboard from latest measurements
<img width="800" alt="grafana-dashboard" src="https://user-images.githubusercontent.com/133750/156337800-6c006f9c-a9be-4911-bdcc-291f927b8ccc.png">


## Useful references
- Orno WE515 https://orno.pl/en/product/1079/1-phase-multi-tariff-energy-meter-wtih-rs-485-100a-mid-1-module-din-th-35mm
- Orno WE515 RS484 Register List https://b2b.orno.pl/download-resource/26063/
- Protoss PW11 http://www.hi-flying.com/pw11
