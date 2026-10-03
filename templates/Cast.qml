pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.folderlistmodel

Item {
  id: root
  property var bar
  property string moduleName
  property var settings
  implicitWidth: 28
  implicitHeight: bar ? bar.barSize : 26
  readonly property color ink: bar ? bar.foreground : "white"
  onInkChanged: icon.requestPaint()
  Canvas {
    id: icon
    anchors.centerIn: parent
    width: 19; height: 19
    onPaint: {
      const c = getContext("2d"); c.reset(); c.strokeStyle = root.ink;
      c.fillStyle = root.ink; c.lineWidth = 1.5; c.lineCap = "round";
      c.beginPath(); c.moveTo(2,7); c.lineTo(2,3); c.lineTo(17,3);
      c.lineTo(17,14); c.lineTo(11,14); c.stroke();
      c.beginPath(); c.arc(2,16,4,-Math.PI/2,0); c.stroke();
      c.beginPath(); c.arc(2,16,8,-Math.PI/2,0); c.stroke();
      c.beginPath(); c.arc(2,16,1,0,2*Math.PI); c.fill();
    }
  }
  IpcHandler { target: "local.cast"; function open(): void { popup.visible = true; root.scan(); } function selectFile(uri: string): void { root.chosenFile = uri; popup.visible = true; root.scan(); } }
  property var playback: ({ok: false, state: "UNKNOWN", position: 0, duration: 0, volume: null, muted: null})
  property string playbackError: ""
  function timeLabel(n) { n = Math.max(0, Math.floor(n || 0)); return Math.floor(n / 60) + ":" + (n % 60 < 10 ? "0" : "") + n % 60; }
  function control(command, value) {
    if (controller.running) return;
    let request = {command: command};
    if (value !== undefined) request.value = value;
    if (devicesBox.currentIndex >= 0 && devicesBox.currentIndex < root.devices.length) request.target = root.devices[devicesBox.currentIndex];
    controller.operation = command;
    if (command !== "status") root.playbackError = "";
    controller.command = ["@HOME@/.local/bin/omarchy-cast", "--control", JSON.stringify(request)];
    controller.running = true;
  }
  Process {
    id: controller
    property string operation: "status"
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          const result = JSON.parse(text);
          if (!result.ok) { root.playbackError = result.error; if (controller.operation === "status") root.playback = {ok: false}; }
          else { if (controller.operation !== "status") root.playbackError = ""; if (result.state) root.playback = result; }
        } catch (e) { root.playbackError = "Receiver did not respond."; root.playback = {ok: false}; }
      }
    }
  }
  Timer { interval: 3000; running: popup.visible; repeat: true; triggeredOnStart: true; onTriggered: root.control("status") }
  property var devices: []
  property string chosenFile: ""
  function togglePicker() {
    popup.visible = !popup.visible;
    if (popup.visible) scan();
  }
  function scan() {
    if (discovery.running) return;
    status.text = "Scanning LAN…";
    discovery.command = ["/usr/bin/python3", "@HOME@/.local/state/video-cast/devices.py"];
    if (address.text.trim()) discovery.command = discovery.command.concat([address.text.trim()]);
    discovery.running = true;
  }
  Process {
    id: discovery
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          root.devices = JSON.parse(text);
          devicesBox.model = root.devices.map(d => d.name + " — " + d.ip);
          status.text = root.devices.length ? "Choose a video below." : "No DLNA receivers found. Turn on a receiver and scan again.";
        } catch (e) { status.text = "Discovery failed. Check the device IP and retry."; }
      }
    }
  }
  PopupWindow {
    id: popup
    visible: false
    implicitWidth: 490
    implicitHeight: 790
    color: root.bar ? root.bar.background : "#171b24"
    anchor {
      id: popupAnchor
      window: root.QsWindow.window
      adjustment: PopupAdjustment.Slide
      edges: Edges.Top | Edges.Left
      gravity: Edges.Bottom | Edges.Right
      onAnchoring: {
        const p = root.mapToItem(root.QsWindow.window.contentItem, 0, root.height + 6);
        popupAnchor.rect.x = p.x - popup.width + root.width;
        popupAnchor.rect.y = p.y;
      }
    }
    // Keep the picker open across focus changes and nested control popups.
    // Close explicitly with the Close button, bar icon, or Cast action.
    ColumnLayout {
      anchors.fill: parent
      anchors.margins: 16
      spacing: 10
      RowLayout {
        Label { text: "Cast video"; font.bold: true; Layout.fillWidth: true; color: root.ink }
        Button { text: "Close"; onClicked: popup.visible = false }
      }
      ComboBox { id: devicesBox; Layout.fillWidth: true; onActivated: { root.playback = {ok: false}; root.control("status"); } }
      Label { text: root.playbackError || (root.playback.ok ? ((root.playback.name || "Receiver") + " · " + root.playback.state) : "Checking playback…"); color: root.ink; Layout.fillWidth: true; elide: Text.ElideRight }
      RowLayout {
        enabled: root.playback.ok && !controller.running
        Button { text: "Restart"; onClicked: root.control("restart") }
        Button { text: "−10s"; onClicked: root.control("skip", -10) }
        Button { text: root.playback.state === "PLAYING" ? "Pause" : "Play"; onClicked: root.control("toggle") }
        Button { text: "+10s"; onClicked: root.control("skip", 10) }
        Button { text: "Stop"; onClicked: root.control("stop") }
      }
      RowLayout {
        Label { text: root.timeLabel(root.playback.position); color: root.ink }
        Slider {
          Layout.fillWidth: true
          from: 0; to: Math.max(1, root.playback.duration || 0)
          value: root.playback.position || 0
          enabled: root.playback.ok && root.playback.duration > 0 && !controller.running
          onPressedChanged: if (!pressed) root.control("seek", value)
        }
        Label { text: root.timeLabel(root.playback.duration); color: root.ink }
      }
      RowLayout {
        enabled: root.playback.ok && root.playback.volume !== null && root.playback.volume !== undefined && !controller.running
        Button { text: root.playback.muted ? "Unmute" : "Mute"; onClicked: root.control("mute") }
        Slider { Layout.fillWidth: true; from: 0; to: 100; value: root.playback.volume || 0; onPressedChanged: if (!pressed) root.control("volume", Math.round(value)) }
        Label { text: (root.playback.volume === null || root.playback.volume === undefined) ? "N/A" : root.playback.volume + "%"; color: root.ink }
      }
      RowLayout {
        TextField { id: address; placeholderText: "Optional device IP"; Layout.fillWidth: true; onAccepted: root.scan() }
        Button { text: discovery.running ? "Scanning…" : "Scan LAN"; enabled: !discovery.running; onClicked: root.scan() }
      }
      RowLayout {
        Button { text: "Up"; onClicked: files.folder = files.parentFolder }
        Button { text: "Videos"; onClicked: files.folder = "file://@HOME@/Videos" }
        Label { text: decodeURIComponent(files.folder.toString().replace("file://", "")); elide: Text.ElideMiddle; Layout.fillWidth: true; color: root.ink }
      }
      FolderListModel {
        id: files
        folder: "file://@HOME@/Videos"
        nameFilters: ["*.mp4", "*.mkv", "*.mov", "*.webm", "*.m4v", "*.avi"]
        showDirs: true
        showDotAndDotDot: false
        showHidden: false
        sortField: FolderListModel.Name
        showDirsFirst: true
      }
      ListView {
        id: listing
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: files
        ScrollBar.vertical: ScrollBar {}
        delegate: ItemDelegate {
          required property string fileName
          required property url fileUrl
          required property bool fileIsDir
          width: listing.width
          text: (fileIsDir ? "▸  " : "    ") + fileName
          highlighted: root.chosenFile === fileUrl.toString()
          onClicked: {
            if (fileIsDir) files.folder = fileUrl;
            else root.chosenFile = fileUrl.toString();
          }
        }
      }
      Label { text: root.chosenFile ? decodeURIComponent(root.chosenFile.split("/").pop()) : "Select a video"; elide: Text.ElideMiddle; Layout.fillWidth: true; color: root.ink }
      Label { id: status; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: root.ink }
      Button {
        text: "Cast"
        Layout.fillWidth: true
        enabled: root.chosenFile !== "" && devicesBox.currentIndex >= 0 && root.devices.length > 0
        onClicked: {
          Quickshell.execDetached(["@HOME@/.local/bin/omarchy-cast", root.chosenFile, JSON.stringify(root.devices[devicesBox.currentIndex])]);
          status.text = "Preparing playback…";
        }
      }
      Label { text: "DLNA receivers · Large videos are optimized automatically"; font.pixelSize: 11; color: root.ink }
    }
  }
  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
    onEntered: if (root.bar) root.bar.showTooltip(root, "Cast to LAN device\nClick: choose device and video · Right-click: restart · Middle-click: stop")
    onExited: if (root.bar) root.bar.hideTooltip(root)
    onClicked: mouse => {
      if (root.bar) root.bar.hideTooltip(root);
      if (mouse.button === Qt.LeftButton) root.togglePicker();
      else Quickshell.execDetached(["@HOME@/.local/bin/omarchy-cast", mouse.button === Qt.RightButton ? "--restart" : "--stop"]);
    }
  }
}
