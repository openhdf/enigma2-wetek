installdir = $(pkglibdir)/python/Plugins/SystemPlugins

SUBDIRS = SoftwareManager PositionerSetup Satfinder \
	VideoTune Hotplug CableScan DiseqcTester \
	DefaultServicesScanner CommonInterfaceAssignment \
	HdmiCEC VideoClippingSetup SatelliteEquipmentControl \
	VideoEnhancement WirelessLan NetworkWizard \
	SABnzbdSetup OSD3DSetup DeviceManager SwapManager LCNScanner

if HAVE_LIBVUGLES2
SUBDIRS += AnimationSetup
endif

install_PYTHON = __init__.py
