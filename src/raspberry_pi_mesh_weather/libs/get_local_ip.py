import socket


def get_local_ip():
	"""
	Connects to a known external address (like Google's DNS server)
	and retrieves the local IP address associated with that connection.
	This is generally more reliable than just using socket.gethostbyname(socket.gethostname()).
	"""
	try:
		# Create a socket object
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

		# Connect the socket to a server (doesn't actually send data, just establishes the route)
		# We use Google's public DNS server address here as an example.
		sock.connect(("8.8.8.8", 80))

		# Once connected, we ask the socket for its local IP address
		local_ip = sock.getsockname()[0]
		return local_ip
	except Exception as e:
		print(f"An error occurred while fetching the IP address: {e}")
		return None
	finally:
		# Always close the socket when done! Good housekeeping!
		sock.close()