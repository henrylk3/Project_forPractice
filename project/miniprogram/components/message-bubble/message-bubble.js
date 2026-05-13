const { parseMarkdown, inlineFormat } = require('../../utils/markdown')

Component({
  properties: {
    message: {
      type: Object,
      value: {},
    },
    userAvatar: {
      type: String,
      value: '',
    },
  },

  data: {
    displayUserAvatar: '',
    mdNodes: [],
    isPlayingVoice: false,
  },

  observers: {
    'userAvatar': function(val) {
      if (val) {
        this.setData({ displayUserAvatar: val })
      } else {
        this.setData({ displayUserAvatar: '' })
      }
    },
    'message.content': function(val) {
      if (!this.properties.message || !this.properties.message.role) return
      if (this.properties.message.role === 'assistant' && val) {
        const mdNodes = parseMarkdown(val)
        mdNodes.forEach(node => {
          if (node.content) node.content = inlineFormat(node.content)
          if (node.items) node.items = node.items.map(inlineFormat)
        })
        this.setData({ mdNodes })
      } else {
        this.setData({ mdNodes: [] })
      }
    },
  },

  lifetimes: {
    detached() {
      if (this._voiceAudio) {
        this._voiceAudio.stop()
        this._voiceAudio.destroy()
        this._voiceAudio = null
      }
    },
  },

  methods: {
    onAvatarError() {
      this.setData({ displayUserAvatar: '' })
    },

    previewImage(e) {
      const url = e.currentTarget.dataset.url
      if (url) {
        wx.previewImage({
          current: url,
          urls: [url],
        })
      }
    },

    copyCode(e) {
      const code = e.currentTarget.dataset.code
      if (code) {
        wx.setClipboardData({
          data: code,
          success: () => {
            wx.showToast({ title: '已复制', icon: 'success' })
          },
        })
      }
    },

    onLongPressBubble() {
      const msg = this.properties.message
      if (!msg || !msg.content) return
      if (msg.contentType === 'image' || msg.contentType === 'voice' || msg.contentType === 'emoji') return

      wx.setClipboardData({
        data: msg.content,
        success: () => {
          wx.showToast({ title: '已复制', icon: 'success' })
        },
      })
    },

    playVoice() {
      const audioUrl = this.properties.message.audioUrl
      if (!audioUrl) return

      if (this._voiceAudio && this.data.isPlayingVoice) {
        this._voiceAudio.stop()
        this.setData({ isPlayingVoice: false })
        return
      }

      if (this._voiceAudio) {
        this._voiceAudio.destroy()
      }

      const audio = wx.createInnerAudioContext()
      audio.src = audioUrl
      audio.obeyMuteSwitch = false

      audio.onPlay(() => {
        this.setData({ isPlayingVoice: true })
      })

      audio.onEnded(() => {
        this.setData({ isPlayingVoice: false })
      })

      audio.onError(() => {
        this.setData({ isPlayingVoice: false })
      })

      audio.onStop(() => {
        this.setData({ isPlayingVoice: false })
      })

      this._voiceAudio = audio
      audio.play()
    },
  },
})
