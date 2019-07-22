from machine import I2C
import time
import xbee


class SHT31(object):
    '''
    A class to read temperature and humidity from SHT3x (SHT30, SHT31, SHT35) via the I2C communication.
    Please refer to 'Datasheet SHT3x-DIS(March2017-Version4)' details.
    '''
    CS_MODE_MAP = {  # ClockStretch is valid -> True
        True: {
            'high': b'\x2c\x06',
            'medium': b'\x2c\x0d',
            'low': b'\x2c\x10'
        },
        False: {
            'high': b'\x24\x00',
            'medium': b'\x24\x0b',
            'low': b'\x24\x16'
        }
    }

    I2C_ADDRESS = 0x44
    SOFT_RESET = b'\x30\xA2'
    HEATER_ON = b'\x30\x6D'
    HEATER_OFF = b'\x30\x66'
    HEATER_STATUS = b'\xF3\x2D'
    MEASUREMENT_WAIT_TIME = 0.015  # See Datasheet p7 [ Table 4 ](High repeatability)

    def __init__(self, i2c, slave_addr=I2C_ADDRESS):
        if i2c == None or i2c.__class__ != I2C:
            raise ValueError('I2C object needed as argument! ')
        self._i2c = i2c
        self._slave_addr_check(i2c, slave_addr)
        self._addr = slave_addr
        self._xbee = xbee.XBee()

    def _send(self, buf):
        return self._i2c.writeto(self._addr, buf)

    def _receive(self, count):
        return self._i2c.readfrom(self._addr, count)

    def soft_reset(self, i2c):
        """ See Datasheet p11 [ 4.9 Reset ]  """
        self._send(self.SOFT_RESET)

    def heater_status(self):
        """ See Datasheet p12 [ 4.11 Status Register ]  """
        self._send(self.HEATER_STATUS)
        data = self._receive(3)  # data(2byte) + crc(1byte)
        # Heater status is 13bit. ON -> 1 , OFF -> 0
        status = (data[0] << 8) + data[1]
        heater_is_on = status & (1 << 13) != 0
        if self._crc_checksum(data[0:2], 2) == data[2]:
            return heater_is_on
        else:
            return "status read failure"

    def turn_heater_on(self):
        """ See Datasheet p12 [ 4.10 Heater ]  """
        self._send(self.HEATER_ON)

    def turn_heater_off(self):
        """ See Datasheet p12 [ 4.10 Heater ]  """
        self._send(self.HEATER_OFF)

    def read_temp_and_humid(self, resolution='high', clock_stretch=True):
        if resolution not in ('high', 'medium', 'low'):
            raise ValueError('Wrong resolution value given!')
        self._send(self.CS_MODE_MAP[clock_stretch][resolution])
        self._xbee.sleep_now(int(self.MEASUREMENT_WAIT_TIME * 1000))  # XBee sleep
        data = self._receive(6)  # temp_data(2byte) + crc(1byte) + humid_data(2byte) + crc(1byte)
        temp_data = data[0:2]
        temp_checksum = data[2]
        humidity_data = data[3:5]
        humidity_checksum = data[5]
        if self._crc_checksum(temp_data, 2) == temp_checksum and \
                self._crc_checksum(humidity_data, 2) == humidity_checksum:
            return self._get_temperature_from_buffer(temp_data), self._get_humidity_from_buffer(humidity_data)

    @staticmethod
    def _slave_addr_check(i2c, slave_add):
        is_present = False
        peripherals = i2c.scan()
        if slave_add in peripherals:
            is_present = True
        assert is_present, " Did not find I2C slave address {:x}! ".format(slave_add)
        return is_present

    @staticmethod
    def _crc_checksum(data, number_of_bytes):
        """  See Datasheet p13 [ 4.12 Checksum Calculation ] """
        POLYNOMIAL = 0x131  # P(x)=x^8+x^5+x^4+1 = 100110001
        crc = 0xFF
        # calculates 8-Bit checksum
        for byteCtr in range(number_of_bytes):
            crc ^= data[byteCtr]
            for bit in range(8, 0, -1):
                if crc & 0x80:
                    crc = (crc << 1) ^ POLYNOMIAL
                else:
                    crc = (crc << 1)
        return crc

    @staticmethod
    def _get_temperature_from_buffer(data):
        """ See Datasheet p13 [ 4.13 Conversion of Signal Output]
        This function reads the first two bytes of data and returns
        the temperature by using the following function
        T = -45 + (175 * (ST/2^16))
        where ST is the value from the sensor
        """
        temperature = (data[0] << 8) + data[1]
        temperature *= 175.0
        temperature /= ((1 << 16) - 1)  # divide by (2^16 - 1)
        temperature -= 45
        return temperature

    @staticmethod
    def _get_humidity_from_buffer(data):
        """ See Datasheet p13 [ 4.13 Conversion of Signal Output]
        This function reads the first two bytes of data and returns
        the relative humidity by using the following function
        RH = (100 * (SRH / 2 ^16))
        where SRH is the value read from the sensor
        """
        humidity = (data[0] << 8) + data[1]
        humidity *= 100.0
        humidity /= ((1 << 16) - 1) # divide by (2^16 - 1)
        humidity -= 0
        return humidity
