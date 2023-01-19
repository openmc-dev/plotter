#!/usr/bin/env python

from argparse import ArgumentParser
from pathlib import Path
from threading import Thread
import os
import signal
import sys

from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import QApplication, QSplashScreen

from . import __version__
from .main_window import MainWindow, _openmcReload

def main():
    ap = ArgumentParser(description='OpenMC Plotter GUI')
    version_str = f'OpenMC Plotter Version: {__version__}'
    ap.add_argument('-v', '--version', action='version', version=version_str,
                    help='Display version info.')
    ap.add_argument('-d', '--model-directory', default=os.curdir,
                    help='Location of model dir (default is current dir)')
    ap.add_argument('-e','--ignore-settings', action='store_false',
                    help='Ignore plot_settings.pkl file if present.')
    ap.add_argument('-s', '--threads', type=int, default=None,
                    help='If present, number of threads used to generate plots.')

    args = ap.parse_args()

    os.chdir(args.model_directory)

    run_app(args)


def run_app(user_args):
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
    openmc_args = {'threads': user_args.threads}
    loader_thread = Thread(target=_openmcReload, kwargs=openmc_args)
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
    mainWindow.loadGui(use_settings_pkl=user_args.ignore_settings)
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
