import os


def get_humidity():
	if os.path.exists('/tmp/humidity.txt'):
		with open('/tmp/humidity.txt', 'r') as f:
			val = f.read()
			return None if val == '' else float(val)
	else:
		return None


def set_humidity(humidity):
	with open('/tmp/humidity.txt', 'w') as f:
		f.write(str(humidity))
