installdir = $(pkglibdir)/python/Plugins/Extensions

SUBDIRS = TuxboxPlugins CutListEditor PicturePlayer MediaScanner MediaPlayer SocketMMI DVDBurn Modem VirtualZap GraphMultiEPG Volume_adjust

if HAVE_LIBDDVD
SUBDIRS += DVDPlayer
endif

if HAVE_WETEK_XBMC
SUBDIRS +=  StartKodi StartXBMC
endif

install_PYTHON = __init__.py
