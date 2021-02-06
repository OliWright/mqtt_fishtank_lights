import math
import json

def componentAdd(a,b):
	return min( a+b, 255 )

class RgbWW():
	def __init__(self, r, g, b, w0, w1=0):
		self.r = r
		self.g = g
		self.b = b
		self.w0 = w0
		self.w1 = w1

	def __add__(self, other):
		return RgbWW( componentAdd(self.r, other.r), componentAdd(self.g, other.g), componentAdd(self.b, other.b), componentAdd(self.w0, other.w0), componentAdd(self.w1, other.w1) )

	def mul(self, other):
		return RgbWW( self.r * other, self.g * other, self.b * other, self.w0 * other, self.w1 * other )

	@classmethod
	def lerp(cls, a, b, fraction):
		w0 = a.w0 + ((b.w0 - a.w0) * fraction)
		w1 = a.w1 + ((b.w1 - a.w1) * fraction)
		r = a.r + ((b.r - a.r) * fraction)
		g = a.g + ((b.g - a.g) * fraction)
		b = a.b + ((b.b - a.b) * fraction)
		return RgbWW(r, g, b, w0, w1)

	def __str__(self):
		return '(' + str(self.r) + ', ' + str(self.g) + ', ' + str(self.b) + ', ' + str(self.w0) + ', ' + str(self.w1) + ')'

class ColourSample():
	def __init__(self, elevation, colour):
		self.elevation = float(elevation)
		self.colour = colour

class ColourTable():
	def __init__(self, name, num_scale = 1):
		self.name = name
		self.num_scale = num_scale
		self.file_name = '/home/oli/src/mqtt_devices/fishtank_lights/' + name + '.json'
		with open(self.file_name) as data_file:
			data = json.load(data_file)
		data_samples = data['samples']
		self.samples = []
		for sample in data_samples:
			self.samples.append(ColourSample(sample['el'], RgbWW( sample['r'] / num_scale, sample['g'] / num_scale, sample['b'] / num_scale, sample['w0'] / num_scale, sample['w1'] / num_scale)))
		lightning_colour = data['lightning_colour']
		self.lightning_colour = RgbWW(lightning_colour['r'] / num_scale, lightning_colour['g'] / num_scale, lightning_colour['b'] / num_scale, lightning_colour['w0'] / num_scale, lightning_colour['w1'] / num_scale)

	def save():
		data_samples = []
		for sample in self.samples:
			data_samples.append( {'el' : sample.elevation, 'r' : sample.colour.r * self.num_scale, 'g' : sample.colour.g * self.num_scale, 'b' : sample.colour.b * self.num_scale, 'w0' : sample.colour.w0 * self.num_scale, 'w1' : sample.colour.w1 * self.num_scale} )
		data = {}
		data['name'] = self.name
		data['samples'] = data_samples
		f = open(self.file_name, 'w')
		f.write(json.dumps(data, sort_keys=False, indent=4, separators=(',', ': ')))
		f.close()

	def lookupColour(self, elevation):
		previous_sample = None
		elevation = math.degrees(elevation)
		for sample in self.samples:
			if sample.elevation >= elevation:
				if previous_sample is None:
					return sample.colour
				else:
					fraction = (elevation - previous_sample.elevation) / (sample.elevation - previous_sample.elevation)
					return RgbWW.lerp(previous_sample.colour, sample.colour, fraction)
			previous_sample = sample
		return self.samples[len(self.samples)-1].colour
