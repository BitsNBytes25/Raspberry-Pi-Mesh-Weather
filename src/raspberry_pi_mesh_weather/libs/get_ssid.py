import subprocess


def get_ssid():
	try:
		# Runs 'nmcli -t -f active,ssid dev wifi'
		# This filters for only the active connection and shows the SSID
		cmd = ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"]
		output = subprocess.check_output(cmd, text=True)

		for line in output.strip().split('\n'):
			if line.startswith("yes:"):
				return line.split(":")[1]
		return None
	except Exception as e:
		print(f"Error: {e}")
		return None
