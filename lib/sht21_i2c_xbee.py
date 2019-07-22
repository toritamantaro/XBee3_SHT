from machine import I2C
import time
import xbee


class SHT21(object):
    ''' A class to read temperature and humidity from SHT2x (SHT20, SHT21, SHT25) via the I2C communication.
    Please refer to 'Sensirion_Humidity_Sensors_SHT21_Datasheet' details.
    https://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/0_Datasheets/Humidity/Sensirion_Humidity_Sensors_SHT21_Datasheet.pdf
    '''
    I2C_ADDRESS = 0x40
    SOFT_RESET = b'\xFE'
    TRIGGER_TEMPERATURE_NO_HOLD = b'\xF3'
    TRIGGER_HUMIDITY_NO_HOLD = b'\xF5'
    STATUS_BITS_MASK = 0xFFFC  # 0xFFFC is 1111111111111100. This can be used for clean last two bits.

    TEMPERATURE_WAIT_TIME = 0.085  # See Datasheet p9 [ Table 7 ]
    HUMIDITY_WAIT_TIME = 0.029  # See Datasheet p9 [ Table 7 ]
    SORT_RESET_WAIT_TIME = 0.015  # See Datasheet p9 [ 5.5 Soft Reset ]

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

    def _soft_reset(self, i2c):
        """ See Datasheet p9 [ 5.5 Soft Reset ]  """
        ack = self._send(self.SOFT_RESET)  # reboot
        time.sleep(self.SORT_RESET_WAIT_TIME)
        if ack == 1:
            return True
        return False

    def read_temperature(self):
        self._send(self.TRIGGER_TEMPERATURE_NO_HOLD)
        # time.sleep(self.TEMPERATURE_WAIT_TIME)
        self._xbee.sleep_now(int(self.TEMPERATURE_WAIT_TIME * 1000))  # XBee sleep
        data = self._receive(3)  # value(2byte) + crc(1byte)
        if self._crc_checksum(data, 2) == data[2]:
            return self._get_temperature_from_buffer(data)

    def read_humidity(self):
        self._send(self.TRIGGER_HUMIDITY_NO_HOLD)
        # time.sleep(self.HUMIDITY_WAIT_TIME)
        self._xbee.sleep_now(int(self.HUMIDITY_WAIT_TIME * 1000))  # XBee sleep
        data = self._receive(3)  # value(2byte) + crc(1byte)
        if self._crc_checksum(data, 2) == data[2]:
            return self._get_humidity_from_buffer(data)

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
        """  See Datasheet p9 [ 5.7 CRC Checksum ] """
        POLYNOMIAL = 0x131  # P(x)=x^8+x^5+x^4+1 = 100110001
        crc = 0
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
        """ See Datasheet p10 [ 6 Conversion of Signal Output ]
        This function reads the first two bytes of data and returns
        the temperature by using the following function
        T = -46.85 + (175.72 * (ST/2^16))
        where ST is the value from the sensor
        """
        temperature = (data[0] << 8) + data[1]
        temperature &= SHT21.STATUS_BITS_MASK  # zero the status bits(last two bits).
        temperature *= 175.72
        temperature /= 1 << 16  # divide by 2^16
        temperature -= 46.85
        return temperature

    @staticmethod
    def _get_humidity_from_buffer(data):
        """ See Datasheet p10 [ 6 Conversion of Signal Output ]
        This function reads the first two bytes of data and returns
        the relative humidity by using the following function
        RH = -6 + (125 * (SRH / 2 ^16))
        where SRH is the value read from the sensor
        """
        humidity = (data[0] << 8) + data[1]
        humidity &= SHT21.STATUS_BITS_MASK  # zero the status bits(last two bits).
        humidity *= 125.0
        humidity /= 1 << 16  # divide by 2^16
        humidity -= 6
        return humidity
