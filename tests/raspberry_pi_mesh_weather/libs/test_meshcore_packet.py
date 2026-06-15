from raspberry_pi_mesh_weather.libs.meshcore_packet import MeshcorePacket
import asyncio
import pytest


@pytest.mark.asyncio
async def test_flood_advert(mock_payload_flood_advert):
	packet = MeshcorePacket(mock_payload_flood_advert)
	assert packet.header == 17
	assert len(packet.path) == 3
	assert packet.path[0] == 'be'
	assert packet.path[1] == 'a1'
	assert packet.path[2] == 'e6'
	assert packet.rssi == -104
	assert packet.snr == 4.75
	assert packet.get_packet_hash() == 'A3718F63449786CF'
	assert packet.payload_type == 4
	assert packet.type == 1
	assert packet.name == 'CDP Sensor Node'
	assert packet.lat == 39.986553
	assert packet.lon == -82.983876

	mqtt = packet.as_mqtt()
	assert mqtt['route'] == 'F'


@pytest.mark.asyncio
async def test_direct_message(mock_payload_direct_message):
	packet = MeshcorePacket(mock_payload_direct_message)
	assert packet.hash == 173548026
	assert packet.header == 10
	assert len(packet.path) == 1
	assert packet.path[0] == 'be'
	assert packet.path_hash_size == 1
	assert packet.payload.hex().upper() == '5D4ADD7EF5CAD341E6947E147312863508A40F02'
	assert packet.payload_type == 2
	assert packet.payload_version == 0
	assert packet.route_type == 2
	assert packet.rssi == -30
	assert packet.snr == 12.0
	assert packet.get_packet_hash() == 'F2BE7A6EC23708DB'

	mqtt = packet.as_mqtt()
	assert mqtt['type'] == 'PACKET'
	assert mqtt['route'] == 'D'
	assert mqtt['direction'] == 'rx'
	assert mqtt['len'] == '23'
	assert mqtt['payload_len'] == '20'
	assert mqtt['path'] == 'be'
