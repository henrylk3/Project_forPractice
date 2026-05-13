App({
  globalData: {
    userInfo: null,
    token: null,
    baseUrl: 'http://10.30.2.175:8000/api/v1',
    isConnected: false,
    resumeConversationId: null,
    serverAvailable: true,
    lastCheckTime: 0,
  },

  onLaunch() {
    this.checkLoginStatus()
    this.monitorNetwork()
  },

  checkLoginStatus() {
    const token = wx.getStorageSync('token')
    const userInfo = wx.getStorageSync('userInfo')
    if (token && userInfo) {
      this.globalData.token = token
      this.globalData.userInfo = userInfo
      this.globalData.isConnected = true
      this._refreshLocalAvatar(userInfo)
    }
  },

  _refreshLocalAvatar(userInfo) {
    if (!userInfo) return
    const localAvatarUrl = userInfo.localAvatarUrl || ''

    if (localAvatarUrl) {
      const fs = wx.getFileSystemManager()
      try {
        fs.accessSync(localAvatarUrl)
        return
      } catch (e) {
        this._downloadServerAvatar(userInfo)
      }
      return
    }

    this._downloadServerAvatar(userInfo)
  },

  _downloadServerAvatar(userInfo) {
    const avatarUrl = userInfo.avatarUrl || ''
    if (!avatarUrl) return

    let fullUrl = avatarUrl
    if (avatarUrl.startsWith('/uploads/')) {
      const baseHost = this.globalData.baseUrl.replace('/api/v1', '')
      fullUrl = `${baseHost}${avatarUrl}`
    } else if (!avatarUrl.startsWith('http')) {
      return
    }

    wx.downloadFile({
      url: fullUrl,
      success: (downloadRes) => {
        if (downloadRes.statusCode === 200) {
          const fs = wx.getFileSystemManager()
          const savedPath = `${wx.env.USER_DATA_PATH}/avatar_${userInfo.id || 'default'}.png`
          try {
            try { fs.unlinkSync(savedPath) } catch (e) {}
            fs.saveFile({
              tempFilePath: downloadRes.tempFilePath,
              filePath: savedPath,
              success: () => {
                const updatedInfo = { ...userInfo, localAvatarUrl: savedPath }
                this.globalData.userInfo = updatedInfo
                wx.setStorageSync('userInfo', updatedInfo)
              },
              fail: () => {
                const updatedInfo = { ...userInfo, localAvatarUrl: downloadRes.tempFilePath }
                this.globalData.userInfo = updatedInfo
                wx.setStorageSync('userInfo', updatedInfo)
              },
            })
          } catch (e) {
            const updatedInfo = { ...userInfo, localAvatarUrl: downloadRes.tempFilePath }
            this.globalData.userInfo = updatedInfo
            wx.setStorageSync('userInfo', updatedInfo)
          }
        }
      },
    })
  },

  monitorNetwork() {
    wx.onNetworkStatusChange((res) => {
      if (!res.isConnected) {
        this.globalData.serverAvailable = false
      } else {
        this.globalData.serverAvailable = true
      }
    })
  },

  async checkServerAvailable() {
    const now = Date.now()
    if (now - this.globalData.lastCheckTime < 10000) {
      return this.globalData.serverAvailable
    }
    this.globalData.lastCheckTime = now

    try {
      const res = await new Promise((resolve, reject) => {
        wx.request({
          url: this.globalData.baseUrl.replace('/api/v1', '') + '/health',
          method: 'GET',
          timeout: 5000,
          success(r) { resolve(r) },
          fail() { reject() },
        })
      })
      this.globalData.serverAvailable = res.statusCode === 200
    } catch (e) {
      this.globalData.serverAvailable = false
    }
    return this.globalData.serverAvailable
  },

  setToken(token) {
    this.globalData.token = token
    wx.setStorageSync('token', token)
  },

  setUserInfo(userInfo) {
    this.globalData.userInfo = userInfo
    wx.setStorageSync('userInfo', userInfo)
    this._refreshLocalAvatar(userInfo)
  },

  logout() {
    this.globalData.token = null
    this.globalData.userInfo = null
    this.globalData.isConnected = false
    wx.removeStorageSync('token')
    wx.removeStorageSync('userInfo')
    wx.reLaunch({ url: '/pages/login/login' })
  },
})
