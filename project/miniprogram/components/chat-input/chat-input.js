const { debounce, vibrateShort, showToast } = require('../../utils/util')
const api = require('../../utils/api')

const EMOJI_LIST = [
  '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂',
  '🙂', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗',
  '😚', '😙', '🥲', '😋', '😛', '😜', '🤪', '😝',
  '🤗', '🤭', '🤫', '🤔', '🫡', '🤐', '🤨', '😐',
  '😑', '😶', '🫥', '😏', '😒', '🙄', '😬', '🤥',
  '😌', '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕',
  '🤢', '🤮', '🥵', '🥶', '🥴', '😵', '🤯', '🤠',
  '🥳', '🥸', '😎', '🤓', '🧐', '😕', '🫤', '😟',
  '🙁', '😮', '😯', '😲', '😳', '🥺', '🥹', '😦',
  '😧', '😨', '😰', '😥', '😢', '😭', '😱', '😖',
  '😣', '😞', '😓', '😩', '😫', '🥱', '😤', '😡',
  '😠', '🤬', '👍', '👎', '👏', '🙏', '💪', '❤️',
]

const MAX_RECORD_TIME = 60

Component({
  properties: {
    disabled: {
      type: Boolean,
      value: false,
    },
    suggestions: {
      type: Array,
      value: [],
    },
    showVoice: {
      type: Boolean,
      value: false,
    },
  },

  data: {
    inputValue: '',
    hasInput: false,
    showEmoji: false,
    emojiList: EMOJI_LIST,
    isRecording: false,
    recordingStatusText: '正在录音...',
    recordTimeText: '0:00',
    volumeLevel: 0,
    recordTime: 0,
  },

  lifetimes: {
    attached() {
      this.fetchSuggestions = debounce((content) => {
        this.triggerEvent('typing', { content })
      }, 500)

      this._recorderManager = wx.getRecorderManager()

      this._recorderManager.onStart(() => {
        vibrateShort()
        this.startRecordTimer()
      })

      this._recorderManager.onStop((res) => {
        this.stopRecordTimer()
        if (res.tempFilePath) {
          this.recognizeAndSend(res.tempFilePath, res.duration || 0)
        }
      })

      this._recorderManager.onError((err) => {
        this.stopRecordTimer()
        this.setData({ isRecording: false })
        if (err.errMsg && err.errMsg.includes('auth deny')) {
          showToast('请授权麦克风权限')
        }
      })
    },
  },

  methods: {
    onInput(e) {
      const value = e.detail.value
      this.setData({ inputValue: value, hasInput: !!value.trim() })
      if (value.trim()) {
        this.fetchSuggestions(value)
      }
    },

    onSend() {
      const content = this.data.inputValue.trim()
      if (!content || this.data.disabled) return

      this.triggerEvent('send', {
        content,
        contentType: 'text',
      })

      this.setData({ inputValue: '', hasInput: false, showEmoji: false })
    },

    onSuggestionTap(e) {
      const text = e.currentTarget.dataset.text
      this.triggerEvent('send', {
        content: text,
        contentType: 'text',
      })
      this.setData({ inputValue: '', hasInput: false, showEmoji: false })
    },

    toggleEmoji() {
      this.setData({ showEmoji: !this.data.showEmoji })
    },

    onEmojiTap(e) {
      const emoji = e.currentTarget.dataset.emoji
      const newValue = this.data.inputValue + emoji
      this.setData({ inputValue: newValue, hasInput: true })
    },

    async chooseImage() {
      wx.chooseMedia({
        count: 1,
        mediaType: ['image'],
        sourceType: ['album', 'camera'],
        sizeType: ['compressed'],
        success: async (res) => {
          const tempFilePath = res.tempFiles[0].tempFilePath
          try {
            const uploadRes = await api.uploadFile('/voice/upload-image', tempFilePath, 'image')
            const serverPath = uploadRes.path || ''
            this.triggerEvent('send', {
              content: '[图片]',
              contentType: 'image',
              mediaUrl: serverPath || tempFilePath,
              localImagePath: tempFilePath,
            })
          } catch (e) {
            this.triggerEvent('send', {
              content: '[图片]',
              contentType: 'image',
              mediaUrl: tempFilePath,
              localImagePath: tempFilePath,
            })
          }
        },
      })
    },

    onVoiceTap() {
      if (this.data.disabled) return

      if (this.data.isRecording) {
        this.onVoiceEnd()
        return
      }

      wx.getSetting({
        success: (res) => {
          if (res.authSetting['scope.record'] === false) {
            wx.showModal({
              title: '需要麦克风权限',
              content: '请在设置中开启麦克风权限',
              confirmText: '去设置',
              success: (modalRes) => {
                if (modalRes.confirm) wx.openSetting()
              },
            })
            return
          }
          this.setData({
            isRecording: true,
            recordTime: 0,
            recordTimeText: '0:00',
            recordingStatusText: '正在录音...',
            volumeLevel: 0,
          })
          this._recorderManager.start({
            format: 'mp3',
            sampleRate: 16000,
            numberOfChannels: 1,
            encodeBitRate: 96000,
            duration: MAX_RECORD_TIME * 1000,
          })
        },
      })
    },

    onVoiceEnd() {
      if (!this.data.isRecording) return
      this.setData({ isRecording: false, recordingStatusText: '识别中...' })
      this._recorderManager.stop()
    },

    onVoiceCancel() {
      if (!this.data.isRecording) return
      this.stopRecordTimer()
      this.setData({ isRecording: false })
      this._recorderManager.stop()
    },

    startRecordTimer() {
      this.setData({ recordTime: 0 })
      this._recordTimer = setInterval(() => {
        const time = this.data.recordTime + 1
        const minutes = Math.floor(time / 60)
        const seconds = time % 60
        this.setData({
          recordTime: time,
          recordTimeText: `${minutes}:${seconds.toString().padStart(2, '0')}`,
        })
        if (time >= MAX_RECORD_TIME) {
          this.onVoiceEnd()
        }
        if (time >= MAX_RECORD_TIME - 5) {
          this.setData({ recordingStatusText: `还可录制${MAX_RECORD_TIME - time}秒` })
        }
      }, 1000)
    },

    stopRecordTimer() {
      if (this._recordTimer) {
        clearInterval(this._recordTimer)
        this._recordTimer = null
      }
    },

    async recognizeAndSend(filePath, duration) {
      try {
        const res = await api.uploadFile('/voice/recognize', filePath, 'audio')
        if (res.success && res.text) {
          this.triggerEvent('voicesend', {
            text: res.text,
            duration: Math.round(duration / 1000),
            audioPath: filePath,
          })
        } else {
          this._localRecognize(filePath, duration)
        }
      } catch (e) {
        this._localRecognize(filePath, duration)
      }
    },

    _localRecognize(filePath, duration) {
      const self = this
      wx.showModal({
        title: '语音识别',
        content: '语音识别服务暂不可用，是否将语音转为文字手动输入？',
        confirmText: '手动输入',
        cancelText: '取消',
        success(modalRes) {
          if (modalRes.confirm) {
            wx.showModal({
              title: '输入语音内容',
              editable: true,
              placeholderText: '请输入您刚才说的话',
              success(inputRes) {
                if (inputRes.confirm && inputRes.content && inputRes.content.trim()) {
                  self.triggerEvent('voicesend', {
                    text: inputRes.content.trim(),
                    duration: Math.round(duration / 1000),
                  })
                }
              },
            })
          }
        },
      })
    },

    setInputValue(value) {
      this.setData({ inputValue: value, hasInput: !!value.trim() })
    },
  },
})
