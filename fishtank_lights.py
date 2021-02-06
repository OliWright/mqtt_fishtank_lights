import time
import math
import json
import random

from . import RgbWW

moon_normalised_colour = RgbWW(0.59, 0.59, 0.78, 0, 0)
moon_brightness = 0.04

class BaseFishTankLights():
	def __init__(self, base_topic, name, colour_table, sun, moon, num_scale = 1):
		self.base_topic = base_topic
		self.name = name
		self.colour_table = colour_table
		self.sun = sun
		self.moon = moon
		self.num_scale = num_scale
		self.auto_colour = RgbWW(0,0,0,0,0)
		self.colour = RgbWW(0,0,0,0,0)
		self.boost = RgbWW(0,0,0,0,0)
		#self.colour_table.lightning_colour = RgbWW(0,0,0,0,0)
		self.subscribe_topic = self.base_topic + "/#"
		self.boost_topic = self.base_topic + "/boost"
		self.set_config_topic = self.base_topic + "/set_config"
		self.lightning_topic = self.base_topic + "/lightning"
		self.accumulated_time = 0;
		self.auto_brightness_level = 1
		self.dt = 10
		self.next_update_time = time.monotonic()
		self.lightning_start_time = None

	def calc_colour(self):
		moon_colour = moon_normalised_colour.mul(self.moon.illumination * moon_brightness)
		self.auto_colour = self.colour_table.lookupColour(self.sun.elevation) + moon_colour
		self.colour = self.auto_colour.mul(self.auto_brightness_level) + self.boost
		self.colour = self.colour.mul(self.num_scale)

	def on_update(self, client):
		# Do some work.
		#print("Updating " + self.name + ", sun elevation " + str(self.sun.elevation))
		previous_auto_colour = self.auto_colour
		self.calc_colour()
		now = time.monotonic()
		if self.lightning_start_time is not None:
			if self.lightning_phase == 0:
				# Instant flash up to full brightness
				# Hold for a random, but short amount of time
				flash_time = random.uniform(0.2, 0.5)
				print("Phase 0: " + str(flash_time))
				self.next_update_time = now + flash_time
				self.colour = self.colour + self.colour_table.lightning_colour
				self.publish(client, 0)
				self.lightning_phase = 1
			elif self.lightning_phase == 1:
				# Nearly instant dim
				self.next_update_time = now + 0.1
				dim_lightning_colour = self.colour_table.lightning_colour.mul(0.2)
				self.colour = self.colour + dim_lightning_colour
				print("Phase 1")
				self.publish(client, 0.05)
				self.lightning_phase = 2
			elif self.lightning_phase == 2:
				# Should we abort the lightning?
				decay_time = 1.5
				if (now - self.lightning_start_time) > random.uniform(1.5, 4):
					# Yes
					self.lightning_start_time = None
					# Allow the decay to complete before resuming normal operations
					self.next_update_time = now + decay_time
					print("End:")
				else:
					gap_time = random.uniform(0.1, 0.2)
					self.next_update_time = now + gap_time
					print("Phase 2: " + str(gap_time))
				# Slow fade during the gap
				self.publish(client, decay_time)
				self.lightning_phase = 0
		else:
			# Regular non-lightning update mode
			# Calculate the colour rate of change
			#diff_r = abs(self.auto_colour.r - previous_auto_colour.r)
			#diff_g = abs(self.auto_colour.g - previous_auto_colour.g)
			#diff_b = abs(self.auto_colour.b - previous_auto_colour.b)
			#diff_w0 = abs(self.auto_colour.w0 - previous_auto_colour.w0)
			#diff_w1 = abs(self.auto_colour.w1 - previous_auto_colour.w1)
			#diff = max(diff_r, diff_g, diff_b, diff_w0, diff_w1)
			#rate_of_change = diff / self.dt
			# And from that, when should our next update be
			#if rate_of_change > 0:
			#	self.dt = 1 / rate_of_change
			#	self.dt = max(self.dt, 1)
			#	self.dt = min(self.dt, 10)
			#else:
			#	self.dt = 10
			self.dt = 10
			self.next_update_time = now + self.dt
			self.publish(client, self.dt)

	# The callback for when a PUBLISH message is received from the server.
	def on_message(self, client, userdata, msg, payload):
		if msg.topic == self.boost_topic:
			json_payload = payload.replace("'", '"')
			print("Received boost " + json_payload)

			payload = json.loads(json_payload)
			self.boost.r = payload["r"]
			self.boost.g = payload["g"]
			self.boost.b = payload["b"]
			self.boost.w0 = payload["w0"]
			self.boost.w1 = payload["w1"]
			self.calc_colour()
			self.publish(client, 2)
		elif msg.topic == self.set_config_topic:
			json_payload = payload.replace("'", '"')
			print("Received config " + json_payload)

			payload = json.loads(json_payload)
			self.auto_brightness_level = payload["auto"]
			self.calc_colour()
			self.publish(client, 2)
		elif msg.topic == self.lightning_topic:
			now = time.monotonic()
			self.lightning_start_time = now
			self.next_update_time = now
			self.lightning_phase = 0

# Old Chinese LED WiFi controllers that are controlled from home assistant
class LegacyFishtankLights(BaseFishTankLights):
	def __init__(self, base_topic, name, colour_table, sun, moon):
		BaseFishTankLights.__init__(self, base_topic + "/" + name.lower(), name, colour_table, sun, moon, 255)
		self.publish_topic = base_topic + "/set"

	def publish(self, client, fade_time):
		# We need to specify a normalised colour, and a brightness.
		# Because home assistant.
		colour = self.colour
		r = colour.r
		g = colour.g
		b = colour.b
		w0 = int(colour.w0)
		w1 = int(colour.w1)
		brightness = max([r, g, b])
		if brightness == 0:
			r = g = b = 0
		else:
			recip_brightness = 255 / brightness
			r = min( [255, int(r * recip_brightness) ] )
			g = min( [255, int(g * recip_brightness) ] )
			b = min( [255, int(b * recip_brightness) ] )

		# This publishes an MQTT packet that is picked up by the "Set Fishtank Lights"
		# automation in home assistant.  The automation then controls the lights.
		message = '{{"entity_id":"light.{name}_fishtank","r":{r},"g":{g},"b":{b},"brightness":"{brightness}","w0":"{w0}","w1":"{w1}" }}'.format(name = self.name.lower(), r = r, g = g, b = b, brightness = int(brightness), w0 = w0, w1 = w1)
		client.publish(self.publish_topic, payload = message)
		#print(message)

# Home made ESP32 LED controller based on OpenMQTTGateway
class FishtankLights(BaseFishTankLights):
	def __init__(self, base_topic, name, controller_topic, colour_table, sun, mooon):
		BaseFishTankLights.__init__(self, base_topic + "/" + name.lower(), name, colour_table, sun, mooon)
		self.publish_topic = controller_topic + '/commands/MQTTtoPWM/set'

	def publish(self, client, fade_time):
		# This publishes an MQTT packet straight to the light.
		colour = self.colour
		message = '{{"r":{r},"g":{g},"b":{b},"w0":{w0},"w1":{w1},"fade":{fade_time}}}'.format(r = colour.r, g = colour.g, b = colour.b, w0 = colour.w0, w1 = colour.w1, fade_time = fade_time)
		client.publish(self.publish_topic, payload = message)
		#print(message)

