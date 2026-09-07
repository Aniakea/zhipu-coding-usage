// Pure helpers for the Zhipu Coding Usage panel. No filesystem, no scene
// graph — formatting only, so every value stays trivially checkable.
.pragma library

function num(value, fallback) {
  var n = Number(value)
  return isFinite(n) ? n : (fallback === undefined ? 0 : fallback)
}

function clamp(value, lo, hi) {
  return Math.max(lo, Math.min(hi, num(value)))
}

function group(value) {
  var n = Math.round(num(value))
  var sign = n < 0 ? "-" : ""
  return sign + String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

// The record's percent is 0-100 with one decimal; the bar wants none.
function percent(pct) {
  return Math.round(num(pct)) + "%"
}

function credits(value) {
  var n = num(value)
  if (n === 0) return "0"
  if (n < 100) return n.toFixed(1)
  return group(n)
}

function tokens(value) {
  var n = num(value)
  if (n < 1000) return String(Math.round(n))
  if (n < 1000000) return (n / 1000).toFixed(n < 10000 ? 1 : 0) + "K"
  if (n < 1000000000) return (n / 1000000).toFixed(n < 10000000 ? 1 : 0) + "M"
  return (n / 1000000000).toFixed(1) + "B"
}

// Countdown to an epoch-ms stamp, in the one or two coarse units a glance reads.
function untilTextMs(targetMs, nowMs) {
  var target = num(targetMs)
  if (target <= 0) return ""
  var delta = target - num(nowMs, Date.now())
  if (delta <= 0) return "now"

  var minutes = Math.floor(delta / 60000)
  if (minutes < 1) return "<1m"
  if (minutes < 60) return minutes + "m"

  var hours = Math.floor(minutes / 60)
  if (hours < 24) {
    var restMinutes = minutes % 60
    return restMinutes > 0 ? hours + "h " + restMinutes + "m" : hours + "h"
  }

  var days = Math.floor(hours / 24)
  var restHours = hours % 24
  return restHours > 0 ? days + "d " + restHours + "h" : days + "d"
}

// Wall-clock time for the same stamp, so the panel can say both "in 2h 5m"
// and the absolute local time the window rolls over.
function clockTextMs(targetMs) {
  var target = num(targetMs)
  if (target <= 0) return ""
  var d = new Date(target)
  var hh = String(d.getHours()).padStart(2, "0")
  var mm = String(d.getMinutes()).padStart(2, "0")
  var days = Math.floor((target - new Date().setHours(0, 0, 0, 0)) / 86400000)
  if (days <= 0) return hh + ":" + mm
  return (d.getMonth() + 1) + "/" + d.getDate() + " " + hh + ":" + mm
}

function agoText(isoString, nowMs) {
  var stamp = Date.parse(String(isoString || ""))
  if (!isFinite(stamp)) return ""
  var delta = num(nowMs, Date.now()) - stamp
  if (delta < 0) return "just now"
  var seconds = Math.floor(delta / 1000)
  if (seconds < 45) return "just now"
  var minutes = Math.floor(seconds / 60)
  if (minutes < 60) return minutes + "m ago"
  var hours = Math.floor(minutes / 60)
  if (hours < 24) return hours + "h ago"
  return Math.floor(hours / 24) + "d ago"
}

// Quota meters are meaningless past full, but the number above them is not.
function meterFraction(pct) {
  if (pct === null || pct === undefined) return 0
  return clamp(num(pct) / 100, 0, 1)
}

function shareOfPeak(value, peakValue) {
  var p = num(peakValue)
  return p > 0 ? clamp(num(value) / p, 0, 1) : 0
}

// ------------------------------------------------------------------- i18n

function strings(lang) {
  var zh = lang === "zh"
  return {
    fiveHour: zh ? "5 小时额度" : "5-hour window",
    weekly: zh ? "每周额度" : "Weekly quota",
    notReported: zh ? "本套餐未上报：每周额度" : "Not reported on this plan: weekly quota",
    requests24h: zh ? "请求 · 24h" : "requests · 24h",
    tokens24h: zh ? "Tokens · 24h" : "tokens · 24h",
    webSearch24h: zh ? "联网搜索 · 24h" : "web search · 24h",
    webRead24h: zh ? "网页读取 · 24h" : "web read · 24h",
    offPeakShare: zh ? "闲时用量占比" : "off-peak share",
    modelsTitle: zh ? "模型 · 最近 24 小时" : "Models · last 24h",
    tokensChart: zh ? "Token 消耗" : "Token consumption",
    range24h: "24h",
    rangeDaily: zh ? "日" : "day",
    rangeWeekly: zh ? "周" : "week",
    rangeMonthly: zh ? "月" : "month",
    noUsage: zh ? "最近 24 小时没有模型用量。\n运行 GLM 模型后此处会自动填充。"
               : "No model usage in the last 24 hours.\nRun a GLM model and this fills in.",
    live: zh ? "实时" : "live",
    stale: zh ? "过期" : "stale",
    refreshing: zh ? "刷新中…" : "refreshing…",
    updated: zh ? "更新于 " : "updated ",
    pace: zh ? "按当前速率" : "on this pace",
    peak: zh ? "峰时 3×" : "peak 3×",
    offPeak: zh ? "闲时 1×" : "off-peak 1×",
    peakBar: zh ? "峰时" : "peak",
    offPeakBar: zh ? "闲时" : "off-peak",
    refreshHint: zh ? "r 刷新 · b 用量页" : "r refresh · b usage"
  }
}

// "resets in 3h 5m · 21:16" / "3小时5分后重置 · 21:16"
function resetLine(targetMs, nowMs, lang) {
  var countdown = untilTextMs(targetMs, nowMs)
  if (countdown === "") return ""
  var clock = clockTextMs(targetMs)
  var head = lang === "zh" ? countdown + "后重置" : "resets in " + countdown
  return clock !== "" ? head + " · " + clock : head
}

// "on this pace: exhausts Wed 14:00 (2d 3h left)" / "按当前速率约周三 14:00 耗尽（剩 2天3小时）"
function paceLine(projection, lang) {
  if (!projection || !projection.exhaustsAtMs) return ""
  var d = new Date(projection.exhaustsAtMs)
  var hhmm = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0")
  var inText = untilTextMs(projection.exhaustsAtMs, Date.now())
  if (lang === "zh") {
    var weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
    return "按当前速率约 " + weekdays[d.getDay()] + " " + hhmm + " 耗尽（剩 " + inText + "）"
  }
  var en = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
  return "on this pace: exhausts " + en[d.getDay()] + " " + hhmm + " (" + inText + " left)"
}
