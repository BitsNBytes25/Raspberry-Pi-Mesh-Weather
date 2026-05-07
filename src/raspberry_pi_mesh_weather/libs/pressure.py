import os


def get_pressure():
	if os.path.exists('/tmp/pressure.txt'):
		with open('/tmp/pressure.txt', 'r') as f:
			return float(f.read())
	else:
		return None


def get_pressure_change():
	"""
	Get if the pressure is quickly rising or falling.
	If rising (>1.5hPa per hour), return 1.
	If falling (>1.5hPa per hour), return -1.
	else, return 0.

	:return:
	"""
	if not os.path.exists('/tmp/pressure_log.txt'):
		return 0

	with open('/tmp/pressure_log.txt', 'r') as f:
		entries = f.read()
	entries = entries.split('\n')
	first_entry = float(entries[0])
	last_entry = float(entries[-1])
	diff = abs(last_entry - first_entry)
	if diff >= 1.5:
		return 1 if last_entry > first_entry else -1
	else:
		return 0



def set_pressure(pressure):
	with open('/tmp/pressure.txt', 'w') as f:
		f.write(str(pressure))

	# Store a log of temperature so we can calculate if the pressure is rising or falling.
	# We want to only store the last 60 entries.
	if os.path.exists('/tmp/pressure_log.txt'):
		with open('/tmp/pressure_log.txt', 'r') as f:
			entries = f.read().strip()

		entries = entries.split('\n')
		entries.append(str(pressure))
		if len(entries) > 60:
			entries = entries[len(entries)-60:]

		with open('/tmp/pressure_log.txt', 'w') as f:
			f.write('\n'.join(entries))
	else:
		with open('/tmp/pressure_log.txt', 'w') as f:
			f.write(f"{pressure}\n")
