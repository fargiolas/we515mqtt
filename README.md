# Orno WE-515 to MQTT

A couple of services to read data from a OR-WE-515 Energy meter and broadcast it to my local MQTT broker and to Grafana for visualization. It will probably work with with OR-WE-514 too commenting out the lines that read the multitariff registers.

Nothing too refined and mainly meant for personal use.

### `we515mqtt.py`
The main service, reads data WE515 from Modbus RTU over TCP and publish it to a MQTT broker.

To interact with the device over wifi I'm using a Protoss PW11-H.

### `mqttinfluxbridge.py`
Subscribes to MQTT data and writes it to a InfluxDB database

### Grafana dashboard example with latest measurements
<img width="800" alt="dashboard" src="https://user-images.githubusercontent.com/133750/156406397-02e12e53-44ab-4d82-b3bf-e92e3bc71c77.png">


## Useful references
- Orno WE515 https://orno.pl/en/product/1079/1-phase-multi-tariff-energy-meter-wtih-rs-485-100a-mid-1-module-din-th-35mm
- Orno WE515 RS484 Register List https://b2b.orno.pl/download-resource/26063/
- Protoss PW11 http://www.hi-flying.com/pw11
