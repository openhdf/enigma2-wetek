# Embedded file name: /usr/lib/enigma2/python/Plugins/Extensions/RunKodi/plugin.py
from Plugins.Plugin import PluginDescriptor
from Components.ActionMap import ActionMap
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigEnableDisable, getConfigListEntry, ConfigText, ConfigInteger
from Components.Label import Label
from Screens.Screen import Screen
import os
from enigma import eTimer, eDVBFrontendParametersSatellite, eDVBFrontendParameters, eComponentScan, eDVBSatelliteEquipmentControl, eDVBFrontendParametersTerrestrial, eDVBFrontendParametersCable, eConsoleAppContainer, eDVBResourceManager, getDesktop
from Components.TuneTest import Tuner
from Components.NimManager import nimmanager, getConfigSatlist
config.av.videomode = ConfigSubsection()

class IPTVImport(Screen):
    skin = '\n\t\t<screen position="center,center" size="1920,1080" title="Kodi Media Center" backgroundColor="#000000" >\n\t\t<widget name="infoL" position="50,90" zPosition="2" size="760,375" font="Regular;32" foregroundColor="#efefef" transparent="1" halign="center" valign="center" />\n\t\t</screen>'

    def __init__(self, session):
        Screen.__init__(self, session)
        self['infoL'] = Label(_('Please Wait ... Starting Kodi Media Center'))
        self['actions'] = ActionMap(['OkCancelActions', 'ColorActions', 'DirectionActions'], {'ok': self.KeyOk}, -1)
        self.current_service = self.session.nav.getCurrentlyPlayingServiceReference()
        selectable_nims = []
        for nim in nimmanager.nim_slots:
            if nim.config_mode == 'nothing':
                continue
            if nim.config_mode == 'advanced' and len(nimmanager.getSatListForNim(nim.slot)) < 1:
                continue
            if nim.config_mode in ('loopthrough', 'satposdepends'):
                root_id = nimmanager.sec.getRoot(nim.slot_id, int(nim.config.connectedTo.value))
                if nim.type == nimmanager.nim_slots[root_id].type:
                    continue
            if nim.isCompatible('DVB-S'):
                selectable_nims.append((str(nim.slot), nim.friendly_full_description))

        self.select_nim = ConfigSelection(choices=selectable_nims)
        self.feid = 0
        if self.select_nim.value != '':
            self.feid = int(self.select_nim.value)
        self.frontend = self.OpenFrontend()
        if self.frontend is None:
            self.oldref = self.session.nav.getCurrentlyPlayingServiceReference()
            self.session.nav.stopService()
            if not self.frontend:
                if session.pipshown:
                    session.pipshown = False
                    del session.pip
                    if not self.openFrontend():
                        self.frontend = None
        self.session.nav.playService(None)
        self.KeyOk()
        return

    def OpenFrontend(self):
        frontend = None
        resource_manager = eDVBResourceManager.getInstance()
        if resource_manager is None:
            print 'get resource manager instance failed'
        else:
            self.raw_channel = resource_manager.allocateRawChannel(self.feid)
            if self.raw_channel is None:
                print 'allocateRawChannel failed'
            else:
                frontend = self.raw_channel.getFrontend()
                if frontend is None:
                    print 'getFrontend failed'
        return frontend

    def KeyOk(self):
        fbsetstr = 'fbset -fb /dev/fb0 -g 1280 720 1280 1440 32'
        rezv = config.av.videomode['HDMI'].value
        if rezv == '1080p' or rezv == '1080i':
            fbsetstr = 'fbset -fb /dev/fb0 -g 1920 1080 1920 2160 32'
        cmd = "echo '#!/bin/sh' > /tmp/runkodi.sh"
        cmd = cmd + ";echo '' >> /tmp/runkodi.sh"
        cmd = cmd + ";echo 'sleep 1' >> /tmp/runkodi.sh"
        cmd = cmd + ";echo '/usr/lib/kodi/kodi.sh' >> /tmp/runkodi.sh"
        cmd = cmd + ";echo 'killall -9 enigma2' >> /tmp/runkodi.sh"
        cmd = cmd + ';echo ' + fbsetstr + ' >> /tmp/runkodi.sh'
        os.system(cmd)
        cmd = 'chmod 755 /tmp/runkodi.sh'
        os.system(cmd)
        cmd = '/tmp/runkodi.sh &'
        os.system('/tmp/runkodi.sh &')


def mainmenu(session, **kwargs):
    session.open(IPTVImport)

def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [(_("Kodi Media Center"), mainmenu, "IPTVImport", 10)]
    return []


def Plugins(**kwargs):
    return [PluginDescriptor(name=_('Kodi Media Center'), description='Run Kodi', icon='plugin.png', where=[PluginDescriptor.WHERE_EXTENSIONSMENU, PluginDescriptor.WHERE_PLUGINMENU], fnc=mainmenu),
			PluginDescriptor(name=_('Kodi Media Center'), description='Run Kodi', icon='plugin.png', where= PluginDescriptor.WHERE_MENU, fnc=menu)]