#!/usr/bin/env python3

import sys
import signal
import logging
import time
from datetime import datetime
import json
from pymodbus.client import ModbusTcpClient
from pymodbus import FramerType
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('we515mqtt')

def word2tuple(w):
   return (w >> 8) & 0xFF, w & 0xFF

def tuple2word(high, low):
   return (high << 8) | low

def tuple2long(high, low):
   return (high << 16) | low

# h, l = np.random.randint(0, 255, size=2)
# assert word2tuple(tuple2word(h, l)) == (h, l)

class GracefulInterrupt(object):
    '''Simple context manager to protect important code from unix
    signals. By default calls exit(0) after the protected code
    terminates (so that it can be used in a try/finally block). It can
    also save default signal handler and replay it after the important
    code completes.
    '''
    def __init__(self, signals=(signal.SIGINT, signal.SIGTERM), delayed=False):
        self.signals = signals
        self.delayed = delayed
        self.old_handler = dict()

    def __enter__(self):
        self.captured_signal = False

        for sig in self.signals:
            self.old_handler[sig] = signal.getsignal(sig)
            signal.signal(sig, self.handler)

    def handler(self, sig, frame):
        self.captured_signal = sig, frame
        logging.debug('Captured signal: {}, {}'.format(sig, frame))

    def __exit__(self, type, value, traceback):

        for sig in self.signals:
            signal.signal(sig, self.old_handler[sig])

        if self.captured_signal:
            if self.delayed:
                self.old_handler[self.captured_signal[0]](*self.captured_signal)
            else:
                sys.exit(0)

class WE515Manager(object):
    def __init__(self, mbus_host, mbus_port, mbus_addr, mqtt_host, mqtt_port, mqtt_topic):
        self.mbus_host = mbus_host
        self.mbus_port = mbus_port
        self.mbus_addr = mbus_addr

        self.mbus = ModbusTcpClient(self.mbus_host, port=self.mbus_port, framer=FramerType.SOCKET)

        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_topic = mqtt_topic
        self.mqtt = mqtt.Client()
        self.mqtt.on_connect = self._on_connect

        self.exit_code = 0
        self.delay = 1

    def set_multirate_limits(self, hstart, mstart, hend, mend):
        self.mbus.write_registers(0x8100, tuple2word(hstart, mstart), slave=self.mbus_addr)
        self.mbus.write_registers(0x8101, tuple2word(0, 1), slave=self.mbus_addr)
        self.mbus.write_registers(0x8102, tuple2word(hend, mend), slave=self.mbus_addr)
        self.mbus.write_registers(0x8103, tuple2word(0, 2), slave=self.mbus_addr)

        # reset all the other time periods and rates
        for i in range(12):
           self.mbus.write_registers(0x8104+i, tuple2word(0, 0), slave=self.mbus_addr)

    def _get_device_time(self):
        rr = self.mbus.read_holding_registers(0x8120, 3, slave=self.mbus_addr)
        y, m = word2tuple(rr.registers[0])
        d, H = word2tuple(rr.registers[1])
        M, S = word2tuple(rr.registers[2])

        return datetime(2000 + y, m, d, H, M, S)

    def _set_device_time(self, t):
        y, m, d, H, M, S, _, _, _ = t.timetuple()
        y = y - 2000
        self.mbus.write_registers(0x8120, tuple2word(y, m), slave=self.mbus_addr)
        self.mbus.write_registers(0x8121, tuple2word(d, H), slave=self.mbus_addr)
        self.mbus.write_registers(0x8122, tuple2word(M, S), slave=self.mbus_addr)

    def _read_byte(self, reg, scale):
        rr = self.mbus.read_holding_registers(reg, 1, slave=self.mbus_addr)
        return rr.registers[0] * scale

    def _read_word(self, reg, scale):
        rr = self.mbus.read_holding_registers(reg, 2, slave=self.mbus_addr)
        return tuple2word(*rr.registers) * scale

    def _read_long(self, reg, scale):
        rr = self.mbus.read_holding_registers(reg, 2, slave=self.mbus_addr)
        return tuple2long(*rr.registers) * scale

    def _on_connect(self, client, userdata, flags, rc):
        if (rc != 0):
            logger.warning(f'mqtt: connection refused: {rc}')
        else:
            logger.info(f'mqtt: connected to {self.mqtt_host}')

    def _read_data(self):
        freq = self._read_byte(0x130, 0.01)
        logger.debug(f'freq = {freq} Hz')
        voltage = self._read_byte(0x131, 0.01)
        logger.debug(f'voltage = {voltage} V')
        current = self._read_word(0x139, 0.001)
        logger.debug(f'current = {current} A')
        active_power = self._read_word(0x140, 1.)
        logger.debug(f'active power = {active_power} W')
        reactive_power = self._read_word(0x148, 0.001)
        logger.debug(f'reactive power = {reactive_power:.3f} kvar')
        apparent_power = self._read_word(0x150, 0.001)
        logger.debug(f'apparent power = {apparent_power:.3f} kva')
        power_factor = self._read_byte(0x158, 0.001)
        logger.debug(f'power factor = {power_factor:.3f}')

        total_active_energy = self._read_long(0xA000, 0.01)
        logger.debug(f'total active energy = {total_active_energy:.3f} kWh')
        rate1_active_energy = self._read_long(0xA002, 0.01)
        logger.debug(f'  F1 = {rate1_active_energy:.3f} kWh')
        rate2_active_energy = self._read_long(0xA004, 0.01)
        logger.debug(f'  F23 = {rate2_active_energy:.3f} kWh')

        total_reactive_energy = self._read_long(0xA01E, 0.01)
        logger.debug(f'total reactive energy = {total_reactive_energy:.3f} kWh')
        rate1_reactive_energy = self._read_long(0xA020, 0.01)
        logger.debug(f'  F1 = {rate1_reactive_energy:.3f} kWh')
        rate2_reactive_energy = self._read_long(0xA022, 0.01)
        logger.debug(f'  F23 = {rate2_reactive_energy:.3f} kWh')

        logger.debug('--')

        record = { 'freq': freq,
                   'voltage': voltage,
                   'current': current,
                   'active_power': active_power,
                   'reactive_power': reactive_power,
                   'apparent_power': apparent_power,
                   'power_factor': power_factor,
                   'total_active_energy': total_active_energy,
                   'rate1_active_energy': rate1_active_energy,
                   'rate2_active_energy': rate2_active_energy,
                   'total_reactive_energy': total_reactive_energy,
                   'rate1_reactive_energy': rate1_reactive_energy,
                   'rate2_reactive_energy': rate2_reactive_energy }

        return record

    def setup(self):
        self.mbus.connect()

        local_time = datetime.now()
        remote_time = self._get_device_time()
        delta = abs((local_time - remote_time).total_seconds())

        logger.info('device time: {}'.format(remote_time))
        logger.info('local time:  {}'.format(local_time))
        if (delta > 10):
            logger.warning('local and device time differ!')
            logger.info('syncing device time')
            self._set_device_time(datetime.now())
            logger.info('updated device time: {}'.format(self._get_device_time()))

        logger.info('mqtt: connecting asynchronously to {}:{}'.format(self.mqtt_host, self.mqtt_port))
        self.mqtt.connect_async(self.mqtt_host, self.mqtt_port)
        logger.info('mqtt: starting network thread')
        self.mqtt.loop_start()

    def cleanup(self):
        logger.info('mqtt: emptying message queue and stopping network thread')
        self.mqtt.loop_stop()
        self.mbus.close()

    def publish(self, record):
        timestamp = time.time()
        payload = ', '.join([f'{k}={v:.3f}' for k,v in record.items()])
        # payload = f'ts={timestamp}, {payload}'
        # logger.info(f'mqtt: publishing: {self.mqtt_topic} => {payload}')

        record.update({'timestamp': timestamp})

        payload_json = json.dumps(record)

        self.mqtt.publish(self.mqtt_topic, payload=payload_json, qos=1)

    def run(self):
        self.setup()

        try:
            while True:
                with GracefulInterrupt():
                    record = self._read_data()
                    self.publish(record)
                    if self.delay > 0:
                        time.sleep(self.delay)
        except SystemExit:
            pass
        except KeyboardInterrupt:
            logger.debug('Received KeyboardInterrupt')
        except BaseException:
            logger.exception('An exception occured in main loop')
            self.exit_code = 1
        finally:
            self.cleanup()
            if (self.exit_code != 0):
                sys.exit(self.exit_code)


if __name__ == '__main__':
    orno = WE515Manager('192.168.1.11', 8899, 0x01,
                        'localhost', 1883,
                        '/dommu/common/energy')

    # orno.set_multirate_limits(8, 0, 19, 0)
    orno.run()
