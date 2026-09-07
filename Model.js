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
