import os


def get_temperature():
	if os.path.exists('/tmp/temperature.txt'):
		with open('/tmp/temperature.txt', 'r') as f:
			return float(f.read())
	else:
		return None


def set_temperature(temp):
	with open('/tmp/temperature.txt', 'w') as f:
		f.write(str(temp))
