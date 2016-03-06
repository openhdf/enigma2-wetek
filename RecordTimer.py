from boxbranding import getMachineBrand, getMachineName
from boxbranding import getMachineBrand, getMachineName
import xml.etree.cElementTree
from datetime import datetime
from time import localtime, strftime, ctime, time
from bisect import insort
from sys import maxint
import os

from enigma import eEPGCache, getBestPlayableServiceReference, eServiceReference, eServiceCenter, iRecordableService, quitMainloop, eActionMap, setPreferredTuner

from Components.config import config
from Components import Harddisk
from Components.UsageConfig import defaultMoviePath
from Components.SystemInfo import SystemInfo
from Components.TimerSanityCheck import TimerSanityCheck
import Components.RecordingConfig
from Screens.MessageBox import MessageBox
import Screens.Standby
from Tools import Directories, Notifications, ASCIItranslit, Trashcan
from Tools.XMLTools import stringToXML
import timer
import NavigationInstance
from ServiceReference import ServiceReference
from enigma import pNavigation


# ok, for descriptions etc we have:
# service reference	 (to get the service name)
# name				 (title)
# description		 (description)
# event data		 (ONLY for time adjustments etc.)

wasRecTimerWakeup = False
#+++
debug = False
#+++

#reset wakeup state after ending timer
def resetTimerWakeup():
	global wasRecTimerWakeup
	if os.path.exists("/tmp/was_rectimer_wakeup"):
		os.remove("/tmp/was_rectimer_wakeup")
		if debug: print "[RECORDTIMER] reset wakeup state"
	wasRecTimerWakeup = False

# parses an event and returns a (begin, end, name, duration, eit)-tuple.
# begin and end will be corrected
def parseEvent(ev, description = True):
	if description:
		name = ev.getEventName()
		description = ev.getShortDescription()
		if description == "":
			description = ev.getExtendedDescription()
	else:
		name = ""
		description = ""
	begin = ev.getBeginTime()
	end = begin + ev.getDuration()
	eit = ev.getEventId()
	begin -= config.recording.margin_before.value * 60
	end += config.recording.margin_after.value * 60
	return begin, end, name, description, eit

class AFTEREVENT:
	def __init__(self):
		pass

	NONE = 0
	STANDBY = 1
	DEEPSTANDBY = 2
	AUTO = 3

def findSafeRecordPath(dirname):
	if not dirname:
		return None
	dirname = os.path.realpath(dirname)
	mountpoint = Harddisk.findMountPoint(dirname)
	if not os.path.ismount(mountpoint):
		print '[RecordTimer] media is not mounted:', dirname
		return None
	if not os.path.isdir(dirname):
		try:
			os.makedirs(dirname)
		except Exception, ex:
			print '[RecordTimer] Failed to create dir "%s":' % dirname, ex
			return None
	return dirname

# type 1 = digital television service
# type 4 = nvod reference service (NYI)
# type 17 = MPEG-2 HD digital television service
# type 22 = advanced codec SD digital television
# type 24 = advanced codec SD NVOD reference service (NYI)
# type 25 = advanced codec HD digital television
# type 27 = advanced codec HD NVOD reference service (NYI)
# type 2 = digital radio sound service
# type 10 = advanced codec digital radio sound service

service_types_tv = '1:7:1:0:0:0:0:0:0:0:(type == 1) || (type == 17) || (type == 22) || (type == 25) || (type == 134) || (type == 195)'
service_types_radio = '1:7:2:0:0:0:0:0:0:0:(type == 2) || (type == 10)'

def getBqRootStr(ref):
	ref = ref.toString()
	if ref.startswith('1:0:2:'):           # we need that also?:----> or ref.startswith('1:0:10:'):
		service_types = service_types_radio
		if config.usage.multibouquet.value:
			bqrootstr = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.radio" ORDER BY bouquet'
		else:
			bqrootstr = '%s FROM BOUQUET "userbouquet.favourites.radio" ORDER BY bouquet'% service_types
	else:
		service_types = service_types_tv
		if config.usage.multibouquet.value:
			bqrootstr = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'
		else:
			bqrootstr = '%s FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet'% service_types

	return bqrootstr

# please do not translate log messages
class RecordTimerEntry(timer.TimerEntry, object):
	def __init__(self, serviceref, begin, end, name, description, eit, disabled = False, justplay = False, afterEvent = AFTEREVENT.AUTO, checkOldTimers = False, dirname = None, tags = None, descramble = 'notset', record_ecm = 'notset', rename_repeat = True, isAutoTimer = False, always_zap = False, MountPath = None):
		timer.TimerEntry.__init__(self, int(begin), int(end))
		if checkOldTimers:
			if self.begin < time() - 1209600:
				self.begin = int(time())

		if self.end < self.begin:
			self.end = self.begin

		assert isinstance(serviceref, ServiceReference)

		if serviceref and serviceref.isRecordable():
			self.service_ref = serviceref
		else:
			self.service_ref = ServiceReference(None)
		self.eit = eit
		self.dontSave = False
		self.name = name
		self.description = description
		self.disabled = disabled
		self.timer = None
		self.__record_service = None
		self.start_prepare = 0
		self.justplay = justplay
		self.always_zap = always_zap
		self.afterEvent = afterEvent
		self.dirname = dirname
		self.dirnameHadToFallback = False
		self.autoincrease = False
		self.autoincreasetime = 3600 * 24 # 1 day
		self.tags = tags or []
		self.MountPath = None
		self.messageString = ""
		self.messageStringShow = False
		self.messageBoxAnswerPending = False
		self.justTriedFreeingTuner = False

		if descramble == 'notset' and record_ecm == 'notset':
			if config.recording.ecm_data.value == 'descrambled+ecm':
				self.descramble = True
				self.record_ecm = True
			elif config.recording.ecm_data.value == 'scrambled+ecm':
				self.descramble = False
				self.record_ecm = True
			elif config.recording.ecm_data.value == 'normal':
				self.descramble = True
				self.record_ecm = False
		else:
			self.descramble = descramble
			self.record_ecm = record_ecm

		self.needChangePriorityFrontend = config.usage.recording_frontend_priority.value != "-2" and config.usage.recording_frontend_priority.value != config.usage.frontend_priority.value
		self.change_frontend = False
		self.setAdvancedPriorityFrontend = None
		if SystemInfo["DVB-T_priority_tuner_available"] or SystemInfo["DVB-C_priority_tuner_available"] or SystemInfo["DVB-S_priority_tuner_available"]:
			rec_ref = self.service_ref and self.service_ref.ref
			str_service = rec_ref and rec_ref.toString()
			if str_service and '%3a//' not in str_service and not str_service.rsplit(":", 1)[1].startswith("/"):
				type_service = rec_ref.getUnsignedData(4) >> 16
				if type_service == 0xEEEE:
					if SystemInfo["DVB-T_priority_tuner_available"] and config.usage.recording_frontend_priority_dvbt.value != "-2":
						if config.usage.recording_frontend_priority_dvbt.value != config.usage.frontend_priority.value:
							self.setAdvancedPriorityFrontend = config.usage.recording_frontend_priority_dvbt.value
				elif type_service == 0xFFFF:
					if SystemInfo["DVB-C_priority_tuner_available"] and config.usage.recording_frontend_priority_dvbc.value != "-2":
						if config.usage.recording_frontend_priority_dvbc.value != config.usage.frontend_priority.value:
							self.setAdvancedPriorityFrontend = config.usage.recording_frontend_priority_dvbc.value
				else:
					if SystemInfo["DVB-S_priority_tuner_available"] and config.usage.recording_frontend_priority_dvbs.value != "-2":
						if config.usage.recording_frontend_priority_dvbs.value != config.usage.frontend_priority.value:
							self.setAdvancedPriorityFrontend = config.usage.recording_frontend_priority_dvbs.value
		self.needChangePriorityFrontend = self.setAdvancedPriorityFrontend is not None or config.usage.recording_frontend_priority.value != "-2" and config.usage.recording_frontend_priority.value != config.usage.frontend_priority.value
		self.rename_repeat = rename_repeat
		self.isAutoTimer = isAutoTimer
		self.wasInStandby = False

		self.log_entries = []
		self.resetState()

	def __repr__(self):
		if not self.disabled:
			return "RecordTimerEntry(name=%s, begin=%s, serviceref=%s, justplay=%s, isAutoTimer=%s)" % (self.name, ctime(self.begin), self.service_ref, self.justplay, self.isAutoTimer)
		else:
			return "RecordTimerEntry(name=%s, begin=%s, serviceref=%s, justplay=%s, isAutoTimer=%s, Disabled)" % (self.name, ctime(self.begin), self.service_ref, self.justplay, self.isAutoTimer)

	def log(self, code, msg):
		self.log_entries.append((int(time()), code, msg))
		print "[TIMER]", msg

	def freespace(self):
		self.MountPath = None
		if not self.dirname:
			dirname = findSafeRecordPath(defaultMoviePath())
		else:
			dirname = findSafeRecordPath(self.dirname)
			if dirname is None:
				dirname = findSafeRecordPath(defaultMoviePath())
				self.dirnameHadToFallback = True
		if not dirname:
			return False

		self.MountPath = dirname
		mountwriteable = os.access(dirname, os.W_OK)
		if not mountwriteable:
			self.log(0, ("Mount '%s' is not writeable." % dirname))
			return False

		s = os.statvfs(dirname)
		if (s.f_bavail * s.f_bsize) / 1000000 < 1024:
			self.log(0, "Not enough free space to record")
			return False
		else:
			if debug:
				self.log(0, "Found enough free space to record")
			return True

	def calculateFilename(self):
		service_name = self.service_ref.getServiceName()
		begin_date = strftime("%Y%m%d %H%M", localtime(self.begin))

#		print "begin_date: ", begin_date
#		print "service_name: ", service_name
#		print "name:", self.name
#		print "description: ", self.description
#
		filename = begin_date + " - " + service_name
		if self.name:
			if config.recording.filename_composition.value == "veryveryshort":
				filename = self.name
			elif config.recording.filename_composition.value == "veryshort":
				filename = self.name + " - " + begin_date
			elif config.recording.filename_composition.value == "short":
				filename = strftime("%Y%m%d", localtime(self.begin)) + " - " + self.name
			elif config.recording.filename_composition.value == "long":
				filename += " - " + self.name + " - " + self.description
			else:
				filename += " - " + self.name # standard

		if config.recording.ascii_filenames.value:
			filename = ASCIItranslit.legacyEncode(filename)

		self.Filename = Directories.getRecordingFilename(filename, self.MountPath)
		if debug:
			self.log(0, "Filename calculated as: '%s'" % self.Filename)
		return self.Filename

	def tryPrepare(self):
		if self.justplay:
			return True
		else:
			if not self.calculateFilename():
				self.do_backoff()
				self.start_prepare = time() + self.backoff
				return False
			rec_ref = self.service_ref and self.service_ref.ref
			if rec_ref and rec_ref.flags & eServiceReference.isGroup:
				rec_ref = getBestPlayableServiceReference(rec_ref, eServiceReference())
				if not rec_ref:
					self.log(1, "'get best playable service for group... record' failed")
					return False

			self.setRecordingPreferredTuner()
			try:
				#not all images support recording type indicators
				self.record_service = rec_ref and NavigationInstance.instance.recordService(rec_ref,False,pNavigation.isRealRecording)
			except:
				self.record_service = rec_ref and NavigationInstance.instance.recordService(rec_ref)

			if not self.record_service:
				self.log(1, "'record service' failed")
				self.setRecordingPreferredTuner(setdefault=True)
				return False

			if self.repeated:
				epgcache = eEPGCache.getInstance()
				queryTime=self.begin+(self.end-self.begin)/2
				evt = epgcache.lookupEventTime(rec_ref, queryTime)
				if evt:
					self.description = evt.getShortDescription()
					if self.description == "":
						self.description = evt.getExtendedDescription()
					event_id = evt.getEventId()
				else:
					event_id = -1
			else:
				event_id = self.eit
				if event_id is None:
					event_id = -1

			prep_res=self.record_service.prepare(self.Filename + self.record_service.getFilenameExtension(), self.begin, self.end, event_id, self.name.replace("\n", ""), self.description.replace("\n", ""), ' '.join(self.tags), bool(self.descramble), bool(self.record_ecm))
			if prep_res:
				if prep_res == -255:
					self.log(4, "failed to write meta information")
				else:
					self.log(2, "'prepare' failed: error %d" % prep_res)

				# we must calc new start time before stopRecordService call because in Screens/Standby.py TryQuitMainloop tries to get
				# the next start time in evEnd event handler...
				self.do_backoff()
				self.start_prepare = time() + self.backoff

				NavigationInstance.instance.stopRecordService(self.record_service)
				self.record_service = None
				self.setRecordingPreferredTuner(setdefault=True)
				return False
			return True

	def do_backoff(self):
		if self.backoff == 0:
			self.backoff = 5
		else:
			self.backoff *= 2
			if self.backoff > 100:
				self.backoff = 100
		self.log(10, "backoff: retry in %d seconds" % self.backoff)

	def activate(self):
		global wasRecTimerWakeup
		if os.path.exists("/tmp/was_rectimer_wakeup") and not wasRecTimerWakeup:
			wasRecTimerWakeup = int(open("/tmp/was_rectimer_wakeup", "r").read()) and True or False

		next_state = self.state + 1
		if debug:
			self.log(5, "activating state %d" % next_state)

		# print "[TIMER] activate called",time(),next_state,self.first_try_prepare,' pending ',self.messageBoxAnswerPending,' justTried ',self.justTriedFreeingTuner,' show ',self.messageStringShow,self.messageString #TODO remove

		if next_state == self.StatePrepared:
			if self.messageBoxAnswerPending:
				self.start_prepare = time() + 1 # call again in 1 second
				return False

			if self.justTriedFreeingTuner:
				self.start_prepare = time() + 5 # tryPrepare in 5 seconds
				self.justTriedFreeingTuner = False
				return False

			if not self.justplay and not self.freespace():
				Notifications.AddPopup(text = _("Write error while recording. Disk full?\n%s") % self.name, type = MessageBox.TYPE_ERROR, timeout = 5, id = "DiskFullMessage")
				self.failed = True
				self.next_activation = time()
				self.end = time() + 5
				self.backoff = 0
				return True

			if self.always_zap:
				if Screens.Standby.inStandby:
					self.wasInStandby = True
					#eActionMap.getInstance().bindAction('', -maxint - 1, self.keypress)
					#set service to zap after standby
					Screens.Standby.inStandby.prev_running_service = self.service_ref.ref
					Screens.Standby.inStandby.paused_service = None
					#wakeup standby
					Screens.Standby.inStandby.Power()
					self.log(5, "wakeup and zap to recording service")
				else:
					cur_zap_ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
					if cur_zap_ref and not cur_zap_ref.getPath():# we do not zap away if it is no live service
						self.messageString += _("The TV was switched to the recording service!\n")
						self.messageStringShow = True
						self.setRecordingPreferredTuner()
						self.failureCB(True)
						self.log(5, "zap to recording service")

			if self.tryPrepare():
				if debug:
					self.log(6, "prepare ok, waiting for begin")
				if self.messageStringShow:
					Notifications.AddNotification(MessageBox, _("In order to record a timer, a tuner was freed successfully:\n\n") + self.messageString, type=MessageBox.TYPE_INFO, timeout=20)
				# create file to "reserve" the filename
				# because another recording at the same time on another service can try to record the same event
				# i.e. cable / sat.. then the second recording needs an own extension... when we create the file
				# here then calculateFilename is happy
				if not self.justplay:
					open(self.Filename + self.record_service.getFilenameExtension(), "w").close()
					# give the Trashcan a chance to clean up
					try:
						Trashcan.instance.cleanIfIdle()
					except Exception, e:
						print "[TIMER] Failed to call Trashcan.instance.cleanIfIdle()"
						print "[TIMER] Error:", e
				# fine. it worked, resources are allocated.
				self.next_activation = self.begin
				self.backoff = 0
				return True

			self.log(7, "prepare failed")
			if self.first_try_prepare == 0:
				# (0) try to make a tuner available by disabling PIP
				self.first_try_prepare += 1
				from Screens.InfoBar import InfoBar
				from Screens.InfoBarGenerics import InfoBarPiP
				from Components.ServiceEventTracker import InfoBarCount
				InfoBarInstance = InfoBarCount == 1 and InfoBar.instance
				if InfoBarInstance and InfoBarPiP.pipShown(InfoBarInstance) == True:
					if config.recording.ask_to_abort_pip.value == "ask":
						self.log(8, "asking user to disable PIP")
						self.messageBoxAnswerPending = True
						Notifications.AddNotificationWithCallback(self.failureCB_pip, MessageBox, _("A timer failed to record!\nDisable PIP and try again?\n"), timeout=20)
					elif config.recording.ask_to_abort_pip.value in ("abort_no_msg", "abort_msg"):
						self.log(8, "disable PIP without asking")
						self.setRecordingPreferredTuner()
						self.failureCB_pip(True)
					return False
				else:
					self.log(8, "currently no PIP active... so we dont need to stop it")

			if self.first_try_prepare == 1:
				# (1) try to make a tuner available by aborting pseudo recordings
				self.first_try_prepare += 1
				self.backoff = 0
				if len(NavigationInstance.instance.getRecordings(False,pNavigation.isPseudoRecording)) > 0:
					if config.recording.ask_to_abort_pseudo_rec.value == "ask":
						self.log(8, "asking user to abort pseudo recordings")
						self.messageBoxAnswerPending = True
						Notifications.AddNotificationWithCallback(self.failureCB_pseudo_rec, MessageBox, _("A timer failed to record!\nAbort pseudo recordings (e.g. EPG refresh) and try again?\n"), timeout=20)
					elif config.recording.ask_to_abort_pseudo_rec.value in ("abort_no_msg", "abort_msg"):
						self.log(8, "abort pseudo recordings without asking")
						self.setRecordingPreferredTuner()
						self.failureCB_pseudo_rec(True)
					return False
				else:
					self.log(8, "currently no pseudo recordings active... so we dont need to stop it")

			if self.first_try_prepare == 2:
				# (2) try to make a tuner available by aborting streaming
				self.first_try_prepare += 1
				self.backoff = 0
				if len(NavigationInstance.instance.getRecordings(False,pNavigation.isStreaming)) > 0:
					if config.recording.ask_to_abort_streaming.value == "ask":
						self.log(8, "asking user to abort streaming")
						self.messageBoxAnswerPending = True
						Notifications.AddNotificationWithCallback(self.failureCB_streaming, MessageBox, _("A timer failed to record!\nAbort streaming and try again?\n"), timeout=20)
					elif config.recording.ask_to_abort_streaming.value in ("abort_no_msg", "abort_msg"):
						self.log(8, "abort streaming without asking")
						self.setRecordingPreferredTuner()
						self.failureCB_streaming(True)
					return False
				else:
					self.log(8, "currently no streaming active... so we dont need to stop it")

			if self.first_try_prepare == 3:
				# (3) try to make a tuner available by switching live TV to the recording service
				self.first_try_prepare += 1
				self.backoff = 0
				cur_ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
				if cur_ref and not cur_ref.getPath():
					if Screens.Standby.inStandby:
						self.setRecordingPreferredTuner()
						self.failureCB(True)
					elif not config.recording.asktozap.value:
						self.log(8, "asking user to zap away")
						self.messageBoxAnswerPending = True
						Notifications.AddNotificationWithCallback(self.failureCB, MessageBox, _("A timer failed to record!\nDisable TV and try again?\n"), timeout=20)
					else: # zap without asking
						self.log(9, "zap without asking")
						self.setRecordingPreferredTuner()
						self.failureCB(True)
					return False
				elif cur_ref:
					self.log(8, "currently running service is not a live service.. so stopping it makes no sense")
				else:
					self.log(8, "currently no service running... so we dont need to stop it")

			if self.first_try_prepare == 4:
				# (4) freeing a tuner failed
				self.first_try_prepare += 1
				self.log(8, "freeing a tuner failed")
				if self.messageString:
					Notifications.AddNotification(MessageBox, _("No tuner is available for recording a timer!\n\nThe following methods of freeing a tuner were tried without success:\n\n") + self.messageString, type=MessageBox.TYPE_INFO, timeout=20)
				else:
					Notifications.AddNotification(MessageBox, _("No tuner is available for recording a timer!\n"), type=MessageBox.TYPE_INFO, timeout=20)

			return False

		elif next_state == self.StateRunning:

			# if this timer has been cancelled, just go to "end" state.
			if self.cancelled:
				return True

			if self.failed:
				return True

			if self.justplay:
				if Screens.Standby.inStandby:
					self.wasInStandby = True
					#eActionMap.getInstance().bindAction('', -maxint - 1, self.keypress)
					self.log(11, "wakeup and zap")
					#set service to zap after standby
					Screens.Standby.inStandby.prev_running_service = self.service_ref.ref
					Screens.Standby.inStandby.paused_service = None
					#wakeup standby
					Screens.Standby.inStandby.Power()
				else:
					self.log(11, "zapping")
					found = False
					notFound = False
					NavigationInstance.instance.isMovieplayerActive()
					from Screens.ChannelSelection import ChannelSelection
					ChannelSelectionInstance = ChannelSelection.instance
					if ChannelSelectionInstance:
						bqrootstr = getBqRootStr(self.service_ref.ref)
						rootstr = ''
						serviceHandler = eServiceCenter.getInstance()
						rootbouquet = eServiceReference(bqrootstr)
						bouquet = eServiceReference(bqrootstr)
						bouquetlist = serviceHandler.list(bouquet)
						# we need a way out of the loop,
						# if channel is not in bouquets
						bouquetcount = 0
						bouquets = []
						if not bouquetlist is None:
							while True:
								bouquet = bouquetlist.getNext()
								# can we make it easier?
								# or found a way to make another way for that
								if bouquets == []:
									bouquets.append(bouquet)
								else:
									for x in bouquets:
										if x != bouquet:
											bouquets.append(bouquet)
										else:
											bouquetcount += 1
								if bouquetcount >= 5:
									notFound = True
									break

								if bouquet.flags & eServiceReference.isDirectory:
									ChannelSelectionInstance.clearPath()
									ChannelSelectionInstance.setRoot(bouquet)
									servicelist = serviceHandler.list(bouquet)
									if not servicelist is None:
										serviceIterator = servicelist.getNext()
										while serviceIterator.valid():
											if self.service_ref.ref == serviceIterator:
												break
											serviceIterator = servicelist.getNext()
										if self.service_ref.ref == serviceIterator:
											break
							if found:
								ChannelSelectionInstance.enterPath(rootbouquet)
								ChannelSelectionInstance.enterPath(bouquet)
								ChannelSelectionInstance.saveRoot()
								ChannelSelectionInstance.saveChannel(self.service_ref.ref)
						if found:
							ChannelSelectionInstance.addToHistory(self.service_ref.ref)
					if notFound:
						# Can we get a result for that ?
						# see if you want to delete the running Timer
						self.switchToAll()
					else:
						NavigationInstance.instance.playService(self.service_ref.ref)
				return True
			else:
				self.log(11, "start recording")
				record_res = self.record_service.start()
				self.setRecordingPreferredTuner(setdefault=True)
				if record_res:
					self.log(13, "start record returned %d" % record_res)
					self.do_backoff()
					# retry
					self.begin = time() + self.backoff
					return False
				return True

		elif next_state == self.StateEnded or next_state == self.StateFailed:
			old_end = self.end
			if self.setAutoincreaseEnd():
				self.log(12, "autoincrease recording %d minute(s)" % int((self.end - old_end)/60))
				self.state -= 1
				return True
			if self.justplay:
				self.log(12, "end zapping")
			else:
				self.log(12, "stop recording")
			if not self.justplay:
				if self.record_service:
					NavigationInstance.instance.stopRecordService(self.record_service)
					self.record_service = None

			NavigationInstance.instance.RecordTimer.saveTimer()
			self.autostate = Screens.Standby.inStandby
			minRT = self.end - self.begin > 3 # do not switch to standby/deepstandby, when timer ended and timer runtime is less than 3s (e.g. zap-timer without end time) -> currently obsolete (timer edit set AFTEREVENT.NONE if time difference < 1 mins)
			isRecordTime = abs(NavigationInstance.instance.RecordTimer.getNextRecordingTime() - time()) <= 900 or NavigationInstance.instance.RecordTimer.getStillRecording()
			if debug: print "[RECORDTIMER] self.autostate=%s" % self.autostate, "wasRecTimerWakeup=%s" % wasRecTimerWakeup, "self.wasInStandby=%s" % self.wasInStandby, "self.afterEvent=%s" % self.afterEvent, "minRT=%s" % minRT

			if self.afterEvent == AFTEREVENT.STANDBY or (self.afterEvent == AFTEREVENT.AUTO and self.wasInStandby and (not wasRecTimerWakeup or (wasRecTimerWakeup and isRecordTime))):
				if not Screens.Standby.inStandby: # not already in standby
					Notifications.AddNotificationWithCallback(self.sendStandbyNotification, MessageBox, _("A finished record timer wants to set your\n%s %s to standby. Do that now?") % (getMachineBrand(), getMachineName()), timeout = 180)

			if isRecordTime or abs(NavigationInstance.instance.RecordTimer.getNextZapTime() - time()) <= 900:
				if self.afterEvent == AFTEREVENT.DEEPSTANDBY or (wasRecTimerWakeup and self.afterEvent == AFTEREVENT.AUTO and self.wasInStandby) or (self.afterEvent == AFTEREVENT.AUTO and wasRecTimerWakeup):
					print '[Timer] Recording or Recording due is next 15 mins, not return to deepstandby'
				self.wasInStandby = False
				return True
			elif abs(NavigationInstance.instance.PowerTimer.getNextPowerManagerTime() - time()) <= 900 or NavigationInstance.instance.PowerTimer.isProcessing(exceptTimer = 0):
				if self.afterEvent == AFTEREVENT.DEEPSTANDBY or (wasRecTimerWakeup and self.afterEvent == AFTEREVENT.AUTO and self.wasInStandby) or (self.afterEvent == AFTEREVENT.AUTO and wasRecTimerWakeup):
					print '[Timer] PowerTimer due is next 15 mins or is actual currently active, not return to deepstandby'
				self.wasInStandby = False
				resetTimerWakeup()
				return True

			if self.afterEvent == AFTEREVENT.DEEPSTANDBY or (wasRecTimerWakeup and self.afterEvent == AFTEREVENT.AUTO and self.wasInStandby):
				if not Screens.Standby.inTryQuitMainloop: # no shutdown messagebox is open
					if Screens.Standby.inStandby: # in standby
						print "[RecordTimer] quitMainloop #1"
						quitMainloop(1)
					else:
						Notifications.AddNotificationWithCallback(self.sendTryQuitMainloopNotification, MessageBox, _("A finished record timer wants to shut down\nyour %s %s. Shutdown now?") % (getMachineBrand(), getMachineName()), default = True, timeout = 180)
			elif self.afterEvent == AFTEREVENT.AUTO and wasRecTimerWakeup:
				if not Screens.Standby.inTryQuitMainloop: # no shutdown messagebox is open
					if Screens.Standby.inStandby: # in standby
						print "[RecordTimer] quitMainloop #2"
						quitMainloop(1)

			self.wasInStandby = False
			resetTimerWakeup()
			return True

	def keypress(self, key=None, flag=1):
		if flag and self.wasInStandby:
			self.wasInStandby = False
			eActionMap.getInstance().unbindAction('', self.keypress)

	def setAutoincreaseEnd(self, entry = None):
		if not self.autoincrease:
			return False
		if entry is None:
			new_end =  int(time()) + self.autoincreasetime
		else:
			new_end = entry.begin -30

		dummyentry = RecordTimerEntry(self.service_ref, self.begin, new_end, self.name, self.description, self.eit, disabled=True, justplay = self.justplay, afterEvent = self.afterEvent, dirname = self.dirname, tags = self.tags)
		dummyentry.disabled = self.disabled
		timersanitycheck = TimerSanityCheck(NavigationInstance.instance.RecordTimer.timer_list, dummyentry)
		if not timersanitycheck.check():
			simulTimerList = timersanitycheck.getSimulTimerList()
			if simulTimerList is not None and len(simulTimerList) > 1:
				new_end = simulTimerList[1].begin
				new_end -= 30				# allow 30 seconds for prepare
		if new_end <= time():
			return False
		self.end = new_end
		return True

	def setRecordingPreferredTuner(self, setdefault=False):
		if self.needChangePriorityFrontend:
			elem = None
			if not self.change_frontend and not setdefault:
				elem = (self.setAdvancedPriorityFrontend is not None and self.setAdvancedPriorityFrontend) or config.usage.recording_frontend_priority.value
				self.change_frontend = True
			elif self.change_frontend and setdefault:
				elem = config.usage.frontend_priority.value
				self.change_frontend = False
				self.setAdvancedPriorityFrontend = None
			if elem is not None:
				setPreferredTuner(int(elem))

	def sendStandbyNotification(self, answer):
		if answer:
			Notifications.AddNotification(Screens.Standby.Standby)

	def sendTryQuitMainloopNotification(self, answer):
		if answer:
			Notifications.AddNotification(Screens.Standby.TryQuitMainloop, 1)

	def getNextActivation(self, getNextStbPowerOn = False):
		self.isStillRecording = False
		next_state = self.state + 1
		if getNextStbPowerOn:
			if next_state == 3:
				self.isStillRecording = True
				next_day = 0
				count_day = 0
				wd_timer = datetime.fromtimestamp(self.begin).isoweekday()*-1
				wd_repeated = bin(128+int(self.repeated))

				for s in range(wd_timer-1,-8,-1):
					count_day +=1
					if int(wd_repeated[s]):
						next_day = s
						break
				if next_day == 0:
					for s in range(-1,wd_timer-1,-1):
						count_day +=1
						if int(wd_repeated[s]):
							next_day = s
							break
				#return self.begin + 86400 * count_day
				return self.start_prepare + 86400 * count_day
			elif next_state == 2:
				return self.begin
			elif next_state == 1:
				return self.start_prepare
			else:
				return -1

		if self.state == self.StateEnded or self.state == self.StateFailed:
			if self.end > time():
				self.isStillRecording = True
			return self.end
		if next_state == self.StateEnded or next_state == self.StateFailed:
			if self.end > time():
				self.isStillRecording = True
		return {self.StatePrepared: self.start_prepare,
				self.StateRunning: self.begin,
				self.StateEnded: self.end}[next_state]

	def failureCB_pip(self, answer):
		if answer:
			self.log(13, "ok, disable PIP")
			from Screens.InfoBar import InfoBar
			from Screens.InfoBarGenerics import InfoBarPiP
			from Components.ServiceEventTracker import InfoBarCount
			InfoBarInstance = InfoBarCount == 1 and InfoBar.instance
			if InfoBarInstance:
				InfoBarPiP.showPiP(InfoBarInstance)
				self.messageString += _("Disabled PIP.\n")
			else:
				self.log(14, "tried to disable PIP, suddenly found no InfoBar.instance")
				self.messageString += _("Tried to disable PIP, suddenly found no InfoBar.instance.\n")
			if config.recording.ask_to_abort_pip.value in ("ask", "abort_msg"):
				self.messageStringShow = True
			self.justTriedFreeingTuner = True
		else:
			self.log(14, "user didn't want to disable PIP, try other methods of freeing a tuner")
		self.messageBoxAnswerPending = False

	def failureCB_pseudo_rec(self, answer):
		if answer:
			self.log(13, "ok, abort pseudo recordings")
			for rec in NavigationInstance.instance.getRecordings(False,pNavigation.isPseudoRecording):
				NavigationInstance.instance.stopRecordService(rec)
				self.messageString += _("Aborted a pseudo recording.\n")
			if config.recording.ask_to_abort_pseudo_rec.value in ("ask", "abort_msg"):
				self.messageStringShow = True
			self.justTriedFreeingTuner = True
		else:
			self.log(14, "user didn't want to abort pseudo recordings, try other methods of freeing a tuner")
		self.messageBoxAnswerPending = False

	def failureCB_streaming(self, answer):
		if answer:
			self.log(13, "ok, abort streaming")
			for rec in NavigationInstance.instance.getRecordings(False,pNavigation.isStreaming):
				NavigationInstance.instance.stopRecordService(rec)
				self.messageString += _("Aborted a streaming service.\n")
			if config.recording.ask_to_abort_streaming.value in ("ask", "abort_msg"):
				self.messageStringShow = True
			self.justTriedFreeingTuner = True
		else:
			self.log(14, "user didn't want to abort streaming, try other methods of freeing a tuner")
		self.messageBoxAnswerPending = False

	def failureCB(self, answer):
		if answer:
			self.log(13, "ok, zapped away")
			self.messageString += _("The TV was switched to the recording service!\n")
			self.messageStringShow = True
			found = False
			notFound = False
			#NavigationInstance.instance.stopUserServices()
			from Screens.ChannelSelection import ChannelSelection
			ChannelSelectionInstance = ChannelSelection.instance
			if ChannelSelectionInstance:
				bqrootstr = getBqRootStr(self.service_ref.ref)
				rootstr = ''
				serviceHandler = eServiceCenter.getInstance()
				rootbouquet = eServiceReference(bqrootstr)
				bouquet = eServiceReference(bqrootstr)
				bouquetlist = serviceHandler.list(bouquet)
				# we need a way out of the loop,
				# if channel is not in bouquets
				bouquetcount = 0
				bouquets = []
				if not bouquetlist is None:
					while True:
						bouquet = bouquetlist.getNext()
						# can we make it easier?
						# or found a way to make another way for that
						if bouquets == []:
							bouquets.append(bouquet)
						else:
							for x in bouquets:
								if x != bouquet:
									bouquets.append(bouquet)
								else:
									bouquetcount += 1
						if bouquetcount >= 5:
							notFound = True
							break

						if bouquet.flags & eServiceReference.isDirectory:
							ChannelSelectionInstance.clearPath()
							ChannelSelectionInstance.setRoot(bouquet)
							servicelist = serviceHandler.list(bouquet)
							if not servicelist is None:
								serviceIterator = servicelist.getNext()
								while serviceIterator.valid():
									if self.service_ref.ref == serviceIterator:
										found = True
										break
									serviceIterator = servicelist.getNext()
								if self.service_ref.ref == serviceIterator:
									found = True
									break
					if found:
						ChannelSelectionInstance.enterPath(rootbouquet)
						ChannelSelectionInstance.enterPath(bouquet)
						ChannelSelectionInstance.saveRoot()
						ChannelSelectionInstance.saveChannel(self.service_ref.ref)
				if found:
					ChannelSelectionInstance.addToHistory(self.service_ref.ref)
			if notFound:
				# Can we get a result for that ?
				# see if you want to delete the running Timer
				self.switchToAll()
			else:
				NavigationInstance.instance.playService(self.service_ref.ref)
			self.justTriedFreeingTuner = True
		else:
			self.log(14, "user didn't want to zap away, record will probably fail")
		self.messageBoxAnswerPending = False

	def switchToAll(self):
		refStr = self.service_ref.ref.toString()
		from Screens.InfoBar import InfoBar
		if refStr.startswith('1:0:2:'):
			if InfoBar.instance.servicelist.mode != 1:
				InfoBar.instance.servicelist.setModeRadio()
				InfoBar.instance.servicelist.radioTV = 1
			InfoBar.instance.servicelist.clearPath()
			rootbouquet = eServiceReference('1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.radio" ORDER BY bouquet')
			bouquet = eServiceReference('%s ORDER BY name'% service_types_radio)
		else:
			if InfoBar.instance.servicelist.mode != 0:
				InfoBar.instance.servicelist.setModeTV()
				InfoBar.instance.servicelist.radioTV = 0
			InfoBar.instance.servicelist.clearPath()
			rootbouquet = eServiceReference('1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet')
			bouquet = eServiceReference('%s ORDER BY name'% service_types_tv)
		if InfoBar.instance.servicelist.bouquet_root != rootbouquet:
			InfoBar.instance.servicelist.bouquet_root = rootbouquet
		InfoBar.instance.servicelist.enterPath(bouquet)
		InfoBar.instance.servicelist.setCurrentSelection(self.service_ref.ref)
		InfoBar.instance.servicelist.zap(enable_pipzap = True)
		InfoBar.instance.servicelist.correctChannelNumber()
		InfoBar.instance.servicelist.startRoot = bouquet
		InfoBar.instance.servicelist.addToHistory(self.service_ref.ref)

	def timeChanged(self):
		old_prepare = self.start_prepare
		self.start_prepare = self.begin - self.prepare_time
		self.backoff = 0

		if int(old_prepare) > 60 and int(old_prepare) != int(self.start_prepare):
			self.log(15, "record time changed, start prepare is now: %s" % ctime(self.start_prepare))

	def gotRecordEvent(self, record, event):
		# TODO: this is not working (never true), please fix. (comparing two swig wrapped ePtrs)
		if self.__record_service.__deref__() != record.__deref__():
			return
		# self.log(16, "record event %d" % event)
		if event == iRecordableService.evRecordWriteError:
			print "WRITE ERROR on recording, disk full?"
			# show notification. the 'id' will make sure that it will be
			# displayed only once, even if more timers are failing at the
			# same time. (which is very likely in case of disk fullness)
			Notifications.AddPopup(text = _("Write error while recording. Disk full?\n"), type = MessageBox.TYPE_ERROR, timeout = 0, id = "DiskFullMessage")
			# ok, the recording has been stopped. we need to properly note
			# that in our state, with also keeping the possibility to re-try.
			# TODO: this has to be done.
		elif event == iRecordableService.evStart:
			text = _("A recording has been started:\n%s") % self.name
			notify = config.usage.show_message_when_recording_starts.value and not Screens.Standby.inStandby
			if self.dirnameHadToFallback:
				text = '\n'.join((text, _("Please note that the previously selected media could not be accessed and therefore the default directory is being used instead.")))
				notify = True
			if notify:
				Notifications.AddPopup(text = text, type = MessageBox.TYPE_INFO, timeout = 3)
		elif event == iRecordableService.evRecordAborted:
			NavigationInstance.instance.RecordTimer.removeEntry(self)
		elif event == iRecordableService.evGstRecordEnded:
			if self.repeated:
				self.processRepeated(findRunningEvent = False)
			NavigationInstance.instance.RecordTimer.doActivate(self)

	# we have record_service as property to automatically subscribe to record service events
	def setRecordService(self, service):
		if self.__record_service is not None:
#			print "[remove callback]"
			NavigationInstance.instance.record_event.remove(self.gotRecordEvent)

		self.__record_service = service

		if self.__record_service is not None:
#			print "[add callback]"
			NavigationInstance.instance.record_event.append(self.gotRecordEvent)

	record_service = property(lambda self: self.__record_service, setRecordService)

def createTimer(xml):
	begin = int(xml.get("begin"))
	end = int(xml.get("end"))
	serviceref = ServiceReference(xml.get("serviceref").encode("utf-8"))
	description = xml.get("description").encode("utf-8")
	repeated = xml.get("repeated").encode("utf-8")
	disabled = long(xml.get("disabled") or "0")
	justplay = long(xml.get("justplay") or "0")
	always_zap = long(xml.get("always_zap") or "0")
	afterevent = str(xml.get("afterevent") or "nothing")
	afterevent = {
		"nothing": AFTEREVENT.NONE,
		"standby": AFTEREVENT.STANDBY,
		"deepstandby": AFTEREVENT.DEEPSTANDBY,
		"auto": AFTEREVENT.AUTO
		}[afterevent]
	eit = xml.get("eit")
	if eit and eit != "None":
		eit = long(eit)
	else:
		eit = None
	location = xml.get("location")
	if location and location != "None":
		location = location.encode("utf-8")
	else:
		location = None
	tags = xml.get("tags")
	if tags and tags != "None":
		tags = tags.encode("utf-8").split(' ')
	else:
		tags = None
	descramble = int(xml.get("descramble") or "1")
	record_ecm = int(xml.get("record_ecm") or "0")
	isAutoTimer = int(xml.get("isAutoTimer") or "0")

	name = xml.get("name").encode("utf-8")
	#filename = xml.get("filename").encode("utf-8")
	entry = RecordTimerEntry(serviceref, begin, end, name, description, eit, disabled, justplay, afterevent, dirname = location, tags = tags, descramble = descramble, record_ecm = record_ecm, isAutoTimer = isAutoTimer, always_zap = always_zap)
	entry.repeated = int(repeated)

	for l in xml.findall("log"):
		time = int(l.get("time"))
		code = int(l.get("code"))
		msg = l.text.strip().encode("utf-8")
		entry.log_entries.append((time, code, msg))

	return entry

class RecordTimer(timer.Timer):
	def __init__(self):
		timer.Timer.__init__(self)

		self.Filename = Directories.resolveFilename(Directories.SCOPE_CONFIG, "timers.xml")

		try:
			self.loadTimer()
		except IOError:
			print "unable to load timers from file!"

	def doActivate(self, w):
		# when activating a timer which has already passed,
		# simply abort the timer. don't run through all the stages.
		if w.shouldSkip():
			w.state = RecordTimerEntry.StateEnded
		else:
			# when active returns true, this means "accepted".
			# otherwise, the current state is kept.
			# the timer entry itself will fix up the delay then.
			if w.activate():
				w.state += 1

		try:
			self.timer_list.remove(w)
		except:
			print '[RecordTimer]: Remove list failed'

		# did this timer reach the last state?
		if w.state < RecordTimerEntry.StateEnded:
			# no, sort it into active list
			insort(self.timer_list, w)
		else:
			# yes. Process repeated, and re-add.
			if w.repeated:
				w.processRepeated()
				w.state = RecordTimerEntry.StateWaiting
				w.first_try_prepare = 0 # changed from a bool to a counter, not renamed for compatibility with openWebif
				w.messageBoxAnswerPending = False
				w.justTriedFreeingTuner = False
				w.messageString = "" # incremental MessageBox string
				w.messageStringShow = False
				self.addTimerEntry(w)
			else:
				# check for disabled timers, if time has passed set to completed.
				self.cleanupDisabled()
				# remove old timers as set in config
				self.cleanupDaily(config.recording.keep_timers.value)
				insort(self.processed_timers, w)
		self.stateChanged(w)

	def isRecTimerWakeup(self):
		global wasRecTimerWakeup
		if os.path.exists("/tmp/was_rectimer_wakeup"):
			wasRecTimerWakeup = int(open("/tmp/was_rectimer_wakeup", "r").read()) and True or False
		else:
			wasRecTimerWakeup = False
		return wasRecTimerWakeup

	def isRecording(self):
		isRunning = False
		for timer in self.timer_list:
			if timer.isRunning() and not timer.justplay:
				isRunning = True
				break
		return isRunning

	def loadTimer(self):
		# TODO: PATH!
		if not Directories.fileExists(self.Filename):
			return
		try:
			file = open(self.Filename, 'r')
			doc = xml.etree.cElementTree.parse(file)
			file.close()
		except SyntaxError:
			from Tools.Notifications import AddPopup
			from Screens.MessageBox import MessageBox

			AddPopup(_("The timer file (timers.xml) is corrupt and could not be loaded."), type = MessageBox.TYPE_ERROR, timeout = 0, id = "TimerLoadFailed")

			print "timers.xml failed to load!"
			try:
				os.rename(self.Filename, self.Filename + "_old")
			except (IOError, OSError):
				print "renaming broken timer failed"
			return
		except IOError:
			print "timers.xml not found!"
			return

		root = doc.getroot()

		# put out a message when at least one timer overlaps
		checkit = True
		for timer in root.findall("timer"):
			newTimer = createTimer(timer)
			if (self.record(newTimer, ignoreTSC=True, dosave=False) is not None) and checkit:
				from Tools.Notifications import AddPopup
				from Screens.MessageBox import MessageBox
				timer_text = _("\nTimer '%s' disabled!") % newTimer.name
				AddPopup(_("Timer overlap in timers.xml detected!\nPlease recheck it!") + timer_text, type = MessageBox.TYPE_ERROR, timeout = 0, id = "TimerLoadFailed")
				checkit = False # at moment it is enough when the message is displayed one time

	def saveTimer(self):
		list = ['<?xml version="1.0" ?>\n', '<timers>\n']

		for timer in self.timer_list + self.processed_timers:
			if timer.dontSave:
				continue
			list.append('<timer')
			list.append(' begin="' + str(int(timer.begin)) + '"')
			list.append(' end="' + str(int(timer.end)) + '"')
			list.append(' serviceref="' + stringToXML(str(timer.service_ref)) + '"')
			list.append(' repeated="' + str(int(timer.repeated)) + '"')
			list.append(' name="' + str(stringToXML(timer.name)) + '"')
			list.append(' description="' + str(stringToXML(timer.description)) + '"')
			list.append(' afterevent="' + str(stringToXML({
				AFTEREVENT.NONE: "nothing",
				AFTEREVENT.STANDBY: "standby",
				AFTEREVENT.DEEPSTANDBY: "deepstandby",
				AFTEREVENT.AUTO: "auto"
				}[timer.afterEvent])) + '"')
			if timer.eit is not None:
				list.append(' eit="' + str(timer.eit) + '"')
			if timer.dirname is not None:
				list.append(' location="' + str(stringToXML(timer.dirname)) + '"')
			if timer.tags is not None:
				list.append(' tags="' + str(stringToXML(' '.join(timer.tags))) + '"')
			list.append(' disabled="' + str(int(timer.disabled)) + '"')
			list.append(' justplay="' + str(int(timer.justplay)) + '"')
			list.append(' always_zap="' + str(int(timer.always_zap)) + '"')
			list.append(' descramble="' + str(int(timer.descramble)) + '"')
			list.append(' record_ecm="' + str(int(timer.record_ecm)) + '"')
			list.append(' isAutoTimer="' + str(int(timer.isAutoTimer)) + '"')
			list.append('>\n')

			for time, code, msg in timer.log_entries:
				list.append('<log')
				list.append(' code="' + str(code) + '"')
				list.append(' time="' + str(time) + '"')
				list.append('>')
				list.append(str(stringToXML(msg)))
				list.append('</log>\n')

			list.append('</timer>\n')

		list.append('</timers>\n')

		file = open(self.Filename + ".writing", "w")
		for x in list:
			file.write(x)
		file.flush()

		os.fsync(file.fileno())
		file.close()
		os.rename(self.Filename + ".writing", self.Filename)

	def getNextZapTime(self):
		now = time()
		for timer in self.timer_list:
			if not timer.justplay or timer.begin < now:
				continue
			return timer.begin
		return -1

	def getStillRecording(self):
		isStillRecording = False
		now = time()
		for timer in self.timer_list:
			if timer.isStillRecording:
				isStillRecording = True
				break
			elif abs(timer.begin - now) <= 10 and not abs(timer.end - now) <= 10:
				isStillRecording = True
				break
		return isStillRecording

	def getNextRecordingTimeOld(self, getNextStbPowerOn = False):
		now = time()
		if getNextStbPowerOn:
			save_act = -1, 0
			for timer in self.timer_list:
				next_act = timer.getNextActivation(getNextStbPowerOn)
				if timer.justplay or next_act < now:
					continue
				if debug: print "[recordtimer] next stb power up", strftime("%a, %Y/%m/%d %H:%M", localtime(next_act))
				if save_act[0] == -1:
					save_act = next_act, int(not timer.always_zap)
				else:
					if next_act < save_act[0]:
						save_act = next_act, int(not timer.always_zap)
			return save_act
		else:
			for timer in self.timer_list:
				next_act = timer.getNextActivation()
				if timer.justplay or next_act < now:
					continue
				return next_act
		return -1

	def getNextRecordingTime(self, getNextStbPowerOn = False):
		#getNextStbPowerOn = True returns tuple -> (timer.begin, set standby)
		nextrectime = self.getNextRecordingTimeOld(getNextStbPowerOn)
		faketime = time()+300

		if getNextStbPowerOn:
			if config.timeshift.isRecording.value:
				if 0 < nextrectime[0] < faketime:
					return nextrectime
				else:
					return faketime, 0
			else:
				return nextrectime
		else:
			if config.timeshift.isRecording.value:
				if 0 < nextrectime < faketime:
					return nextrectime
				else:
					return faketime
			else:
				return nextrectime

	def isNextRecordAfterEventActionAuto(self):
		for timer in self.timer_list:
			# all types needed True for ident in Navigation.py
			return True
			if timer.justplay:
				continue
			if timer.afterEvent == AFTEREVENT.AUTO or timer.afterEvent == AFTEREVENT.DEEPSTANDBY:
				return True
		return False

	def record(self, entry, ignoreTSC=False, dosave=True): # wird von loadTimer mit dosave=False aufgerufen
		timersanitycheck = TimerSanityCheck(self.timer_list,entry)
		answer = None
		if not timersanitycheck.check():
			if not ignoreTSC:
				print "[RecordTimer] timer conflict detected!"
				print timersanitycheck.getSimulTimerList()
				return timersanitycheck.getSimulTimerList()
			else:
				print "[RecordTimer] ignore timer conflict..."
				if not dosave:
					entry.disabled = True
					answer = timersanitycheck.getSimulTimerList()
		elif timersanitycheck.doubleCheck():
			print "[RecordTimer] ignore double timer..."
			return None
		entry.timeChanged()
		print "[Timer] Record " + str(entry)
		entry.Timer = self
		self.addTimerEntry(entry)
		if dosave:
			self.saveTimer()
		return answer

	def isInTimer(self, eventid, begin, duration, service):
		returnValue = None
		type = 0
		time_match = 0

		isAutoTimer = False
		bt = None
		check_offset_time = not config.recording.margin_before.value and not config.recording.margin_after.value
		end = begin + duration
		refstr = ':'.join(service.split(':')[:11])
		for x in self.timer_list:
			if x.isAutoTimer == 1:
				isAutoTimer = True
			else:
				isAutoTimer = False
			check = ':'.join(x.service_ref.ref.toString().split(':')[:11]) == refstr
			if not check:
				sref = x.service_ref.ref
				parent_sid = sref.getUnsignedData(5)
				parent_tsid = sref.getUnsignedData(6)
				if parent_sid and parent_tsid:
					# check for subservice
					sid = sref.getUnsignedData(1)
					tsid = sref.getUnsignedData(2)
					sref.setUnsignedData(1, parent_sid)
					sref.setUnsignedData(2, parent_tsid)
					sref.setUnsignedData(5, 0)
					sref.setUnsignedData(6, 0)
					check = sref.toCompareString() == refstr
					num = 0
					if check:
						check = False
						event = eEPGCache.getInstance().lookupEventId(sref, eventid)
						num = event and event.getNumOfLinkageServices() or 0
					sref.setUnsignedData(1, sid)
					sref.setUnsignedData(2, tsid)
					sref.setUnsignedData(5, parent_sid)
					sref.setUnsignedData(6, parent_tsid)
					for cnt in range(num):
						subservice = event.getLinkageService(sref, cnt)
						if sref.toCompareString() == subservice.toCompareString():
							check = True
							break
			if check:
				timer_end = x.end
				timer_begin = x.begin
				type_offset = 0
				if not x.repeated and check_offset_time:
					if 0 < end - timer_end <= 59:
						timer_end = end
					elif 0 < timer_begin - begin <= 59:
						timer_begin = begin
				if x.justplay:
					type_offset = 5
					if (timer_end - x.begin) <= 1:
						timer_end += 60
				if x.always_zap:
					type_offset = 10

				if x.repeated != 0:
					if bt is None:
						bt = localtime(begin)
						bday = bt.tm_wday
						begin2 = 1440 + bt.tm_hour * 60 + bt.tm_min
						end2 = begin2 + duration / 60
					xbt = localtime(x.begin)
					xet = localtime(timer_end)
					offset_day = False
					checking_time = x.begin < begin or begin <= x.begin <= end
					if xbt.tm_yday != xet.tm_yday:
						oday = bday - 1
						if oday == -1: oday = 6
						offset_day = x.repeated & (1 << oday)
					xbegin = 1440 + xbt.tm_hour * 60 + xbt.tm_min
					xend = xbegin + ((timer_end - x.begin) / 60)
					if xend < xbegin:
						xend += 1440
					if x.repeated & (1 << bday) and checking_time:
						if begin2 < xbegin <= end2:
							if xend < end2:
								# recording within event
								time_match = (xend - xbegin) * 60
								type = type_offset + 3
							else:
								# recording last part of event
								time_match = (end2 - xbegin) * 60
								type = type_offset + 1
						elif xbegin <= begin2 <= xend:
							if xend < end2:
								# recording first part of event
								time_match = (xend - begin2) * 60
								type = type_offset + 4
							else:
								# recording whole event
								time_match = (end2 - begin2) * 60
								type = type_offset + 2
						elif offset_day:
							xbegin -= 1440
							xend -= 1440
							if begin2 < xbegin <= end2:
								if xend < end2:
									# recording within event
									time_match = (xend - xbegin) * 60
									type = type_offset + 3
								else:
									# recording last part of event
									time_match = (end2 - xbegin) * 60
									type = type_offset + 1
							elif xbegin <= begin2 <= xend:
								if xend < end2:
									# recording first part of event
									time_match = (xend - begin2) * 60
									type = type_offset + 4
								else:
									# recording whole event
									time_match = (end2 - begin2) * 60
									type = type_offset + 2
					elif offset_day and checking_time:
						xbegin -= 1440
						xend -= 1440
						if begin2 < xbegin <= end2:
							if xend < end2:
								# recording within event
								time_match = (xend - xbegin) * 60
								type = type_offset + 3
							else:
								# recording last part of event
								time_match = (end2 - xbegin) * 60
								type = type_offset + 1
						elif xbegin <= begin2 <= xend:
							if xend < end2:
								# recording first part of event
								time_match = (xend - begin2) * 60
								type = type_offset + 4
							else:
								# recording whole event
								time_match = (end2 - begin2) * 60
								type = type_offset + 2
				else:
					if begin < timer_begin <= end:
						if timer_end < end:
							# recording within event
							time_match = timer_end - timer_begin
							type = type_offset + 3
						else:
							# recording last part of event
							time_match = end - timer_begin
							type = type_offset + 1
					elif timer_begin <= begin <= timer_end:
						if timer_end < end:
							# recording first part of event
							time_match = timer_end - begin
							type = type_offset + 4
							if x.justplay:
								type = type_offset + 2
						else: # recording whole event
							time_match = end - begin
							type = type_offset + 2

				if time_match:
					returnValue = (time_match, type, isAutoTimer)
					if type in (2,7,12): # when full recording do not look further
						break
		return returnValue

	def removeEntry(self, entry):
		print "[Timer] Remove " + str(entry)

		# avoid re-enqueuing
		entry.repeated = False

		# abort timer.
		# this sets the end time to current time, so timer will be stopped.
		entry.autoincrease = False
		entry.abort()

		if entry.state != entry.StateEnded:
			self.timeChanged(entry)

#		print "state: ", entry.state
#		print "in processed: ", entry in self.processed_timers
#		print "in running: ", entry in self.timer_list
		# autoincrease instanttimer if possible
		if not entry.dontSave:
			for x in self.timer_list:
				if x.setAutoincreaseEnd():
					self.timeChanged(x)
		# now the timer should be in the processed_timers list. remove it from there.
		self.processed_timers.remove(entry)
		self.saveTimer()

	def shutdown(self):
		self.saveTimer()
