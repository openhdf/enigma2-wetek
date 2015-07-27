### Start XBMC
### check for space and whether installed
### main work done in enigma2.sh, here we do just a touch
### TODO: installation error checking is missing, network state...


from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
import os
#from Components.Ipkg import IpkgComponent
#from Screens.Ipkg import Ipkg
from enigma import quitMainloop
from Plugins.Extensions.StartXBMC.installsomething import InstallSomething



class StartXBMC(Screen):

	xbmc_name = "xbmc-amlogic"
	xbmcneeds = 200             # TODO: check real needs, more likely to be ~ 300MB
	caninstall = False
	isinstalled = False

	skin = """
		<screen position="150,200" size="450,200" title="Start XBMC" >
			<widget name="text" position="0,0" size="550,80" font="Regular;20" />
			<widget name="freespace_label" position="10,100" size="290,25" font="Regular;20" />
			<widget name="installed_label" position="10,125" size="290,25" font="Regular;20" />
			<widget name="freespace" position="300,100" size="50,25" font="Regular;20" />
			<widget name="installed" position="300,125" size="50,25" font="Regular;20" />
		</screen>"""
	def __init__(self, session, args = 0):
		self.session = session
		Screen.__init__(self, session)

		freemb = str(self.getFreeNand()) 
		isInstalled = str(self.isXBMCInstalled())

		self["text"] = Label(_("\n   Please press OK to start XBMC..."))
		self["freespace_label"] = Label(_("Free space in MB:"))
		self["installed_label"] = Label(_("XBMC installed:"))
		self["freespace"] = Label(freemb)
		self["installed"] = Label(isInstalled)

		self["actions"] = ActionMap(["OkCancelActions"],
		{
			"ok": self.ok,
			"cancel": self.close,
		})
		self.onShown.append(self.onFirstShown)   ### !!! A must to avoid modal crap 

	def onFirstShown(self):
		self.onShown.remove(self.onFirstShown)   ### avoid perpetual installs
		if (self.isinstalled):
			self["text"] = Label(_("\n   Please press OK to start XBMC..."))
			os.system("touch /etc/.xbmcstart")
		elif (self.caninstall is False):
			self["text"] = Label(_("\n  WARNING: \n  There is not enough space to install XBMC!"))
		else:
			self.session.openWithCallback(self.doInstallCallback, MessageBox, _("\n XBMC not present. Proceed with install?"))

### wo callback message is shown after install
#			self.session.open(MessageBox,_("\n XBMC not present, installing, please wait..."), MessageBox.TYPE_INFO, timeout = 5)
#			self["text"] = Label(_("\n XBMC not present, installing, please wait..."))
#			os.system("opkg install xbmc-amlogic")
#			os.system("touch /etc/.xbmcstart")
# Try more civilized download
#			self.XBMCInstallation = InstallSomething(self.session, self.xbmc_name)
#			self.XBMCInstallation.__install__()
#			self.isinstalled = True


	def doInstallCallback(self, result):
		if result:
			self.XBMCInstallation = InstallSomething(self.session, [self.xbmc_name])
			self.XBMCInstallation.__install__()
			self.isinstalled = True                 # actually very bad, we did not check for errors
			os.system("touch /etc/.xbmcstart")      # but enigma2.sh checks for /usr/bin/xbmc 


### TODO: touch(es) should go here
	def ok(self):
		if (self.isinstalled):
			quitMainloop(3)
		else:
			self.close()


### TODO: check portability (busybox vs coreutils)
	def getFreeNand(self):
		os.system('sync ; sync ; sync' )
		sizeread = os.popen("df | grep %s | tr -s ' '" % 'root')
		c = sizeread.read().strip().split(" ")
		sizeread.close()
		free = int(c[3])/1024
		if (free > self.xbmcneeds):
			self.caninstall = True
		else:
			self.caninstall = False
		return free  
		#hopefully returrn free MBs in NAND/uSD
		#self["lab_flash"].setText("%sB out of %sB" % (c[3], c[1]))
		#self["Used"].setText("Used: %s" % c[2])
		#self["Available"].setText("Available: %s" % c[3])
		#self["Use in %"].setText("Use: %s" % c[4])
		#self["Partition"].setText("Partition: %s" % c[0])

### not very clever...
	def isXBMCInstalled(self):
		if os.path.exists("/usr/bin/xbmc"):
			self.isinstalled = True
			return True
		else:
			self.isinstalled = False
			return False


### Not used at the moment
class SysMessage(Screen):
	skin = """
		<screen position="150,200" size="450,200" title="System Message" >
			<widget source="text" position="0,0" size="450,200" font="Regular;20" halign="center" valign="center" render="Label" />
			<ePixmap pixmap="icons/input_error.png" position="5,5" size="53,53" alphatest="on" />
		</screen>"""
	def __init__(self, session, message):
		from Components.Sources.StaticText import StaticText

		Screen.__init__(self, session)

		self["text"] = StaticText(message)

		self["actions"] = ActionMap(["OkCancelActions"],
		{
			"cancel": self.ok,
		})

	def ok(self):
		self.close()



### MENU service stuff
def main(session, **kwargs):
	session.open(StartXBMC)

def menu(menuid, **kwargs):
	if menuid == "mainmenu":
		return [(_("Start XBMC"), main, "start_xbmc", 44)]
	return []

def Plugins(**kwargs):
	return [
	PluginDescriptor(name = _("Start XBMC"), description = _("WeTek media player"), 	where = PluginDescriptor.WHERE_PLUGINMENU, icon = "xbmc.png", needsRestart = False, fnc = main),
	PluginDescriptor(name = _("Start XBMC"), description = _("Play back media files"), where = PluginDescriptor.WHERE_MENU, needsRestart = False, fnc = menu)
]
#	PluginDescriptor(name = _("StartXBMC"), description = _("Play back media files"), where = PluginDescriptor.WHERE_EXTENSIONSMENU, needsRestart = False, fnc = menu)



