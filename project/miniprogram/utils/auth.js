const app = getApp()

function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (res.code) {
          resolve(res.code)
        } else {
          reject(new Error('微信登录失败'))
        }
      },
      fail(err) {
        reject(err)
      },
    })
  })
}

function checkAuth() {
  return !!app.globalData.token
}

function requireAuth(page) {
  if (!checkAuth()) {
    wx.navigateTo({ url: '/pages/login/login' })
    return false
  }
  return true
}

module.exports = {
  wxLogin,
  checkAuth,
  requireAuth,
}
