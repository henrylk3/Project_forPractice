const app = getApp()
const api = require('../../utils/api')
const storage = require('../../utils/storage')
const { showToast, showConfirm, showLoading, hideLoading } = require('../../utils/util')

Page({
  data: {
    userInfo: {},
    isLogged: false,
    cacheSize: '',
    showProfileEdit: false,
    editNickname: '',
    editAvatarUrl: '',
    displayAvatarUrl: '',
  },

  onShow() {
    this.loadUserInfo()
    this.loadCacheSize()
  },

  loadUserInfo() {
    const userInfo = app.globalData.userInfo
    const isLogged = !!app.globalData.token

    let displayUrl = ''
    if (userInfo) {
      const url = userInfo.localAvatarUrl || userInfo.avatarUrl
      if (url) {
        if (url.startsWith('/uploads/')) {
          displayUrl = app.globalData.baseUrl.replace('/api/v1', '') + url
        } else {
          displayUrl = url
        }
      }
    }

    this.setData({
      userInfo: userInfo || {},
      isLogged,
      displayAvatarUrl: displayUrl,
    })
  },

  loadCacheSize() {
    const info = storage.getStorageSize()
    if (info) {
      this.setData({ cacheSize: `${info.currentSize} KB` })
    }
  },

  goProfileEdit() {
    if (!this.data.isLogged) {
      wx.navigateTo({ url: '/pages/login/login' })
      return
    }

    this.setData({
      showProfileEdit: true,
      editNickname: this.data.userInfo.nickname || '',
      editAvatarUrl: this.data.displayAvatarUrl || '',
    })
  },

  hideProfileEdit() {
    this.setData({ showProfileEdit: false })
  },

  onNicknameInput(e) {
    this.setData({ editNickname: e.detail.value })
  },

  chooseAvatar() {
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        this.setData({ editAvatarUrl: res.tempFilePaths[0] })
      },
    })
  },

  async saveProfile() {
    const { editNickname, editAvatarUrl } = this.data
    const nickname = editNickname.trim()

    if (!nickname) {
      showToast('昵称不能为空')
      return
    }

    showLoading('保存中...')

    try {
      let avatarPath = null
      let localAvatarUrl = editAvatarUrl

      if (editAvatarUrl && (editAvatarUrl.startsWith('http://tmp') || editAvatarUrl.startsWith('wxfile://'))) {
        try {
          const uploadRes = await api.uploadFile('/auth/upload-avatar', editAvatarUrl, 'avatar')
          avatarPath = uploadRes.path || null

          const fs = wx.getFileSystemManager()
          const userId = app.globalData.userInfo?.id || 'default'
          const savedPath = `${wx.env.USER_DATA_PATH}/avatar_${userId}.png`
          try {
            try { fs.unlinkSync(savedPath) } catch (e) {}
            await new Promise((resolve, reject) => {
              fs.saveFile({
                tempFilePath: editAvatarUrl,
                filePath: savedPath,
                success: resolve,
                fail: reject,
              })
            })
            localAvatarUrl = savedPath
          } catch (e) {
            localAvatarUrl = editAvatarUrl
          }
        } catch (e) {
          console.error('Avatar upload failed:', e)
        }
      }

      await api.put('/auth/me', {
        nickname,
        avatar_url: avatarPath,
      })

      const userInfo = {
        ...this.data.userInfo,
        nickname,
        avatarUrl: avatarPath || this.data.userInfo.avatarUrl,
        localAvatarUrl: localAvatarUrl || this.data.userInfo.localAvatarUrl,
      }
      app.setUserInfo(userInfo)

      this.setData({
        userInfo,
        displayAvatarUrl: localAvatarUrl,
        showProfileEdit: false,
      })

      showToast('资料已更新')
    } catch (e) {
      showToast(e.message || '保存失败')
    }

    hideLoading()
  },

  goHelp() {
    wx.navigateTo({ url: '/pages/help/help' })
  },

  goSearch() {
    wx.navigateTo({ url: '/pages/search/search' })
  },

  async clearCache() {
    const confirmed = await showConfirm('确定要清除所有缓存数据吗？')
    if (confirmed) {
      showLoading('清除中...')
      storage.clearAllData()
      if (app.globalData.token) {
        wx.setStorageSync('token', app.globalData.token)
        wx.setStorageSync('userInfo', app.globalData.userInfo)
      }
      this.loadCacheSize()
      hideLoading()
      showToast('缓存已清除')
    }
  },

  onLogout() {
    app.logout()
  },

  goStats() {
    wx.navigateTo({ url: '/pages/stats/stats' })
  },

  onAvatarError() {
    this.setData({ displayAvatarUrl: '' })
  },
})
