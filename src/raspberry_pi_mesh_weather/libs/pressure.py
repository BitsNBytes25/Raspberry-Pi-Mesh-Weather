import os


def get_pressure():
	if os.path.exists('/tmp/pressure.txt'):
		with open('/tmp/pressure.txt', 'r') as f:
			return float(f.read())
	else:
		return None


def set_pressure(pressure):
	with open('/tmp/pressure.txt', 'w') as f:
		f.write(str(pressure))
