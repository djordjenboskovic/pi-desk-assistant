import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls

Window {
    property var backgrounds: [
        "wallpapers/bg1_cinqueterre.jpg",
        "wallpapers/bg1_lakebled.jpg",
        "wallpapers/bg2_nycskyline.jpg",
        "wallpapers/bg2_hawaii.jpg",
        "wallpapers/bg4_morainelake.jpg",
        "wallpapers/bg3_dolomitescabin.jpg",
        "wallpapers/bg5_dolomitesrowboats.jpg"
    ]
    // Decided per-image by analyzing each photo's actual bottom corners --
    // whichever corner is calmer (less visual detail) gets the clock, and
    // its color is picked for contrast against that specific corner.
    property var clockSides:  ["left", "left", "left", "right", "left", "left", "right"]
    property var clockColors: ["white", "white", "white", "white", "white", "white", "white"]

    property int currentIndex: 0
    property bool showingA: true
    property string clockTimeText: ""

    // Each image slot keeps its own matching side/color, updated only when
    // that slot's picture changes -- so the clock always belongs to whichever
    // photo it's paired with, and simply fades with it.
    property string sideA: clockSides[0]
    property string colorA: clockColors[0]
    property string sideB: "left"
    property string colorB: "white"

    color: "black"

    Image {
        id: imageA
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        source: backgrounds[0]
        opacity: showingA ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 1200; easing.type: Easing.InOutQuad } }
    }

    Image {
        id: imageB
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        opacity: showingA ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 1200; easing.type: Easing.InOutQuad } }
    }

    Text {
        id: clockTextA
        y: parent.height - height - 35
        x: sideA === "left" ? 50 : parent.width - width - 50
        text: clockTimeText
        color: colorA
        style: Text.Outline
        styleColor: colorA === "white" ? "black" : "white"
        font.family: "Quicksand"
        font.pixelSize: 70
        font.weight: Font.DemiBold
        opacity: imageA.opacity
    }

    Text {
        id: clockTextB
        y: parent.height - height - 35
        x: sideB === "left" ? 50 : parent.width - width - 50
        text: clockTimeText
        color: colorB
        style: Text.Outline
        styleColor: colorB === "white" ? "black" : "white"
        font.family: "Quicksand"
        font.pixelSize: 70
        font.weight: Font.DemiBold
        opacity: imageB.opacity
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: clockTimeText = Qt.formatTime(new Date(), "h:mm AP")
    }

    Timer {
        interval: 60000
        running: true
        repeat: true
        onTriggered: {
            currentIndex = (currentIndex + 1) % backgrounds.length
            if (showingA) {
                imageB.source = backgrounds[currentIndex]
                sideB = clockSides[currentIndex]
                colorB = clockColors[currentIndex]
            } else {
                imageA.source = backgrounds[currentIndex]
                sideA = clockSides[currentIndex]
                colorA = clockColors[currentIndex]
            }
            showingA = !showingA
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {
            showingGrid = true
            idleTimer.restart()
        }
    }

    // --- App grid: tap anywhere to reveal, auto-returns after 10s idle ---
    property bool showingGrid: false
    property bool showingSettings: false
    property bool showingClockScreen: false
    property bool showingWeatherScreen: false
    property bool showingAlarmsScreen: false

    Rectangle {
        id: gridOverlay
        anchors.fill: parent
        color: "black"
        opacity: showingGrid ? 0.85 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 400; easing.type: Easing.InOutQuad } }

        GridLayout {
            anchors.centerIn: parent
            columns: 2
            rowSpacing: 30
            columnSpacing: 30

            Repeater {
                model: ["Clock", "Weather", "Alarms", "Settings"]
                delegate: Rectangle {
                    width: 220
                    height: 150
                    radius: 20
                    color: "#2a2a2e"
                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        color: "white"
                        font.family: "Quicksand"
                        font.pixelSize: 28
                        font.weight: Font.DemiBold
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            idleTimer.restart()
                            if (modelData === "Settings") {
                                showingSettings = true
                                volumeSlider.value = settingsBridge.getVolume()
                                brightnessSlider.value = settingsBridge.getBrightness()
                            } else if (modelData === "Clock") {
                                showingClockScreen = true
                            } else if (modelData === "Weather") {
                                showingWeatherScreen = true
                                weatherText.text = settingsBridge.getWeatherText()
                            } else if (modelData === "Alarms") {
                                showingAlarmsScreen = true
                                alarmsText.text = settingsBridge.getAlarmsText()
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: settingsOverlay
        anchors.fill: parent
        color: "#1c1c20"
        opacity: showingSettings ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 36
            width: 480

            Text {
                text: "Settings"
                color: "white"
                font.family: "Quicksand"
                font.pixelSize: 36
                font.weight: Font.Bold
                Layout.alignment: Qt.AlignHCenter
            }

            ColumnLayout {
                spacing: 8
                Layout.fillWidth: true
                Text {
                    text: "Volume"
                    color: "white"
                    font.family: "Quicksand"
                    font.pixelSize: 22
                }
                Slider {
                    id: volumeSlider
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: 50
                    onMoved: {
                        settingsBridge.setVolume(value)
                        idleTimer.restart()
                    }
                }
            }

            ColumnLayout {
                spacing: 8
                Layout.fillWidth: true
                Text {
                    text: "Brightness"
                    color: "white"
                    font.family: "Quicksand"
                    font.pixelSize: 22
                }
                Slider {
                    id: brightnessSlider
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: 100
                    onMoved: {
                        settingsBridge.setBrightness(value)
                        idleTimer.restart()
                    }
                }
            }

            Rectangle {
                width: 160
                height: 56
                radius: 12
                color: "#3a3a3e"
                Layout.alignment: Qt.AlignHCenter
                Text {
                    anchors.centerIn: parent
                    text: "Back"
                    color: "white"
                    font.family: "Quicksand"
                    font.pixelSize: 22
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        showingSettings = false
                        idleTimer.restart()
                    }
                }
            }
        }
    }

    Rectangle {
        id: clockOverlay
        anchors.fill: parent
        color: "#1c1c20"
        opacity: showingClockScreen ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }

        property real hourAngle: 0
        property real minuteAngle: 0
        property real secondAngle: 0

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 24

            Item {
                id: clockFace
                width: 300
                height: 300
                Layout.alignment: Qt.AlignHCenter

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: "#2a2a2e"
                    border.color: "white"
                    border.width: 4
                }

                Repeater {
                    model: 12
                    delegate: Item {
                        anchors.fill: parent
                        rotation: index * 30
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: 14
                            width: index % 3 === 0 ? 6 : 3
                            height: index % 3 === 0 ? 22 : 12
                            radius: 2
                            color: "white"
                        }
                    }
                }

                // Hour hand
                Item {
                    anchors.fill: parent
                    rotation: clockOverlay.hourAngle
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: parent.height / 2 - 65
                        width: 8
                        height: 65
                        radius: 4
                        color: "white"
                    }
                }

                // Minute hand
                Item {
                    anchors.fill: parent
                    rotation: clockOverlay.minuteAngle
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: parent.height / 2 - 100
                        width: 6
                        height: 100
                        radius: 3
                        color: "white"
                    }
                }

                // Second hand
                Item {
                    anchors.fill: parent
                    rotation: clockOverlay.secondAngle
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: parent.height / 2 - 115
                        width: 2
                        height: 115
                        radius: 1
                        color: "#FF5555"
                    }
                }

                Rectangle {
                    width: 16
                    height: 16
                    radius: 8
                    color: "white"
                    anchors.centerIn: parent
                }
            }

            Text {
                id: clockDateText
                color: "white"
                font.family: "Quicksand"
                font.pixelSize: 26
                font.weight: Font.DemiBold
                Layout.alignment: Qt.AlignHCenter
            }

            Rectangle {
                width: 160
                height: 56
                radius: 12
                color: "#3a3a3e"
                Layout.alignment: Qt.AlignHCenter
                Text {
                    anchors.centerIn: parent
                    text: "Back"
                    color: "white"
                    font.family: "Quicksand"
                    font.pixelSize: 22
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        showingClockScreen = false
                        idleTimer.restart()
                    }
                }
            }
        }
    }

    Timer {
        interval: 1000
        running: showingClockScreen
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            var now = new Date()
            var h = now.getHours() % 12
            var m = now.getMinutes()
            var s = now.getSeconds()
            clockOverlay.secondAngle = s * 6
            clockOverlay.minuteAngle = m * 6 + s * 0.1
            clockOverlay.hourAngle = h * 30 + m * 0.5
            clockDateText.text = Qt.formatDate(now, "dddd, MMMM d")
        }
    }

    Rectangle {
        id: weatherOverlay
        anchors.fill: parent
        color: "#1c1c20"
        opacity: showingWeatherScreen ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 30
            width: 600
            Text {
                id: weatherText
                color: "white"
                font.family: "Quicksand"
                font.pixelSize: 34
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
            }
            Rectangle {
                width: 160
                height: 56
                radius: 12
                color: "#3a3a3e"
                Layout.alignment: Qt.AlignHCenter
                Text {
                    anchors.centerIn: parent
                    text: "Back"
                    color: "white"
                    font.family: "Quicksand"
                    font.pixelSize: 22
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        showingWeatherScreen = false
                        idleTimer.restart()
                    }
                }
            }
        }
    }

    Rectangle {
        id: alarmsOverlay
        anchors.fill: parent
        color: "#1c1c20"
        opacity: showingAlarmsScreen ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }

        property int alarmHour: 7
        property int alarmMinute: 0
        property bool alarmPM: false

        function pad(n) { return (n < 10 ? "0" : "") + n }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 30
            width: 600
            Text {
                id: alarmsText
                color: "white"
                font.family: "Quicksand"
                font.pixelSize: 30
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
            }

            RowLayout {
                spacing: 24
                Layout.alignment: Qt.AlignHCenter

                ColumnLayout {
                    spacing: 6
                    Rectangle {
                        width: 64; height: 48; radius: 10; color: "#3a3a3e"
                        Layout.alignment: Qt.AlignHCenter
                        Text { anchors.centerIn: parent; text: "+"; color: "white"; font.pixelSize: 26 }
                        MouseArea { anchors.fill: parent; onClicked: { alarmsOverlay.alarmHour = alarmsOverlay.alarmHour === 12 ? 1 : alarmsOverlay.alarmHour + 1; idleTimer.restart() } }
                    }
                    Text {
                        text: alarmsOverlay.alarmHour
                        color: "white"; font.family: "Quicksand"; font.pixelSize: 40; font.weight: Font.DemiBold
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Rectangle {
                        width: 64; height: 48; radius: 10; color: "#3a3a3e"
                        Layout.alignment: Qt.AlignHCenter
                        Text { anchors.centerIn: parent; text: "-"; color: "white"; font.pixelSize: 26 }
                        MouseArea { anchors.fill: parent; onClicked: { alarmsOverlay.alarmHour = alarmsOverlay.alarmHour === 1 ? 12 : alarmsOverlay.alarmHour - 1; idleTimer.restart() } }
                    }
                }

                Text { text: ":"; color: "white"; font.pixelSize: 40; font.weight: Font.DemiBold }

                ColumnLayout {
                    spacing: 6
                    Rectangle {
                        width: 64; height: 48; radius: 10; color: "#3a3a3e"
                        Layout.alignment: Qt.AlignHCenter
                        Text { anchors.centerIn: parent; text: "+"; color: "white"; font.pixelSize: 26 }
                        MouseArea { anchors.fill: parent; onClicked: { alarmsOverlay.alarmMinute = (alarmsOverlay.alarmMinute + 5) % 60; idleTimer.restart() } }
                    }
                    Text {
                        text: alarmsOverlay.pad(alarmsOverlay.alarmMinute)
                        color: "white"; font.family: "Quicksand"; font.pixelSize: 40; font.weight: Font.DemiBold
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Rectangle {
                        width: 64; height: 48; radius: 10; color: "#3a3a3e"
                        Layout.alignment: Qt.AlignHCenter
                        Text { anchors.centerIn: parent; text: "-"; color: "white"; font.pixelSize: 26 }
                        MouseArea { anchors.fill: parent; onClicked: { alarmsOverlay.alarmMinute = (alarmsOverlay.alarmMinute + 55) % 60; idleTimer.restart() } }
                    }
                }

                Rectangle {
                    width: 80; height: 56; radius: 12; color: "#3a3a3e"
                    Layout.alignment: Qt.AlignHCenter
                    Text {
                        anchors.centerIn: parent
                        text: alarmsOverlay.alarmPM ? "PM" : "AM"
                        color: "white"; font.family: "Quicksand"; font.pixelSize: 24
                    }
                    MouseArea { anchors.fill: parent; onClicked: { alarmsOverlay.alarmPM = !alarmsOverlay.alarmPM; idleTimer.restart() } }
                }
            }

            Rectangle {
                width: 220
                height: 56
                radius: 12
                color: "#4A00E0"
                Layout.alignment: Qt.AlignHCenter
                Text {
                    anchors.centerIn: parent
                    text: "Set Alarm"
                    color: "white"
                    font.family: "Quicksand"
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        var h24 = alarmsOverlay.alarmHour % 12
                        if (alarmsOverlay.alarmPM) h24 += 12
                        var timeStr = alarmsOverlay.pad(h24) + ":" + alarmsOverlay.pad(alarmsOverlay.alarmMinute)
                        settingsBridge.setAlarm(timeStr)
                        alarmsText.text = settingsBridge.getAlarmsText()
                        idleTimer.restart()
                    }
                }
            }

            Rectangle {
                width: 160
                height: 56
                radius: 12
                color: "#3a3a3e"
                Layout.alignment: Qt.AlignHCenter
                Text {
                    anchors.centerIn: parent
                    text: "Back"
                    color: "white"
                    font.family: "Quicksand"
                    font.pixelSize: 22
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        showingAlarmsScreen = false
                        idleTimer.restart()
                    }
                }
            }
        }
    }

    Timer {
        id: idleTimer
        interval: 10000
        repeat: false
        onTriggered: {
            showingGrid = false
            showingSettings = false
            showingClockScreen = false
            showingWeatherScreen = false
            showingAlarmsScreen = false
        }
    }

    Timer {
        interval: 150
        running: true
        repeat: true
        onTriggered: inConversation = settingsBridge.isConversing()
    }

    property bool inConversation: false

    Rectangle {
        id: conversationBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 8
        opacity: inConversation ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.InOutQuad } }
        clip: true
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#4A00E0" }
            GradientStop { position: 1.0; color: "#2979FF" }
        }

        Rectangle {
            id: highlight
            width: parent.width * 0.3
            height: parent.height
            x: -width
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0) }
                GradientStop { position: 0.5; color: Qt.rgba(0.65, 0.85, 1, 0.95) }
                GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0) }
            }

            NumberAnimation on x {
                running: inConversation
                loops: Animation.Infinite
                from: -highlight.width
                to: conversationBar.width
                duration: 1800
                easing.type: Easing.InOutSine
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: Qt.quit()
    }
}
