"""
Touchscreen app entry point. Loads main.qml and exposes a small set of
Python-side controls (volume, brightness) that QML can call directly --
these live in functions.py so the exact same code also works as voice
commands later ("Hey Jarvis, turn up the volume").
"""

import signal
import sys

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from functions import (
    set_volume, get_volume, set_brightness, get_brightness,
    get_current_time, get_weather, list_alarms, set_alarm,
)

VOICE_STATE_PATH = "/tmp/assistant_state.txt"

# Qt's event loop normally swallows Ctrl+C entirely (a well-known PySide/PyQt
# gotcha) -- this restores the OS's default terminate-on-SIGINT behavior.
signal.signal(signal.SIGINT, signal.SIG_DFL)


class SettingsBridge(QObject):
    """Exposes Pi-level controls to QML. Each method just calls straight
    into functions.py -- no logic lives here, this is purely the bridge."""

    @Slot(int)
    def setVolume(self, percent):
        set_volume(percent)

    @Slot(result=int)
    def getVolume(self):
        return get_volume()

    @Slot(int)
    def setBrightness(self, percent):
        set_brightness(percent)

    @Slot(result=int)
    def getBrightness(self):
        return get_brightness()

    @Slot(result=bool)
    def isConversing(self):
        try:
            with open(VOICE_STATE_PATH) as f:
                return f.read().strip() == "CONVERSING"
        except FileNotFoundError:
            return False

    @Slot(result=str)
    def getCurrentTime(self):
        return get_current_time()

    @Slot(result=str)
    def getWeatherText(self):
        return get_weather()

    @Slot(result=str)
    def getAlarmsText(self):
        return list_alarms()

    @Slot(str, result=str)
    def setAlarm(self, time_str):
        return set_alarm(time_str=time_str)


app = QGuiApplication(sys.argv)

# Find the DSI touchscreen specifically, rather than whichever screen Qt
# happens to pick as "primary" -- so this always shows up on the real
# target display regardless of what else is connected (e.g. HDMI for dev work).
DSI_NAME_HINT = "DSI"  # matches e.g. "DSI-2", confirmed earlier via wlr-randr

target_screen = None
for screen in app.screens():
    print(f"Found screen: {screen.name()}")
    if DSI_NAME_HINT in screen.name():
        target_screen = screen

engine = QQmlApplicationEngine()

settings_bridge = SettingsBridge()
engine.rootContext().setContextProperty("settingsBridge", settings_bridge)

engine.load("main.qml")

if not engine.rootObjects():
    sys.exit(-1)

window = engine.rootObjects()[0]

if target_screen:
    print(f"Targeting DSI screen: {target_screen.name()}")
    window.setScreen(target_screen)
    window.setGeometry(target_screen.geometry())
else:
    print("No DSI screen found -- showing on the default screen instead.")

window.showFullScreen()

sys.exit(app.exec())
