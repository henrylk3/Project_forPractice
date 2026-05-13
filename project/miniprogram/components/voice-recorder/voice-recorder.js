const api = require('../../utils/api')
const { showToast, vibrateShort } = require('../../utils/util')

const MAX_RECORD_TIME = 60

Component({
  properties: {
    disabled: {
      type: Boolean,
      value: false,
    },
  },

  data: {
    isRecording: false,
    recordTime: 0,
    recordTimeText: '0:00',
    recordStatusText: '正在录音...',
    volumeLevel: 0,
    recorderManager: null,
    tempFilePath: '',
    timer: null,
  },

  lifetimes: {
    attached() {
      this.setData({
        recorderManager: wx.getRecorderManager(),
      })

      const manager = this.data.recorderManager

      manager.onStart(() => {
        this.startTimer()
        vibrateShort()
      })

      manager.onStop((res) => {
        this.stopTimer()
        if (res.tempFilePath) {
          this.setData({ tempFilePath: res.tempFilePath })
          this.recognizeAndSend(res.tempFilePath, res.duration || 0)
        }
      })

      manager.onError((err) => {
        this.stopTimer()
        this.setData({ isRecording: false })
        console.error('Recording error:', err)
        if (err.errMsg && err.errMsg.includes('auth deny')) {
          showToast('请授权麦克风权限后再使用语音功能')
        } else {
          showToast('录音失败，请重试')
        }
      })

      manager.onFrameRecorded((res) => {
        if (res.frameBuffer) {
          const volume = Math.min(Math.floor(res.frameBuffer.byteLength / 100), 8)
          this.setData({ volumeLevel: volume })
        }
      })
    },
  },

  methods: {
    onTouchStart() {
      if (this.data.disabled) return
      this.startRecord()
    },

    onTouchEnd() {
      if (!this.data.isRecording) return
      this.stopRecord()
    },

    onTouchCancel() {
      if (!this.data.isRecording) return
      this.cancelRecord()
    },

    startRecord() {
      wx.getSetting({
        success: (res) => {
          if (res.authSetting['scope.record'] === false) {
            wx.showModal({
              title: '需要麦克风权限',
              content: '请在设置中开启麦克风权限以使用语音功能',
              confirmText: '去设置',
              success: (modalRes) => {
                if (modalRes.confirm) {
                  wx.openSetting()
                }
              },
            })
            return
          }

          this.setData({
            isRecording: true,
            recordTime: 0,
            recordTimeText: '0:00',
            recordStatusText: '正在录音...',
            volumeLevel: 0,
          })

          this.data.recorderManager.start({
            format: 'mp3',
            sampleRate: 16000,
            numberOfChannels: 1,
            encodeBitRate: 96000,
            duration: MAX_RECORD_TIME * 1000,
          })
        },
      })
    },

    stopRecord() {
      this.setData({
        isRecording: false,
        recordStatusText: '识别中...',
        volumeLevel: 0,
      })
      this.data.recorderManager.stop()
    },

    cancelRecord() {
      this.stopTimer()
      this.setData({
        isRecording: false,
        recordTime: 0,
        recordTimeText: '0:00',
        volumeLevel: 0,
      })
      this.data.recorderManager.stop()
    },

    startTimer() {
      this.setData({ recordTime: 0 })
      this.data.timer = setInterval(() => {
        const time = this.data.recordTime + 1
        const minutes = Math.floor(time / 60)
        const seconds = time % 60
        this.setData({
          recordTime: time,
          recordTimeText: `${minutes}:${seconds.toString().padStart(2, '0')}`,
        })

        if (time >= MAX_RECORD_TIME) {
          this.stopRecord()
        }

        if (time >= MAX_RECORD_TIME - 5) {
          this.setData({ recordStatusText: `还可录制${MAX_RECORD_TIME - time}秒` })
        }
      }, 1000)
    },

    stopTimer() {
      if (this.data.timer) {
        clearInterval(this.data.timer)
        this.data.timer = null
      }
    },

    async recognizeAndSend(filePath, duration) {
      try {
        const res = await api.uploadFile('/voice/recognize', filePath, 'audio')

        if (res.success && res.text) {
          this.triggerEvent('voicesend', {
            text: res.text,
            duration: Math.round(duration / 1000),
            confidence: res.confidence,
          })
        } else {
          showToast(res.message || '语音识别失败，请使用文字输入')
        }
      } catch (e) {
        console.error('Voice recognition error:', e)
        showToast('语音识别失败，请使用文字输入')
      }
    },
  },
})
