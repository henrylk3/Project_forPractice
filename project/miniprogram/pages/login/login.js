const app = getApp()
const api = require('../../utils/api')
const { showToast } = require('../../utils/util')

Page({
  data: {
    isLoading: false,
    canLogin: true,
    showProfile: false,
    isSaving: false,
    loginError: '',
    tempAvatarUrl: '',
    tempNickname: '',
    loginCode: '',
  },

  async onWxLogin() {
    if (this.data.isLoading) return
    this.setData({ isLoading: true, loginError: '' })

    try {
      const loginRes = await new Promise((resolve, reject) => {
        wx.login({
          success(res) { resolve(res) },
          fail(err) { reject(err) },
        })
      })

      if (!loginRes.code) {
        this.setData({ loginError: '微信登录失败，请重试', isLoading: false })
        return
      }

      const res = await api.post('/auth/wx-login', {
        code: loginRes.code,
        nickname: null,
        avatar_url: null,
      })

      app.setToken(res.access_token)
      app.setUserInfo({
        id: res.user_id,
        nickname: res.nickname,
        avatarUrl: res.avatar_url,
      })

      this.setData({ isLoading: false })

      if (!res.nickname || res.nickname === '用户') {
        this.setData({
          showProfile: true,
          tempNickname: '',
          tempAvatarUrl: '',
        })
      } else {
        wx.switchTab({ url: '/pages/chat/chat' })
      }
    } catch (e) {
      this.setData({ isLoading: false })
      if (e.code === 503) {
        this.setData({ loginError: '微信登录暂不可用，请联系管理员' })
      } else {
        this.setData({ loginError: e.message || '登录失败，请重试' })
      }
    }
  },

  onChooseAvatar(e) {
    const avatarUrl = e.detail.avatarUrl
    if (avatarUrl) {
      this.setData({ tempAvatarUrl: avatarUrl })
    }
  },

  onNicknameInput(e) {
    this.setData({ tempNickname: e.detail.value })
  },

  onNicknameBlur(e) {
    this.setData({ tempNickname: e.detail.value })
  },

  async onStartChat() {
    if (this.data.isSaving) return

    const { tempNickname, tempAvatarUrl } = this.data
    const nickname = tempNickname.trim() || '用户'

    this.setData({ isSaving: true })

    try {
      let avatarPath = null
      let localAvatarUrl = ''

      if (tempAvatarUrl && (tempAvatarUrl.startsWith('wxfile://') || tempAvatarUrl.startsWith('http://tmp'))) {
        try {
          const uploadRes = await api.uploadFile('/auth/upload-avatar', tempAvatarUrl, 'avatar')
          avatarPath = uploadRes.path || null

          const fs = wx.getFileSystemManager()
          const userId = app.globalData.userInfo?.id || 'default'
          const savedPath = `${wx.env.USER_DATA_PATH}/avatar_${userId}.png`
          try {
            try { fs.unlinkSync(savedPath) } catch (e) {}
            await new Promise((resolve, reject) => {
              fs.saveFile({
                tempFilePath: tempAvatarUrl,
                filePath: savedPath,
                success: resolve,
                fail: reject,
              })
            })
            localAvatarUrl = savedPath
          } catch (e) {
            localAvatarUrl = tempAvatarUrl
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
        ...app.globalData.userInfo,
        nickname,
        avatarUrl: avatarPath || app.globalData.userInfo.avatarUrl,
        localAvatarUrl: localAvatarUrl || app.globalData.userInfo.localAvatarUrl,
      }
      app.setUserInfo(userInfo)

      wx.switchTab({ url: '/pages/chat/chat' })
    } catch (e) {
      showToast(e.message || '保存失败')
    } finally {
      this.setData({ isSaving: false })
    }
  },
})
