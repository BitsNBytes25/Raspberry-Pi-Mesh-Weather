import time
from dotenv import load_dotenv
from smbus2 import SMBus
import os
from .libs.pressure import set_pressure
from .libs.temperature import set_temperature
from .libs.humidity import set_humidity
from .libs.home_assistant import push_to_ha


class BME280Direct:
	def __init__(self, bus=1, address=0x76):
		self.address = address
		self.bus = SMBus(bus)
		self.load_calibration()
		# Set config: Forced/Normal mode and oversampling
		# 0x3F = Temp x16, Pres x16, Normal Mode
		self.bus.write_byte_data(self.address, 0xF4, 0x3F)
		# Humidity oversampling x16
		self.bus.write_byte_data(self.address, 0xF2, 0x05)

	def load_calibration(self):
		# T1-T3, P1-P9 (Reg 0x88 to 0xA1)
		b1 = self.bus.read_i2c_block_data(self.address, 0x88, 24)
		self.dig_T1 = self.u16(b1[1], b1[0])
		self.dig_T2 = self.s16(b1[3], b1[2])
		self.dig_T3 = self.s16(b1[5], b1[4])
		self.dig_P1 = self.u16(b1[7], b1[6])
		self.dig_P2 = self.s16(b1[9], b1[8])
		self.dig_P3 = self.s16(b1[11], b1[10])
		self.dig_P4 = self.s16(b1[13], b1[12])
		self.dig_P5 = self.s16(b1[15], b1[14])
		self.dig_P6 = self.s16(b1[17], b1[16])
		self.dig_P7 = self.s16(b1[19], b1[18])
		self.dig_P8 = self.s16(b1[21], b1[20])
		self.dig_P9 = self.s16(b1[23], b1[22])

		# H1 (Reg 0xA1)
		self.dig_H1 = self.bus.read_byte_data(self.address, 0xA1)
		# H2-H6 (Reg 0xE1 to 0xE7)
		b2 = self.bus.read_i2c_block_data(self.address, 0xE1, 7)
		self.dig_H2 = self.s16(b2[1], b2[0])
		self.dig_H3 = b2[2]
		self.dig_H4 = (b2[3] << 4) | (b2[4] & 0x0F)
		self.dig_H5 = (b2[5] << 4) | (b2[4] >> 4)
		self.dig_H6 = b2[6]
		if self.dig_H6 > 127: self.dig_H6 -= 256

	def u16(self, msb, lsb): return (msb << 8) | lsb
	def s16(self, msb, lsb):
		val = (msb << 8) | lsb
		return val if val < 32768 else val - 65536

	def get_readings(self):
		# Burst read all data registers (0xF7 to 0xFE)
		# P_msb, P_lsb, P_xlsb, T_msb, T_lsb, T_xlsb, H_msb, H_lsb
		d = self.bus.read_i2c_block_data(self.address, 0xF7, 8)

		raw_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
		raw_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
		raw_h = (d[6] << 8) | d[7]

		# Temperature Compensation
		v1 = (raw_t / 16384.0 - self.dig_T1 / 1024.0) * self.dig_T2
		v2 = ((raw_t / 131072.0 - self.dig_T1 / 8192.0) ** 2) * self.dig_T3
		t_fine = v1 + v2
		temp = t_fine / 5120.0

		# Pressure Compensation
		v1 = (t_fine / 2.0) - 64000.0
		v2 = v1 * v1 * self.dig_P6 / 32768.0
		v2 = v2 + v1 * self.dig_P5 * 2.0
		v2 = (v2 / 4.0) + (self.dig_P4 * 65536.0)
		v1 = (self.dig_P3 * v1 * v1 / 524288.0 + self.dig_P2 * v1) / 524288.0
		v1 = (1.0 + v1 / 32768.0) * self.dig_P1

		if v1 == 0: pres = 0 # Avoid div by zero
		else:
			pres = 1048576.0 - raw_p
			pres = ((pres - (v2 / 4096.0)) * 6250.0) / v1
			v1 = self.dig_P9 * pres * pres / 2147483648.0
			v2 = pres * self.dig_P8 / 32768.0
			pres = pres + (v1 + v2 + self.dig_P7) / 16.0

		# Humidity Compensation
		h = t_fine - 76800.0
		h = (raw_h - (self.dig_H4 * 64.0 + self.dig_H5 / 16384.0 * h)) * (self.dig_H2 / 65536.0 * (1.0 + self.dig_H6 / 67108864.0 * h * (1.0 + self.dig_H3 / 67108864.0 * h)))
		h = h * (1.0 - self.dig_H1 * h / 524288.0)
		hum = max(0, min(100, h)) # Clamp 0-100%

		return round(temp, 2), round(pres / 100.0, 2), round(hum, 2)


def main():
	load_dotenv()

	BME280_PORT = int(os.getenv('BME280_PORT', 1))
	BME280_ADDR = int(os.getenv('BME280_ADDR', 0x77), 16)
	HA_URL = os.getenv("HA_URL")
	HA_TOKEN = os.getenv("HA_TOKEN")

	sensor = BME280Direct(BME280_PORT, BME280_ADDR)

	while True:
		t, p, h = sensor.get_readings()
		# payload = {"temp": t, "pres": p, "hum": h, "time": time.time()}
		# pprint(payload)

		set_pressure(p)
		set_temperature(t)
		set_humidity(h)

		if HA_URL != '':
			# Push metrics
			push_to_ha(HA_URL, HA_TOKEN, "temperature", t, "°C")
			push_to_ha(HA_URL, HA_TOKEN, "humidity", h, "%")
			push_to_ha(HA_URL, HA_TOKEN, "pressure", p, "hPa")

		time.sleep(1)