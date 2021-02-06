import datetime
import math
import ephem
import array
import time

g = ephem.Observer()
g.name = 'Somewhere'
#g.lat = math.radians(53.2338)  # lat/long in decimal degrees  
g.lat = math.radians(20)  # lat/long in decimal degrees  
g.long = math.radians(-2.595)
desired_sunset_time = 21.0
desired_max_daytime_hours = 9
sunset_time_offset = datetime.timedelta(0)
sunrise_time_offset = datetime.timedelta(0)
midday_utc_hours = 0
midday_hours_to_skip = 0

LUT_INTERVAL_MINUTES = int(5)
NUM_LUT_ENTRIES = int(((24 * 60) / LUT_INTERVAL_MINUTES) + 1)
NUM_SECONDS_IN_A_DAY = int(24 * 60 * 60)

class CelestialData():
	def __init__(self, body_name):
		self.body_name = body_name
		self.elevation = 0
		self.illumination = 0
		methodToCall = getattr(ephem, body_name)
		self.body = methodToCall()
		self.computeTable(datetime.datetime.utcnow().date())
		self.Update()

	def computeTable(self, date):
		global g
		global desired_sunset_time
		global sunset_time_offset
		global sunrise_time_offset
		global midday_hours_to_skip
		global midday_utc_hours

		g.date = date
		is_sun = (self.body_name == 'Sun')
		
		if is_sun:
			# Establish sunrise and sunset times at our desired location
			sunrise_time = ephem.localtime(g.next_rising(self.body)).time()
			sunrise_time_hours = sunrise_time.hour + (sunrise_time.minute / 60.0) + (sunrise_time.second / 3600.0)
			print('Actual sunrise: ' + str(sunrise_time_hours))
			sunset_time = ephem.localtime(g.next_setting(self.body)).time()
			sunset_time_hours = sunset_time.hour + (sunset_time.minute / 60.0) + (sunset_time.second / 3600.0)
			midday_hours = (sunrise_time_hours + sunset_time_hours) / 2
			print('Actual midday: ' + str(midday_hours))
			print('Actual sunset: ' + str(sunset_time_hours))
			# Figure out how to offset the sunset and sunrise to achieve our
			# desired local sunrise time and max daytime length
			sunset_time_offset_hours = desired_sunset_time - sunset_time_hours
			sunset_time_offset = datetime.timedelta(hours = sunset_time_offset_hours)
			daytime_hours = sunset_time_hours - sunrise_time_hours;
			sunrise_time_offset_hours = sunset_time_offset_hours
			if daytime_hours > desired_max_daytime_hours:
				sunrise_time_offset_hours = sunset_time_offset_hours + daytime_hours - desired_max_daytime_hours
				daytime_hours = desired_max_daytime_hours
			sunrise_time_offset = datetime.timedelta(hours = sunrise_time_offset_hours)
			
			sunrise_time_hours = sunrise_time_hours + sunrise_time_offset_hours
			sunset_time_hours = sunset_time_hours + sunset_time_offset_hours
			midday_hours = (sunrise_time_hours + sunset_time_hours) / 2
			midday_hours_to_skip = sunrise_time_offset_hours - sunset_time_offset_hours
			print('Adjusted local sunrise: ' + str(sunrise_time_hours) + ", adjusted by " + str(sunrise_time_offset_hours) + " hours")
			print('Adjusted local midday: ' + str(midday_hours) + ", skipping " + str(midday_hours_to_skip) + " hours")
			print('Adjusted local sunset: ' + str(sunset_time_hours) + ", adjusted by " + str(sunset_time_offset_hours) + " hours")
			
			adjusted_day_length = datetime.timedelta(hours = (sunset_time_hours - sunrise_time_hours))
			sunrise_time = datetime.datetime.combine(date, sunrise_time) + sunrise_time_offset
			print('Adjusted sunrise: ' + str(sunrise_time))
			sunset_time = datetime.datetime.combine(date, sunset_time) + sunset_time_offset
			print('Adjusted sunset: ' + str(sunset_time))
			midday_time = sunrise_time + (adjusted_day_length / 2)
			print('Adjusted midday: ' + str(midday_time))
			# There's probably a better way to do this...
			utc_offset = datetime.datetime.now() - datetime.datetime.utcnow()
			utc_offset_hours = (utc_offset.total_seconds() + 1800) // 3600
			print('UTC Offset: ' + str(utc_offset_hours))
			midday_utc_hours = midday_hours - utc_offset_hours
			print('Adjusted midday: ' + str(midday_utc_hours))
	
		if is_sun:
			table_start_datetime = datetime.datetime.combine(date, datetime.time())
		else:
			table_start_datetime = (datetime.datetime.combine(date, datetime.time()) - sunrise_time_offset)
		print('Table start datetime: ' + str(table_start_datetime))
		g.date = table_start_datetime
		
		self.elevation_lut = array.array('f', [0.0] * NUM_LUT_ENTRIES)
		self.illumination_lut = array.array('f', [0.0] * NUM_LUT_ENTRIES)

		print('Calculating look-up-table for ' + self.body_name)
		self.look_up_table_date = date
		is_morning = True
		for i in range(NUM_LUT_ENTRIES):
			self.body.compute(g)
			self.elevation_lut[i] = self.body.alt
			self.illumination_lut[i] = max( self.body.phase * math.cos(math.pi * 0.5 - self.body.alt) * 0.01, 0 )
			#print(math.degrees(self.body.alt), math.degrees(self.body.az), self.body.phase, self.illumination_lut[i])
			utc_time_hours = float(i * LUT_INTERVAL_MINUTES) / 60
			
			#print("UTC " + str(utc_time_hours) + ", " + str(self.body.alt))
			if is_sun and is_morning and utc_time_hours > midday_utc_hours:
				# Skip the middle of the day
				is_morning = False
				g.date += ephem.minute* ((midday_hours_to_skip) * 60)
			if not is_sun or (utc_time_hours >= sunrise_time_offset_hours):
				g.date += ephem.minute*LUT_INTERVAL_MINUTES

	def Update(self):
		now = datetime.datetime.utcnow()

		# Make sure our look-up-table is for today's date
		today = now.date() # Start of today
		if today != self.look_up_table_date:
			self.computeTable(today)

		day_seconds = (now - datetime.datetime.combine(today, datetime.time())).seconds
		#print(str(day_seconds))
		day_fraction = float(day_seconds) / float(NUM_SECONDS_IN_A_DAY)
		#print(str(day_fraction))
		lut_entry = day_fraction * (NUM_LUT_ENTRIES - 1)
		lut_index = int(lut_entry)
		lut_fraction = lut_entry - lut_index
		self.elevation = self.elevation_lut[lut_index] * (1.0 - lut_fraction) + (self.elevation_lut[lut_index+1]) * lut_fraction
		self.illumination = self.illumination_lut[lut_index] * (1.0 - lut_fraction) + (self.illumination_lut[lut_index+1]) * lut_fraction

if __name__ == '__main__':
	sun = CelestialData('Sun')
	moon = CelestialData('Moon')
	print( 'Sun: ' + str(math.degrees(sun.elevation)) + ', ' + str(sun.illumination) )
	print( 'Moon: ' + str(math.degrees(moon.elevation)) + ', ' + str(moon.illumination) )


class CelestialController():
	def __init__(self):
		self.sun = CelestialData('Sun')
		self.moon = CelestialData('Moon')
		self.do_adhoc_updates = True

	def on_update(self, client):
		#print("Updating celestial controller")
		self.sun.Update()
		self.moon.Update()
