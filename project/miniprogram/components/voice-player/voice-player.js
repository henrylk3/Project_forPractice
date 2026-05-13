const app = getApp()

Component({
  properties: {
    audioUrl: {
      type: String,
      value: '',
    },
    autoPlay: {
      type: Boolean,
      value: false,
    },
  },

  data: {
    isPlaying: false,
    hasPlayed: false,
    currentTime: 0,
    duration: 0,
    currentTimeText: '0:00',
    durationText: '0:00',
    progressPercent: 0,
  },

  observers: {
    audioUrl(url) {
      if (url) {
        this.initAudio(url)
      }
    },
  },

  lifetimes: {
    detached() {
      this.destroyAudio()
    },
  },

  methods: {
    initAudio(url) {
      this.destroyAudio()

      const fullUrl = url.startsWith('http') ? url : `${app.globalData.baseUrl.replace('/api/v1', '')}${url}`

      const audio = wx.createInnerAudioContext()
      audio.src = fullUrl
      audio.obeyMuteSwitch = false

      audio.onCanplay(() => {
        this.setData({ duration: audio.duration })
        this.updateTimeText()

        if (this.data.autoPlay) {
          this.play()
        }
      })

      audio.onTimeUpdate(() => {
        const currentTime = audio.currentTime
        const duration = audio.duration
        const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0

        this.setData({
          currentTime,
          duration,
          progressPercent,
        })
        this.updateTimeText()
      })

      audio.onEnded(() => {
        this.setData({
          isPlaying: false,
          hasPlayed: true,
          currentTime: 0,
          progressPercent: 0,
        })
        this.updateTimeText()
      })

      audio.onError((err) => {
        console.error('Audio playback error:', err)
        this.setData({ isPlaying: false })
      })

      this._audio = audio
    },

    destroyAudio() {
      if (this._audio) {
        this._audio.stop()
        this._audio.destroy()
        this._audio = null
      }
    },

    play() {
      if (this._audio) {
        this._audio.play()
        this.setData({ isPlaying: true, hasPlayed: true })
      }
    },

    pause() {
      if (this._audio) {
        this._audio.pause()
        this.setData({ isPlaying: false })
      }
    },

    stopPlay() {
      if (this._audio) {
        this._audio.stop()
        this.setData({
          isPlaying: false,
          currentTime: 0,
          progressPercent: 0,
        })
        this.updateTimeText()
      }
    },

    togglePlay() {
      if (this.data.isPlaying) {
        this.pause()
      } else {
        this.play()
      }
    },

    onProgressTap(e) {
      if (!this._audio || !this.data.duration) return

      const query = this.createSelectorQuery()
      query.select('.player-progress').boundingClientRect((rect) => {
        if (rect) {
          const tapX = e.detail.x - rect.left
          const percent = tapX / rect.width
          const seekTime = percent * this.data.duration
          this._audio.seek(seekTime)
        }
      }).exec()
    },

    updateTimeText() {
      this.setData({
        currentTimeText: this.formatTime(this.data.currentTime),
        durationText: this.formatTime(this.data.duration),
      })
    },

    formatTime(seconds) {
      const mins = Math.floor(seconds / 60)
      const secs = Math.floor(seconds % 60)
      return `${mins}:${secs.toString().padStart(2, '0')}`
    },
  },
})
