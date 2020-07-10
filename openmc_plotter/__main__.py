#!/usr/bin/env python3

from pathlib import Path
from threading import Thread
import signal
import sys

from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import QApplication, QSplashScreen

from .main_window import MainWindow, _openmcReload

def main():
    path_icon = str(Path(__file__).parent / 'assets/openmc_logo.png')
    path_splash = str(Path(__file__).parent / 'assets/splash.png')

    app = QApplication(sys.argv)
    app.setOrganizationName("OpenMC")
    app.setOrganizationDomain("openmc.org")
    app.setApplicationName("OpenMC Plot Explorer")
    app.setWindowIcon(QtGui.QIcon(path_icon))
    app.setAttribute(QtCore.Qt.AA_DontShowIconsInMenus, True)

    splash_pix = QtGui.QPixmap(path_splash)
    splash = QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
    splash.setMask(splash_pix.mask())
    splash.show()
    app.processEvents()
    splash.setMask(splash_pix.mask())
    splash.showMessage("Loading Model...",
                       QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom)
    app.processEvents()
    # load OpenMC model on another thread
    loader_thread = Thread(target=_openmcReload)
    loader_thread.start()
    # while thread is working, process app events
    while loader_thread.is_alive():
        app.processEvents()

    splash.clearMessage()
    splash.showMessage("Starting GUI...",
                       QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom)
    app.processEvents()

    font_metric = QtGui.QFontMetrics(app.font())
    screen_size = app.primaryScreen().size()
    mainWindow = MainWindow(font_metric, screen_size)
    # connect splashscreen to main window, close when main window opens
    mainWindow.loadGui()
    mainWindow.show()
    splash.close()

    # connect interrupt signal to close call
    signal.signal(signal.SIGINT, lambda *args: mainWindow.close())
    # create timer that interrupts the Qt event loop
    # to check for a signal
    timer = QtCore.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
