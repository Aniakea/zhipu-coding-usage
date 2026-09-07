import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as M

// Zhipu Coding Plan usage as one bar glyph and one panel. The widget is
// strictly a display: `bin/zhipu-coding-usage` owns every number and publishes
// them as a JSON record, and everything below draws whatever that record says.
Panel {
  id: root
  moduleName: "io.github.aniakea.zhipu-coding-usage"
  ipcTarget: "zhipu"
  manageIpc: false

  // Painted ink width of the face (glyph ink start to number ink end); the
  // slot pads it with the standard WidgetButton margin on both sides so
  // neighbor spacing matches every other bar widget, and the open-panel mark
  // below subtracts those margins again to hug the ink.
  readonly property real faceInkWidth: button.x + button.labelWidth - Style.space(1)
  implicitWidth: faceInkWidth + 2 * button.scaledHorizontalMargin
  implicitHeight: button.implicitHeight

  // ------------------------------------------------------------- appearance
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color accent: Color.accent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color faint: Qt.darker(foreground, 2.1)
  readonly property color surface: Color.popups.background
  readonly property color track: Style.selectedFillFor(foreground, Color.accent)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  // ------------------------------------------------------------------- data
  property var record: null
  property bool loading: collector.running
  property string collectorError: ""
  property string parseError: ""
  readonly property string recordError: record && record.error ? String(record.error) : ""
  readonly property string activeError: recordError !== "" ? errorText(recordError)
    : parseError !== "" ? parseError
    : collectorError

  readonly property var fiveHour: record && record.fiveHour ? record.fiveHour : null
  readonly property var weekly: record && record.weekly ? record.weekly : null
  readonly property var usage24h: record && record.usage24h ? record.usage24h : null
  readonly property var models: usage24h && usage24h.models ? usage24h.models : []
  property string chartRange: "24h"

  function seriesForRange(range) {
    if (range === "24h") return chartBuckets
    var history = record && record.history ? record.history : {}
    var series = history[range]
    if (!series || series.length === 0) return []
    var out = []
    for (var i = 0; i < series.length; i++)
      out.push({ label: String(series[i].key), tokens: series[i].tokens })
    return out
  }

  readonly property var chartBuckets: {
    if (chartRange !== "24h") return seriesForRange(chartRange)
    if (!usage24h || !usage24h.tokensByHour) return []
    var out = []
    for (var i = 0; i < usage24h.tokensByHour.length; i++) {
      var label = usage24h.hourLabels && usage24h.hourLabels[i] ? String(usage24h.hourLabels[i]) : ""
      out.push({
        tokens: usage24h.tokensByHour[i],
        peak: usage24h.peakByHour ? usage24h.peakByHour[i] === true : false,
        label: label,
        hour: label.length >= 13 ? label.substring(11, 13) : ""
      })
    }
    return out
  }
  readonly property string planLabel: record && record.planLabel ? String(record.planLabel) : ""
  readonly property string region: record && record.region ? String(record.region) : ""

  property double nowMs: Date.now()

  // The glyph tracks the most urgent live window: neutral while there is room,
  // the theme's urgent color once a window is nearly spent.
  function severityColor(pct) {
    if (pct === null || pct === undefined) return foreground
    if (pct >= 90) return urgent
    if (pct >= 75) return Qt.tint(foreground, alpha(urgent, 0.45))
    return foreground
  }
  readonly property color statusColor: fiveHour && fiveHour.present
    ? severityColor(fiveHour.percent)
    : weekly && weekly.present ? severityColor(weekly.percent) : foreground

  // ---------------------------------------------------------------- settings
  // parseInt + || guard: `settings` arrives empty and fills asynchronously,
  // and a stringly-typed value must never yield NaN into the Timer interval.
  readonly property int refreshIntervalSec: Math.max(30, parseInt(setting("refreshIntervalSec", 120), 10) || 120)
  readonly property string barDisplay: String(setting("barDisplay", "percent"))
  readonly property bool showBarLabel: barDisplay !== "icon"
  readonly property string language: String(setting("language", "auto"))
  readonly property string langEffective: {
    if (language === "en" || language === "zh") return language
    return String(Qt.locale().name).indexOf("zh") === 0 ? "zh" : "en"
  }
  readonly property var t: M.strings(langEffective)
  readonly property string glyph: {
    var configured = String(setting("glyph", ""))
    return configured === "" ? "\uf0e7" : configured
  }

  readonly property string statePath: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state"))
    + "/omarchy/zhipu/usage.json"

  // The open-panel mark under the bar defaults to 55% of the slot; the ink
  // width keeps it exactly as wide as what is painted.
  readonly property real openPanelIndicatorWidth: root.faceInkWidth

  // ------------------------------------------------------------------ label
  readonly property string barLabel: {
    if (!showBarLabel) return ""
    if (barDisplay === "weekly") return weekly && weekly.present ? M.percent(weekly.percent) : "—"
    if (barDisplay === "both")
      return (fiveHour && fiveHour.present ? M.percent(fiveHour.percent) : "—")
        + "·" + (weekly && weekly.present ? M.percent(weekly.percent) : "—")
    return fiveHour && fiveHour.present ? M.percent(fiveHour.percent) : "—"
  }

  readonly property string tooltipText: {
    if (activeError !== "") return "Zhipu — " + activeError
    if (!record) return "Zhipu Coding Plan — no usage recorded yet"
    var lines = [planLabel + " · " + region]
    if (fiveHour && fiveHour.present) {
      var clock = M.clockTextMs(fiveHour.resetsAtMs)
      lines.push("5h " + M.percent(fiveHour.percent) + " · resets to "
        + (fiveHour.budget ? M.credits(fiveHour.budget) : "full") + " in " + M.untilTextMs(fiveHour.resetsAtMs, nowMs)
        + (clock !== "" ? " (" + clock + ")" : ""))
    }
    if (weekly && weekly.present) {
      var weekClock = M.clockTextMs(weekly.resetsAtMs)
      lines.push("weekly " + M.percent(weekly.percent) + " · resets to "
        + (weekly.budget ? M.credits(weekly.budget) : "full") + " in " + M.untilTextMs(weekly.resetsAtMs, nowMs)
        + (weekClock !== "" ? " (" + weekClock + ")" : ""))
    }
    return lines.join("\n")
  }

  function errorText(code) {
    if (code === "no-key") return "no API key — run bin/zhipu-coding-usage --set-key (or export ZHIPUAI_API_KEY)"
    if (code === "http-401" || code === "http-403") return "API key rejected"
    if (code === "unreachable") return "Zhipu API unreachable"
    if (code === "bad-payload") return "unexpected API response"
    if (code === "no-limits") return "no quota windows on this plan"
    return code
  }

  // ----------------------------------------------------------------- actions
  function refreshNow() {
    if (collector.running) return
    collector.running = true
  }

  function cycleBarDisplay() {
    var order = ["percent", "weekly", "both", "icon"]
    var index = Math.max(0, order.indexOf(barDisplay))
    var next = order[(index + 1) % order.length]
    if (bar && typeof bar.run === "function")
      bar.run("omarchy bar set " + moduleName + " barDisplay " + next)
  }

  function openUsagePage() {
    var url = region === "intl" ? "https://z.ai/subscribe" : "https://bigmodel.cn/coding-plan/usage-stats"
    if (bar && typeof bar.run === "function")
      bar.run("xdg-open " + url)
    close()
  }

  // ------------------------------------------------------------------ wiring
  Process {
    id: collector
    running: false
    // Resolved relative to the plugin directory so the collector ships with
    // the plugin and needs no place on PATH.
    command: [Qt.resolvedUrl("bin/zhipu-coding-usage").toString().replace("file://", ""), "--quiet"]
    onExited: function(code) {
      root.collectorError = code === 0 ? "" : "collector exited " + code
      usageFile.reload()
    }
  }

  FileView {
    id: usageFile
    path: root.statePath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parse(text())
    onLoadFailed: {
      root.record = null
    }
  }

  function parse(content) {
    try {
      var parsed = JSON.parse(String(content || ""))
      root.record = parsed && typeof parsed === "object" ? parsed : null
      root.parseError = ""
    } catch (e) {
      console.warn(moduleName, "ignoring malformed usage record", e)
      root.record = null
      root.parseError = "malformed record"
    }
  }

  Timer {
    interval: root.refreshIntervalSec * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refreshNow()
  }

  Timer {
    interval: 1000
    running: root.opened
    repeat: true
    onTriggered: root.nowMs = Date.now()
  }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { root.refreshNow(); return "ok" }
    function usage(): string {
      if (!root.record || root.record.error) return root.activeError
      var five = root.fiveHour && root.fiveHour.present ? M.percent(root.fiveHour.percent) : "—"
      var week = root.weekly && root.weekly.present ? M.percent(root.weekly.percent) : "—"
      return root.planLabel + ": 5h " + five + " · weekly " + week
    }
  }

  // ------------------------------------------------------------- bar button
  WidgetButton {
    id: button
    anchors.verticalCenter: parent.verticalCenter
    width: implicitWidth
    // Standard left margin, the glyph's advance box, then the box's own
    // margin slid under the glyph so the number's ink sits close to it.
    x: button.scaledHorizontalMargin + glyphText.implicitWidth - Style.space(8)
    bar: root.bar
    // Only the number lives in the button's own text; the glyph is the
    // sibling to its left. The face-wide MouseArea below owns interaction,
    // so the button keeps painting but not pointing.
    text: root.showBarLabel && root.barLabel !== "" ? root.barLabel : root.glyph
    tooltipText: ""
    interactive: false
    active: root.statusColor === root.urgent
    activeColor: root.urgent
    fontSize: Style.font.body
  }

  Text {
    id: glyphText
    visible: root.showBarLabel && root.barLabel !== ""
    anchors.verticalCenter: parent.verticalCenter
    x: button.scaledHorizontalMargin
    text: root.glyph
    color: root.statusColor
    font.family: root.fontFamily
    font.pixelSize: Style.font.body
    renderType: Text.NativeRendering
  }

  // Zero-footprint anchor at the face's horizontal center, so the panel
  // opens under glyph+number rather than under the number's box alone.
  Item {
    id: faceAnchor
    x: root.width / 2
    width: 1
    height: root.height
  }

  // Interaction for the whole face (glyph overhang included).
  MouseArea {
    anchors.fill: parent
    acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onEntered: if (root.bar) root.bar.showTooltip(root, root.tooltipText)
    onExited: if (root.bar) root.bar.hideTooltip(root)
    onClicked: function(mouse) {
      if (root.bar) root.bar.hideTooltip(root)
      if (mouse.button === Qt.RightButton) root.refreshNow()
      else if (mouse.button === Qt.MiddleButton) root.cycleBarDisplay()
      else root.toggle()
    }
  }

  // ------------------------------------------------------------------ panel
  KeyboardPanel {
    id: panel
    anchorItem: faceAnchor
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(400))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(600))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      onMoveRequested: function(dx, dy) {
        if (dy !== 0)
          flick.contentY = M.clamp(flick.contentY + dy * Style.space(56), 0,
                                   Math.max(0, flick.contentHeight - flick.height))
      }
      onActivateRequested: root.refreshNow()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refreshNow()
        else if (t === "b" || t === "B") root.openUsagePage()
      }

      Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: column
          width: flick.width
          spacing: Style.space(12)

          PanelHero {
            width: parent.width
            title: "Zhipu Coding Plan"
            meta: {
              var parts = []
              if (root.planLabel !== "") parts.push(root.planLabel)
              parts.push(root.region === "intl" ? "z.ai" : "bigmodel.cn")
              parts.push(root.record && root.record.error ? root.t.stale : root.t.live)
              if (root.record && root.record.peak)
                parts.push(root.record.peak.peakNow ? root.t.peak : root.t.offPeak)
              return parts.join("  ·  ")
            }
            detail: root.activeError !== "" ? root.activeError
              : root.fiveHour && root.fiveHour.present
                ? "5h " + M.percent(root.fiveHour.percent) + (root.weekly && root.weekly.present ? "  ·  weekly " + M.percent(root.weekly.percent) : "")
                : "no usage recorded yet"
            foreground: root.foreground
            fontFamily: root.fontFamily

            iconComponent: Component {
              Text {
                text: root.glyph
                color: root.statusColor
                font.family: root.fontFamily
                font.pixelSize: Style.font.display
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
              }
            }

            trailingControl: Component {
              PanelActionButton {
                iconText: "\uf021"
                tooltipText: "Refresh"
                foreground: root.foreground
                fontFamily: root.fontFamily
                opacity: root.loading ? 0.45 : 1.0
                onClicked: root.refreshNow()
              }
            }
          }

          QuotaMeter {
            width: parent.width
            label: root.t.fiveHour
            window: root.fiveHour
          }

          QuotaMeter {
            width: parent.width
            label: root.t.weekly
            window: root.weekly
          }

          Text {
            width: parent.width
            visible: root.record && root.record.projection
            text: M.paceLine(root.record ? root.record.projection : null, root.langEffective)
            color: root.faint
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }

          // An absent window is a state of the plan, not a zero: naming it
          // beats a silently missing row.
          Text {
            width: parent.width
            visible: root.weekly && !root.weekly.present
            text: root.t.notReported
            color: root.faint
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          PanelSeparator { width: parent.width }

          Grid {
            width: parent.width
            columns: 2
            columnSpacing: Style.space(10)
            rowSpacing: Style.space(8)
            visible: !!root.usage24h

            Repeater {
              model: [
                { label: root.t.requests24h, value: M.group(root.usage24h ? root.usage24h.calls : 0), strong: true },
                { label: root.t.tokens24h, value: M.tokens(root.usage24h ? root.usage24h.tokens : 0), strong: false },
                { label: root.t.webSearch24h, value: M.group(root.usage24h && root.usage24h.tools ? root.usage24h.tools.search : 0), strong: false },
                { label: root.t.webRead24h, value: M.group(root.usage24h && root.usage24h.tools ? root.usage24h.tools.web_read : 0), strong: false },
                {
                  label: root.t.offPeakShare,
                  value: root.record && root.record.peak && root.record.peak.offPeakShare24h !== null && root.record.peak.offPeakShare24h !== undefined
                    ? Math.round(root.record.peak.offPeakShare24h * 100) + "%" : "—",
                  strong: false
                },
                {
                  label: root.t.pace,
                  value: root.record && root.record.projection
                    ? M.untilTextMs(root.record.projection.exhaustsAtMs, root.nowMs) : "—",
                  strong: false
                }
              ]

              Column {
                required property var modelData
                width: (column.width - Style.space(10)) / 2
                spacing: Style.space(1)

                Text {
                  text: modelData.value
                  color: modelData.strong ? root.foreground : root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.subtitle
                  font.bold: modelData.strong === true
                  elide: Text.ElideRight
                  width: parent.width
                }
                Text {
                  text: modelData.label
                  color: root.faint
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                  width: parent.width
                }
              }
            }
          }

          Item {
            width: parent.width
            implicitHeight: headerRow.implicitHeight
            visible: root.chartBuckets.length > 0

            Text {
              id: chartTitle
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              text: root.t.tokensChart
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }

            Row {
              id: headerRow
              anchors.right: parent.right
              spacing: Style.space(4)

              Repeater {
                model: [
                  { key: "24h", label: root.t.range24h },
                  { key: "daily", label: root.t.rangeDaily },
                  { key: "weekly", label: root.t.rangeWeekly },
                  { key: "monthly", label: root.t.rangeMonthly }
                ]

                Rectangle {
                  required property var modelData
                  readonly property bool active: root.chartRange === modelData.key
                  readonly property bool offered: root.seriesForRange(modelData.key).length > 0
                  width: chipLabel.implicitWidth + Style.space(6)
                  height: chipLabel.implicitHeight + Style.space(3)
                  radius: height / 2
                  color: active ? root.alpha(root.accent, 0.35) : "transparent"
                  border.width: offered ? 1 : 0
                  border.color: root.alpha(root.foreground, 0.25)
                  opacity: offered ? 1 : 0.35

                  Text {
                    id: chipLabel
                    anchors.centerIn: parent
                    text: parent.modelData.label
                    color: parent.active ? root.foreground : root.dim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                  }

                  MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: parent.offered ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: if (parent.offered) root.chartRange = parent.modelData.key
                  }
                }
              }
            }
          }

          LineChart {
            id: tokenChart
            width: parent.width
            height: Style.space(72)
            visible: root.chartBuckets.length > 0
            points: root.chartBuckets
            lineColor: root.alpha(root.accent, 0.9)
            fillColor: root.alpha(root.accent, 0.14)
            peakColor: Qt.tint(root.foreground, root.alpha(root.urgent, 0.55))
            fontFamily: root.fontFamily
            textColor: root.faint
            tooltipHost: root
            pointText: function(p) {
              return p.label + " · " + M.tokens(p.tokens)
                + (p.peak !== undefined ? " · " + (p.peak ? root.t.peakBar : root.t.offPeakBar) : "")
            }
          }

          PanelSectionHeader {
            width: parent.width
            text: root.t.modelsTitle
            foreground: root.foreground
            fontFamily: root.fontFamily
            visible: root.models.length > 0
          }

          Column {
            id: modelList
            width: parent.width
            spacing: Style.space(6)
            visible: root.models.length > 0

            readonly property real peak: {
              var best = 0
              for (var i = 0; i < root.models.length; i++)
                best = Math.max(best, M.num(root.models[i] ? root.models[i].tokens : 0))
              return best
            }

            Repeater {
              model: root.models

              Item {
                id: modelRow
                required property var modelData
                width: parent.width
                implicitHeight: modelText.implicitHeight + Style.space(7)

                readonly property real share: M.shareOfPeak(modelData.tokens, modelList.peak)

                // The bar lives behind the text so a long model name never
                // fights the chart for width.
                Rectangle {
                  anchors.left: parent.left
                  anchors.verticalCenter: parent.verticalCenter
                  width: Math.max(Style.space(2), parent.width * modelRow.share)
                  height: parent.height
                  radius: Math.max(1, Style.space(2))
                  color: root.alpha(root.accent, 0.16)
                  Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                }

                Row {
                  anchors.fill: parent
                  anchors.leftMargin: Style.space(6)
                  anchors.rightMargin: Style.space(6)
                  spacing: Style.space(8)

                  Text {
                    id: modelText
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - tokenText.width - Style.space(16)
                    text: modelData.name
                    color: root.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    elide: Text.ElideRight
                  }

                  Text {
                    id: tokenText
                    anchors.verticalCenter: parent.verticalCenter
                    text: M.tokens(modelData.tokens)
                    color: root.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    font.bold: true
                  }
                }

                MouseArea {
                  anchors.fill: parent
                  hoverEnabled: true
                  onEntered: if (root.bar) root.bar.showTooltip(modelRow,
                    modelData.name + " · " + M.tokens(modelData.tokens) + " tokens · "
                    + Math.round(modelRow.share * 100) + "% of 24h spend")
                  onExited: if (root.bar) root.bar.hideTooltip(modelRow)
                }
              }
            }
          }

          Text {
            width: parent.width
            visible: root.models.length === 0 && root.activeError === ""
            text: root.t.noUsage
            color: root.faint
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
          }

          PanelSeparator { width: parent.width }

          Item {
            width: parent.width
            implicitHeight: Math.max(updatedText.implicitHeight, hintText.implicitHeight)

            Text {
              id: updatedText
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              width: parent.width - hintText.implicitWidth - Style.space(10)
              text: root.loading ? root.t.refreshing
                : root.record && root.record.generatedAt
                  ? root.t.updated + M.agoText(root.record.generatedAt, root.nowMs) : ""
              color: root.faint
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }

            Text {
              id: hintText
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: root.t.refreshHint
              color: root.faint
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
          }
        }
      }
    }
  }

  // ----------------------------------------------------------------- meters

  // A polyline chart over `points` ({label, tokens, peak?}) with a soft
  // area fill, sparse x labels, and per-point hover through the bar's own
  // tooltip channel. Peak-flagged points draw a marker in `peakColor`.
  component LineChart: Item {
    id: chart
    property var points: []
    property color lineColor
    property color fillColor
    property color peakColor
    property color textColor
    property string fontFamily
    property var tooltipHost: null
    property var pointText: function(p) { return "" }

    readonly property real labelStrip: Style.space(12)
    readonly property real chartTop: Style.space(4)
    readonly property real chartBottom: height - labelStrip
    readonly property real peakValue: {
      var best = 0
      for (var i = 0; i < points.length; i++) best = Math.max(best, M.num(points[i].tokens))
      return best
    }

    onPointsChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()

    function xAt(i) { return points.length > 1 ? width * i / (points.length - 1) : width / 2 }
    function yAt(i) {
      var share = M.shareOfPeak(M.num(points[i].tokens), peakValue)
      return chartBottom - (chartBottom - chartTop) * share
    }

    Canvas {
      id: canvas
      anchors.fill: parent

      onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        if (chart.points.length < 2) {
          if (chart.points.length === 1) {
            ctx.fillStyle = chart.lineColor
            ctx.beginPath()
            ctx.arc(chart.xAt(0), chart.yAt(0), Math.max(1.5, Style.space(1)), 0, Math.PI * 2)
            ctx.fill()
          }
          return
        }
        var path = []
        for (var i = 0; i < chart.points.length; i++)
          path.push({ x: chart.xAt(i), y: chart.yAt(i) })

        ctx.beginPath()
        ctx.moveTo(path[0].x, chart.chartBottom)
        for (var j = 0; j < path.length; j++) ctx.lineTo(path[j].x, path[j].y)
        ctx.lineTo(path[path.length - 1].x, chart.chartBottom)
        ctx.closePath()
        ctx.fillStyle = chart.fillColor
        ctx.fill()

        ctx.beginPath()
        ctx.moveTo(path[0].x, path[0].y)
        for (var k = 1; k < path.length; k++) ctx.lineTo(path[k].x, path[k].y)
        ctx.strokeStyle = chart.lineColor
        ctx.lineWidth = Math.max(1, Style.space(0.6))
        ctx.lineJoin = "round"
        ctx.stroke()

        for (var m = 0; m < chart.points.length; m++) {
          if (chart.points[m].peak !== true) continue
          ctx.beginPath()
          ctx.arc(path[m].x, path[m].y, Math.max(1.5, Style.space(0.8)), 0, Math.PI * 2)
          ctx.fillStyle = chart.peakColor
          ctx.fill()
        }
      }
    }

    Repeater {
      model: chart.points.length

      Item {
        id: pointZone
        required property int index
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        x: chart.width * index / Math.max(1, chart.points.length - 1) - chart.width / Math.max(2, chart.points.length * 2)
        width: chart.width / Math.max(2, chart.points.length)

        Text {
          anchors.bottom: parent.bottom
          anchors.horizontalCenter: parent.horizontalCenter
          visible: pointZone.index === 0
                    || pointZone.index === chart.points.length - 1
                    || (chart.points.length > 8 && pointZone.index % Math.ceil(chart.points.length / 5) === 0)
          text: {
            var label = String(chart.points[pointZone.index].label)
            return label.length >= 13 ? label.substring(11, 16) : label.substring(5)
          }
          color: chart.textColor
          font.family: chart.fontFamily
          font.pixelSize: Style.font.caption
        }

        MouseArea {
          anchors.fill: parent
          hoverEnabled: true
          onEntered: if (chart.tooltipHost && chart.tooltipHost.bar)
            chart.tooltipHost.bar.showTooltip(pointZone, chart.pointText(chart.points[pointZone.index]))
          onExited: if (chart.tooltipHost && chart.tooltipHost.bar)
            chart.tooltipHost.bar.hideTooltip(pointZone)
        }
      }
    }
  }

  component QuotaMeter: Column {
    property string label: ""
    property var window: null
    readonly property bool live: window && window.present === true

    width: parent.width
    spacing: Style.space(6)
    visible: live

    Item {
      width: parent.width
      implicitHeight: Math.max(labelText.implicitHeight, percentText.implicitHeight)

      Text {
        id: labelText
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        text: label
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        id: percentText
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: window && window.percent !== null && window.percent !== undefined ? M.percent(window.percent) : "—"
        color: root.severityColor(window ? window.percent : null)
        font.family: root.fontFamily
        font.pixelSize: Style.font.heading
        font.bold: true
      }
    }

    Item {
      width: parent.width
      height: Style.space(10)

      Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.track
      }

      Rectangle {
        width: Math.max(height, parent.width * M.meterFraction(window ? window.percent : null))
        height: parent.height
        radius: height / 2
        color: root.severityColor(window ? window.percent : null)
        Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
      }
    }

    Item {
      width: parent.width
      implicitHeight: Math.max(creditsText.implicitHeight, resetText.implicitHeight)

      Text {
        id: creditsText
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        text: window && window.used !== null && window.used !== undefined && window.budget
          ? M.credits(window.used) + " / " + M.credits(window.budget) + " credits" : ""
        color: root.faint
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Text {
        id: resetText
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: window && window.resetsAtMs
          ? M.resetLine(window.resetsAtMs, root.nowMs, root.langEffective) : ""
        color: root.faint
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
  }
}
