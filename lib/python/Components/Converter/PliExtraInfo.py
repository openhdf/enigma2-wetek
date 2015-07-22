# shamelessly copied from pliExpertInfo (Vali, Mirakels, Littlesat)

from os import path
from enigma import iServiceInformation, iPlayableService
from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.config import config
from Tools.Transponder import ConvertToHumanReadable
from Tools.GetEcmInfo import GetEcmInfo
from Poll import Poll
from Components.Converter.ChannelNumbers import channelnumbers

def addspace(text):
	if text:
		text += "  "
	return text

class PliExtraInfo(Poll, Converter, object):
	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = type
		self.poll_interval = 1000
		self.poll_enabled = True
		self.caid_data = (
			( "0x100",  "0x1ff", "Seca",     "S",  True  ),
			( "0x500",  "0x5ff", "Via",      "V",  True  ),
			( "0x600",  "0x6ff", "Irdeto",   "I",  True  ),
			( "0x900",  "0x9ff", "NDS",      "Nd", True  ),
			( "0xb00",  "0xbff", "Conax",    "Co", True  ),
			( "0xd00",  "0xdff", "CryptoW",  "Cw", True  ),
			( "0xe00",  "0xeff", "PowerVU",  "P",  False ),
			("0x1700", "0x17ff", "Beta",     "B",  True  ),
			("0x1800", "0x18ff", "Nagra",    "N",  True  ),
			("0x2600", "0x2600", "Biss",     "Bi", False ),
			("0x4ae0", "0x4ae1", "Dre",      "D",  False ),
			("0x4aee", "0x4aee", "BulCrypt", "B1", False ),
			("0x5581", "0x5581", "BulCrypt", "B2", False )
		)
		self.ca_table = (
			("CryptoCaidSecaAvailable",	"S",	False),
			("CryptoCaidViaAvailable",	"V",	False),
			("CryptoCaidIrdetoAvailable",	"I",	False),
			("CryptoCaidNDSAvailable",	"Nd",	False),
			("CryptoCaidConaxAvailable",	"Co",	False),
			("CryptoCaidCryptoWAvailable",	"Cw",	False),
			("CryptoCaidPowerVUAvailable",	"P",	False),
			("CryptoCaidBetaAvailable",	"B",	False),
			("CryptoCaidNagraAvailable",	"N",	False),
			("CryptoCaidBissAvailable",	"Bi",	False),
			("CryptoCaidDreAvailable",	"D",	False),
			("CryptoCaidBulCrypt1Available","B1",	False),
			("CryptoCaidBulCrypt2Available","B2",	False),
			("CryptoCaidSecaSelected",	"S",	True),
			("CryptoCaidViaSelected",	"V",	True),
			("CryptoCaidIrdetoSelected",	"I",	True),
			("CryptoCaidNDSSelected",	"Nd",	True),
			("CryptoCaidConaxSelected",	"Co",	True),
			("CryptoCaidCryptoWSelected",	"Cw",	True),
			("CryptoCaidPowerVUSelected",	"P",	True),
			("CryptoCaidBetaSelected",	"B",	True),
			("CryptoCaidNagraSelected",	"N",	True),
			("CryptoCaidBissSelected",	"Bi",	True),
			("CryptoCaidDreSelected",	"D",	True),
			("CryptoCaidBulCrypt1Selected",	"B1",	True),
			("CryptoCaidBulCrypt2Selected",	"B2",	True),
		)
		self.ecmdata = GetEcmInfo()
		self.feraw = self.fedata = self.updateFEdata = None

	def getCryptoInfo(self, info):
		if info.getInfo(iServiceInformation.sIsCrypted) == 1:
			data = self.ecmdata.getEcmData()
			self.current_source = data[0]
			self.current_caid = data[1]
			self.current_provid = data[2]
			self.current_ecmpid = data[3]
		else:
			self.current_source = ""
			self.current_caid = "0"
			self.current_provid = "0"
			self.current_ecmpid = "0"

	def createCryptoBar(self, info):
		res = ""
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)

		for caid_entry in self.caid_data:
			if int(caid_entry[0], 16) <= int(self.current_caid, 16) <= int(caid_entry[1], 16):
				color="\c0000??00"
			else:
				color = "\c007?7?7?"
				try:
					for caid in available_caids:
						if int(caid_entry[0], 16) <= caid <= int(caid_entry[1], 16):
							color="\c00????00"
				except:
					pass

			if color != "\c007?7?7?" or caid_entry[4]:
				if res: res += " "
				res += color + caid_entry[3]

		res += "\c00??????"
		return res

	def createCryptoSeca(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x100', 16) <= int(self.current_caid, 16) <= int('0x1ff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0x100', 16) <= caid <= int('0x1ff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'S'
		res += "\c00??????"
		return res

	def createCryptoVia(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x500', 16) <= int(self.current_caid, 16) <= int('0x5ff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0x500', 16) <= caid <= int('0x5ff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'V'
		res += "\c00??????"
		return res

	def createCryptoIrdeto(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x600', 16) <= int(self.current_caid, 16) <= int('0x6ff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0x600', 16) <= caid <= int('0x6ff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'I'
		res += "\c00??????"
		return res

	def createCryptoNDS(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x900', 16) <= int(self.current_caid, 16) <= int('0x9ff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0x900', 16) <= caid <= int('0x9ff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'NDS'
		res += "\c00??????"
		return res

	def createCryptoConax(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0xb00', 16) <= int(self.current_caid, 16) <= int('0xbff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0xb00', 16) <= caid <= int('0xbff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'CO'
		res += "\c00??????"
		return res

	def createCryptoCryptoW(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0xd00', 16) <= int(self.current_caid, 16) <= int('0xdff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0xd00', 16) <= caid <= int('0xdff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'CW'
		res += "\c00??????"
		return res

	def createCryptoPowerVU(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0xe00', 16) <= int(self.current_caid, 16) <= int('0xeff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0xe00', 16) <= caid <= int('0xeff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'P'
		res += "\c00??????"
		return res

	def createCryptoBeta(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x1700', 16) <= int(self.current_caid, 16) <= int('0x17ff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0x1700', 16) <= caid <= int('0x17ff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'B'
		res += "\c00??????"
		return res

	def createCryptoNagra(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x1800', 16) <= int(self.current_caid, 16) <= int('0x18ff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0x1800', 16) <= caid <= int('0x18ff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'N'
		res += "\c00??????"
		return res

	def createCryptoBiss(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x2600', 16) <= int(self.current_caid, 16) <= int('0x26ff', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0x2600', 16) <= caid <= int('0x26ff', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'BI'
		res += "\c00??????"
		return res

	def createCryptoDre(self, info):
		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
		if int('0x4ae0', 16) <= int(self.current_caid, 16) <= int('0x4ae1', 16):
			color="\c004c7d3f"
		else:
			color = "\c009?9?9?"
			try:
				for caid in available_caids:
					if int('0x4ae0', 16) <= caid <= int('0x4ae1', 16):
						color="\c00eeee00"
			except:
				pass
		res = color + 'DC'
		res += "\c00??????"
		return res

	def createCryptoSpecial(self, info):
		caid_name = "FTA"
		try:
			for caid_entry in self.caid_data:
				if int(caid_entry[0], 16) <= int(self.current_caid, 16) <= int(caid_entry[1], 16):
					caid_name = caid_entry[2]
					break
			return caid_name + ":%04x:%04x:%04x" % (int(self.current_caid,16), int(self.current_provid,16), info.getInfo(iServiceInformation.sSID))
		except:
			pass
		return ""

	def createResolution(self, info):
		video_height = 0
		video_width = 0
		video_pol = " "
		video_rate = 0
		if path.exists("/proc/stb/vmpeg/0/yres"):
			f = open("/proc/stb/vmpeg/0/yres", "r")
			try:
				video_height = int(f.read(),16)
			except:
				pass
			f.close()
		if path.exists("/proc/stb/vmpeg/0/xres"):
			f = open("/proc/stb/vmpeg/0/xres", "r")
			try:
				video_width = int(f.read(),16)
			except:
				pass
			f.close()
		if path.exists("/proc/stb/vmpeg/0/progressive"):
			f = open("/proc/stb/vmpeg/0/progressive", "r")
			try:
				video_pol = "p" if int(f.read(),16) else "i"
			except:
				pass
			f.close()
		if path.exists("/proc/stb/vmpeg/0/framerate"):
			f = open("/proc/stb/vmpeg/0/framerate", "r")
			try:
				video_rate = int(f.read())
			except:
				pass
			f.close()

		fps  = str((video_rate + 500) / 1000)
		return str(video_width) + "x" + str(video_height) + video_pol + fps

	def createVideoCodec(self, info):
		return ("MPEG2", "MPEG4", "MPEG1", "MPEG4-II", "VC1", "VC1-SM", "")[info.getInfo(iServiceInformation.sVideoType)]

	def createPIDInfo(self, info):
		vpid = info.getInfo(iServiceInformation.sVideoPID)
		apid = info.getInfo(iServiceInformation.sAudioPID)
		pcrpid = info.getInfo(iServiceInformation.sPCRPID)
		sidpid = info.getInfo(iServiceInformation.sSID)
		tsid = info.getInfo(iServiceInformation.sTSID)
		onid = info.getInfo(iServiceInformation.sONID)
		if vpid < 0 : vpid = 0
		if apid < 0 : apid = 0
		if pcrpid < 0 : pcrpid = 0
		if sidpid < 0 : sidpid = 0
		if tsid < 0 : tsid = 0
		if onid < 0 : onid = 0
		return "%d-%d:%05d:%04d:%04d:%04d" % (onid, tsid, sidpid, vpid, apid, pcrpid)

	def createTransponderInfo(self, fedata, feraw):
		if not feraw:
			return ""
		elif "DVB-T" in feraw.get("tuner_type"):
			tmp = addspace(self.createChannelNumber(fedata, feraw)) + addspace(self.createFrequency(feraw)) + addspace(self.createPolarization(fedata))
		else:
			tmp = addspace(self.createFrequency(feraw)) + addspace(self.createPolarization(fedata))
		return addspace(self.createTunerSystem(fedata)) + tmp + addspace(self.createSymbolRate(fedata, feraw)) + addspace(self.createFEC(fedata, feraw)) \
			+ addspace(self.createModulation(fedata)) + addspace(self.createOrbPos(feraw))

	def createFrequency(self, fedata):
		frequency = fedata.get("frequency")
		if frequency:
			return str(frequency)
		return ""

	def createChannelNumber(self, fedata, feraw):
		return "DVB-T" in feraw.get("tuner_type") and fedata.get("channel") or ""

	def createSymbolRate(self, fedata, feraw):
		if "DVB-T" in feraw.get("tuner_type"):
			bandwidth = fedata.get("bandwidth")
			if bandwidth:
				return bandwidth
		else:
			symbolrate = fedata.get("symbol_rate")
			if symbolrate:
				return str(symbolrate)
		return ""

	def createPolarization(self, fedata):
		return fedata.get("polarization_abbreviation") or ""

	def createFEC(self, fedata, feraw):
		if "DVB-T" in feraw.get("tuner_type"):
			code_rate_lp = fedata.get("code_rate_lp")
			code_rate_hp = fedata.get("code_rate_hp")
			if code_rate_lp and code_rate_hp:
				return code_rate_lp + "-" + code_rate_hp
		else:
			fec = fedata.get("fec_inner")
			if fec:
				return fec
		return ""

	def createModulation(self, fedata):
		if fedata.get("tuner_type") == _("Terrestrial"):
			constellation = fedata.get("constellation")
			if constellation:
				return constellation
		else:
			modulation = fedata.get("modulation")
			if modulation:
				return modulation
		return ""

	def createTunerType(self, feraw):
		return feraw.get("tuner_type") or ""

	def createTunerSystem(self, fedata):
		return fedata.get("system") or ""

	def createOrbPos(self, feraw):
		orbpos = feraw.get("orbital_position")
		if orbpos > 1800:
			return str((float(3600 - orbpos)) / 10.0) + "\xc2\xb0 W"
		elif orbpos > 0:
			return str((float(orbpos)) / 10.0) + "\xc2\xb0 E"
		return ""

	def createOrbPosOrTunerSystem(self, fedata,feraw):
		orbpos = self.createOrbPos(feraw)
		if orbpos is not "":
			return orbpos
		return self.createTunerSystem(fedata)

	def createTransponderName(self,feraw):
		freq = feraw.get("frequency")
		c_band = False
		if freq and freq < 10700000:
			c_band = True

		orb_pos = ""
		orbpos = feraw.get("orbital_position")
		if orbpos > 1800:
			if c_band:
				orbpos += 1
			if orbpos == 3592:
				orb_pos = 'Thor/Intelsat'
			elif orbpos == 3560:
				orb_pos = 'Amos'
			elif orbpos == 3550:
				orb_pos = 'Eutelsat 5W'
			elif orbpos == 3530:
				orb_pos = 'Nilesat/Eutelsat 7W'
			elif orbpos == 3520:
				orb_pos = 'Eutelsat 8W'
			elif orbpos == 3490:
				orb_pos = 'Express 11W'
			elif orbpos == 3475:
				orb_pos = 'Eutelsat 12.5W'
			elif orbpos == 3460:
				orb_pos = 'Express 14W'
			elif orbpos == 3450:
				orb_pos = 'Telstar 15W'
			elif orbpos == 3420:
				orb_pos = 'Intelsat 18W'
			elif orbpos == 3400:
				orb_pos = 'NSS 20W'
			elif orbpos == 3380:
				orb_pos = 'SES 22W'
			elif orbpos == 3355:
				orb_pos = 'Intelsat 24.5W'
			elif orbpos == 3325:
				orb_pos = 'Intelsat 27.5W'
			elif orbpos == 3300:
				orb_pos = 'Hispasat'
			elif orbpos == 3285:
				orb_pos = 'Intelsat 31.5W'
			elif orbpos == 3255:
				orb_pos = 'Intelsat 34.5W'
			elif orbpos == 3225:
				orb_pos = 'NSS/Telstar 37W'
			elif orbpos == 3195:
				orb_pos = 'SES 40.5W'
			elif orbpos == 3169:
				orb_pos = 'Intelsat 43.1W'
			elif orbpos == 3150:
				orb_pos = 'Intelsat 45W'
			elif orbpos == 3100:
				orb_pos = 'Intelsat 50W'
			elif orbpos == 3070:
				orb_pos = 'Intelsat 53W'
			elif orbpos == 3045:
				orb_pos = 'Intelsat 55.5W'
			elif orbpos == 3020:
				orb_pos = 'Intelsat 58W'
			elif orbpos == 2990:
				orb_pos = 'Amazonas'
			elif orbpos == 2985:
				orb_pos = 'Echostar 61.5W'
			elif orbpos == 2900:
				orb_pos = 'Star One'
			elif orbpos == 2880:
				orb_pos = 'AMC 72W'
			elif orbpos == 2830:
				orb_pos = 'Echostar/QuetzSat'
			elif orbpos == 2780:
				orb_pos = 'NIMIQ 82W'
			elif orbpos == 2690:
				orb_pos = 'NIMIQ 91W'
			elif orbpos == 2630:
				orb_pos = 'Galaxy 97W'
			elif orbpos == 2500:
				orb_pos = 'Echostar/DirectTV 110W'
			elif orbpos == 2410:
				orb_pos = 'Echostar/DirectTV 119W'
			elif orbpos == 2390:
				orb_pos = 'Echostar/Galaxy 121W'
			elif orbpos == 2310:
				orb_pos = 'Ciel'
			elif c_band:
				orb_pos = str((float(3600 - orbpos)) / 10.0) + "W C-band"
			else:
				orb_pos = str((float(3600 - orbpos)) / 10.0) + "W"
		elif orbpos > 0:
			if c_band:
				orbpos -= 1
			if orbpos == 130:
				orb_pos = 'Hot Bird'
			elif orbpos == 192:
				orb_pos = 'Astra 1KR/1L/1M/1N'
			elif orbpos == 235:
				orb_pos = 'Astra 3'
			elif orbpos == 1100:
				orb_pos = 'BSat/NSAT'
			elif orbpos == 1105:
				orb_pos = 'ChinaSat'
			elif orbpos == 1130:
				orb_pos = 'KoreaSat'
			elif orbpos == 1440:
				orb_pos = 'SuperBird'
			elif orbpos == 1005:
				orb_pos = 'AsiaSat 100E'
			elif orbpos == 1030:
				orb_pos = 'Express 103E'
			elif orbpos == 1055:
				orb_pos = 'Asiasat 105E'
			elif orbpos == 1082:
				orb_pos = 'NSS/SES 108E'
			elif orbpos == 880:
				orb_pos = 'ST2'
			elif orbpos == 900:
				orb_pos = 'Yamal 90E'
			elif orbpos == 915:
				orb_pos = 'Mesat'
			elif orbpos == 950:
				orb_pos = 'NSS/SES 95E'
			elif orbpos == 765:
				orb_pos = 'Apstar'
			elif orbpos == 785:
				orb_pos = 'ThaiCom'
			elif orbpos == 800:
				orb_pos = 'Express 80E'
			elif orbpos == 830:
				orb_pos = 'Insat'
			elif orbpos == 851:
				orb_pos = 'Intelsat/Horizons'
			elif orbpos == 750:
				orb_pos = 'ABS'
			elif orbpos == 720:
				orb_pos = 'Intelsat 72E'
			elif orbpos == 705:
				orb_pos = 'Eutelsat 70.5E'
			elif orbpos == 685:
				orb_pos = 'Intelsat 68.5E'
			elif orbpos == 620:
				orb_pos = 'Intelsat 902'
			elif orbpos == 600:
				orb_pos = 'Intelsat 904'
			elif orbpos == 570:
				orb_pos = 'NSS 57E'
			elif orbpos == 530:
				orb_pos = 'Express 53E'
			elif orbpos == 490:
				orb_pos = 'Yamal 49E'
			elif orbpos == 480:
				orb_pos = 'Afghansat'
			elif orbpos == 450:
				orb_pos = 'Intelsat 45E'
			elif orbpos == 420:
				orb_pos = 'Turksat'
			elif orbpos == 400:
				orb_pos = 'Express 40E'
			elif orbpos == 390:
				orb_pos = 'Hellas Sat'
			elif orbpos == 380:
				orb_pos = 'Paksat'
			elif orbpos == 360:
				orb_pos = 'Eutelsat 36E'
			elif orbpos == 330:
				orb_pos = 'Eutelsat 33E'
			elif orbpos == 315:
				orb_pos = 'Astra 5'
			elif orbpos == 305:
				orb_pos = 'Arabsat 30.5E'
			elif orbpos == 282:
				orb_pos = 'Astra 2E/2F/2G'
			elif orbpos == 1222:
				orb_pos = 'AsiaSat 122E'
			elif orbpos == 1380:
				orb_pos = 'Telstar 18'
			elif orbpos == 260:
				orb_pos = 'Badr 4/5/6'
			elif orbpos == 255:
				orb_pos = 'Eutelsat 25.5E'
			elif orbpos == 215:
				orb_pos = 'Eutelsat 21.5E'
			elif orbpos == 200:
				orb_pos = 'Arabsat 20E'
			elif orbpos == 160:
				orb_pos = 'Eutelsat 16E'
			elif orbpos == 100:
				orb_pos = 'Eutelsat 10E'
			elif orbpos == 90:
				orb_pos = 'Eutelsat 9E'
			elif orbpos == 70:
				orb_pos = 'Eutelsat 7E'
			elif orbpos == 48:
				orb_pos = 'SES 5'
			elif orbpos == 30:
				orb_pos = 'Rascom/Eutelsat 3E'
			elif c_band:
				orb_pos = str((float(orbpos)) / 10.0) + "E C-band"
			else:
				orb_pos = str((float(orbpos)) / 10.0) + "E"
		return orb_pos

	def createProviderName(self,info):
		return info.getInfoString(iServiceInformation.sProvider)

	@cached
	def getText(self):
		service = self.source.service
		if service is None:
			return ""
		info = service and service.info()

		if not info:
			return ""

		if self.type == "CryptoInfo":
			self.getCryptoInfo(info)
			if int(config.usage.show_cryptoinfo.value) > 0:
				return addspace(self.createCryptoBar(info)) + self.createCryptoSpecial(info)
			else:
				return addspace(self.createCryptoBar(info)) + addspace(self.current_source) + self.createCryptoSpecial(info)

		if self.type == "CryptoBar":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoBar(info)
			else:
				return ""

		if self.type == "CryptoSeca":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoSeca(info)
			else:
				return ""

		if self.type == "CryptoVia":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoVia(info)
			else:
				return ""

		if self.type == "CryptoIrdeto":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoIrdeto(info)
			else:
				return ""

		if self.type == "CryptoNDS":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoNDS(info)
			else:
				return ""

		if self.type == "CryptoConax":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoConax(info)
			else:
				return ""

		if self.type == "CryptoCryptoW":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoCryptoW(info)
			else:
				return ""

		if self.type == "CryptoBeta":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoBeta(info)
			else:
				return ""

		if self.type == "CryptoNagra":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoNagra(info)
			else:
				return ""

		if self.type == "CryptoBiss":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoBiss(info)
			else:
				return ""

		if self.type == "CryptoDre":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoDre(info)
			else:
				return ""

		if self.type == "CryptoSpecial":
			if int(config.usage.show_cryptoinfo.value) > 0:
				self.getCryptoInfo(info)
				return self.createCryptoSpecial(info)
			else:
				return ""

		if self.type == "ResolutionString":
			return self.createResolution(info)

		if self.type == "VideoCodec":
			return self.createVideoCodec(info)

		if self.updateFEdata:
			feinfo = service.frontendInfo()
			if feinfo:
				self.feraw = feinfo.getAll(config.usage.infobar_frontend_source.value == "settings")
				if self.feraw:
					self.fedata = ConvertToHumanReadable(self.feraw)

		feraw = self.feraw
		if not feraw:
			feraw = info.getInfoObject(iServiceInformation.sTransponderData)
			fedata = ConvertToHumanReadable(feraw)
		else:
			fedata = self.fedata
		if self.type == "All":
			self.getCryptoInfo(info)
			if int(config.usage.show_cryptoinfo.value) > 0:
				return addspace(self.createProviderName(info)) + self.createTransponderInfo(fedata,feraw) + addspace(self.createTransponderName(feraw)) + "\n"\
				+ addspace(self.createCryptoBar(info)) + addspace(self.createCryptoSpecial(info)) + "\n"\
				+ addspace(self.createPIDInfo(info)) + addspace(self.createVideoCodec(info)) + self.createResolution(info)
			else:
				return addspace(self.createProviderName(info)) + self.createTransponderInfo(fedata,feraw) + addspace(self.createTransponderName(feraw)) + "\n" \
				+ addspace(self.createCryptoBar(info)) + self.current_source + "\n" \
				+ addspace(self.createCryptoSpecial(info)) + addspace(self.createVideoCodec(info)) + self.createResolution(info)

		if self.type == "ServiceInfo":
			return addspace(self.createProviderName(info)) + addspace(self.createTunerSystem(fedata)) + addspace(self.createFrequency(feraw)) + addspace(self.createPolarization(fedata)) \
			+ addspace(self.createSymbolRate(fedata, feraw)) + addspace(self.createFEC(fedata, feraw)) + addspace(self.createModulation(fedata)) + addspace(self.createOrbPos(feraw)) + addspace(self.createTransponderName(feraw))\
			+ addspace(self.createVideoCodec(info)) + self.createResolution(info)

		if self.type == "TransponderInfo2line":
			return addspace(self.createProviderName(info)) + addspace(self.createTunerSystem(fedata)) + addspace(self.createTransponderName(feraw)) + '\n'\
			+ addspace(self.createFrequency(fedata)) + addspace(self.createPolarization(fedata))\
			+ addspace(self.createSymbolRate(fedata, feraw)) + self.createModulation(fedata) + '-' + addspace(self.createFEC(fedata, feraw))

		if self.type == "TransponderInfo":
			return self.createTransponderInfo(fedata, feraw)

		if self.type == "TransponderFrequency":
			return self.createFrequency(feraw)

		if self.type == "TransponderSymbolRate":
			return self.createSymbolRate(fedata, feraw)

		if self.type == "TransponderPolarization":
			return self.createPolarization(fedata)

		if self.type == "TransponderFEC":
			return self.createFEC(fedata, feraw)

		if self.type == "TransponderModulation":
			return self.createModulation(fedata)

		if self.type == "OrbitalPosition":
			return self.createOrbPos(feraw)

		if self.type == "TunerType":
			return self.createTunerType(feraw)

		if self.type == "TunerSystem":
			return self.createTunerSystem(fedata)

		if self.type == "OrbitalPositionOrTunerSystem":
			return self.createOrbPosOrTunerSystem(fedata,feraw)

		if self.type == "PIDInfo":
			return self.createPIDInfo(info)

		if self.type == "TerrestrialChannelNumber":
			return self.createChannelNumber(fedata, feraw)

		return _("invalid type")

	text = property(getText)

	@cached
	def getBool(self):
		service = self.source.service
		info = service and service.info()

		if not info:
			return False

		request_caid = None
		for x in self.ca_table:
			if x[0] == self.type:
				request_caid = x[1]
				request_selected = x[2]
				break

		if request_caid is None:
			return False

		if info.getInfo(iServiceInformation.sIsCrypted) != 1:
			return False

		data = self.ecmdata.getEcmData()

		if data is None:
			return False

		current_caid	= data[1]

		available_caids = info.getInfoObject(iServiceInformation.sCAIDs)

		for caid_entry in self.caid_data:
			if caid_entry[3] == request_caid:
				if request_selected:
					if int(caid_entry[0], 16) <= int(current_caid, 16) <= int(caid_entry[1], 16):
						return True
				else: # request available
					try:
						for caid in available_caids:
							if int(caid_entry[0], 16) <= caid <= int(caid_entry[1], 16):
								return True
					except:
						pass

		return False

	boolean = property(getBool)

	def changed(self, what):
		if what[0] == self.CHANGED_SPECIFIC:
			self.updateFEdata = False
			if what[1] == iPlayableService.evNewProgramInfo:
				self.updateFEdata = True
			if what[1] == iPlayableService.evEnd:
				self.feraw = self.fedata = None
			Converter.changed(self, what)
		elif what[0] == self.CHANGED_POLL and self.updateFEdata is not None:
			self.updateFEdata = False
			Converter.changed(self, what)
