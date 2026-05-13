function formatTime(date) {
  const year = date.getFullYear()
  const month = padZero(date.getMonth() + 1)
  const day = padZero(date.getDate())
  const hour = padZero(date.getHours())
  const minute = padZero(date.getMinutes())
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function formatMessageTime(dateStr) {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 60) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`

  return formatTime(date)
}

function padZero(num) {
  return num < 10 ? `0${num}` : `${num}`
}

function generateId() {
  return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

function truncateText(text, maxLength = 20) {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

function debounce(fn, delay = 300) {
  let timer = null
  return function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn.apply(this, args)
    }, delay)
  }
}

function throttle(fn, delay = 300) {
  let lastTime = 0
  return function (...args) {
    const now = Date.now()
    if (now - lastTime >= delay) {
      lastTime = now
      fn.apply(this, args)
    }
  }
}

function showToast(title, icon = 'none', duration = 2000) {
  wx.showToast({ title, icon, duration })
}

function showLoading(title = '加载中...') {
  wx.showLoading({ title, mask: true })
}

function hideLoading() {
  wx.hideLoading()
}

function showConfirm(content, title = '提示') {
  return new Promise((resolve) => {
    wx.showModal({
      title,
      content,
      success(res) {
        resolve(res.confirm)
      },
    })
  })
}

function vibrateShort() {
  try {
    wx.vibrateShort({ type: 'light' })
  } catch (e) {}
}

function resolveUrl(path) {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('wxfile://')) {
    return path
  }
  const app = getApp()
  const base = app.globalData.baseUrl.replace('/api/v1', '')
  if (path.startsWith('/')) {
    return base + path
  }
  return base + '/' + path
}

module.exports = {
  formatTime,
  formatMessageTime,
  padZero,
  generateId,
  truncateText,
  debounce,
  throttle,
  showToast,
  showLoading,
  hideLoading,
  showConfirm,
  vibrateShort,
  resolveUrl,
}
