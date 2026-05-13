const app = getApp()
const api = require('../../utils/api')
const storage = require('../../utils/storage')
const { generateId, formatMessageTime, vibrateShort, showToast } = require('../../utils/util')

Page({
  data: {
    messages: [],
    conversationId: null,
    isLoading: false,
    suggestions: [],
    userInfo: null,
    scrollTop: 0,
    showScrollBtn: false,
    page: 1,
    hasMore: false,
    autoPlayVoice: true,
  },

  _isAutoScrolling: false,
  _scrollTimer: null,

  _getDisplayAvatar(userInfo) {
    if (!userInfo) return ''
    const url = userInfo.localAvatarUrl || userInfo.avatarUrl || ''
    if (url.startsWith('/uploads/')) {
      return app.globalData.baseUrl.replace('/api/v1', '') + url
    }
    return url
  },

  onLoad(options) {
    const userInfo = app.globalData.userInfo
    const settings = storage.getSettings()
    this.setData({
      userInfo,
      userAvatar: this._getDisplayAvatar(userInfo),
      autoPlayVoice: settings.autoPlayVoice !== false,
    })

    if (options.conversationId) {
      this.setData({ conversationId: options.conversationId })
      this.loadMessages(options.conversationId)
    }

    const draft = storage.getDraft(this.data.conversationId || 'new')
    if (draft) {
      const chatInput = this.selectComponent('#chatInput')
      if (chatInput) {
        chatInput.setInputValue(draft)
      }
    }
  },

  onShow() {
    const userInfo = app.globalData.userInfo
    if (userInfo) {
      this.setData({ userInfo, userAvatar: this._getDisplayAvatar(userInfo) })
    }

    if (app.globalData.resumeConversationId) {
      const convId = app.globalData.resumeConversationId
      app.globalData.resumeConversationId = null
      this.setData({ conversationId: convId, messages: [], page: 1, scrollTop: 0, showScrollBtn: false })
      this.loadMessages(convId)
      return
    }
  },

  onHide() {
    const chatInput = this.selectComponent('#chatInput')
    if (chatInput) {
      const draft = chatInput.data.inputValue
      if (draft) {
        storage.saveDraft(this.data.conversationId || 'new', draft)
      }
    }
  },

  async loadMessages(conversationId) {
    try {
      let allMessages = []
      let page = 1
      let hasMore = true
      let maxPages = 50

      while (hasMore && page <= maxPages) {
        const res = await api.get(`/chat/conversations/${conversationId}/messages?page=${page}&page_size=100`)
        const formatted = res.messages.map((msg) => this.formatMessage(msg)).filter(Boolean)
        allMessages = allMessages.concat(formatted)
        hasMore = res.has_more
        page++
      }

      this.setData({ messages: allMessages, showScrollBtn: true })

      this._isAutoScrolling = true
      setTimeout(() => { this.scrollToBottom() }, 100)
      setTimeout(() => { this.scrollToBottom() }, 500)
      setTimeout(() => { this.scrollToBottom() }, 1000)
      setTimeout(() => { this._isAutoScrolling = false }, 2000)
    } catch (e) {
      console.error('Load messages error:', e)
    }
  },

  startNewChat() {
    this.setData({
      conversationId: null,
      messages: [],
      page: 1,
      hasMore: false,
      suggestions: [],
      scrollTop: 0,
      showScrollBtn: false,
    })
    const chatInput = this.selectComponent('#chatInput')
    if (chatInput) {
      chatInput.setData({ inputValue: '', hasInput: false })
    }
  },

  _scheduleScrollToBottom() {
    if (this._scrollTimer) {
      clearTimeout(this._scrollTimer)
    }
    this._scrollTimer = setTimeout(() => {
      this.scrollToBottom()
      this._scrollTimer = setTimeout(() => {
        this.scrollToBottom()
      }, 500)
    }, 150)
  },

  async onSendMessage(e) {
    const { content, contentType, mediaUrl, localImagePath } = e.detail || {}
    if (!content || !content.trim() || this.data.isLoading) return

    vibrateShort()

    const tempId = generateId()
    const userMessage = {
      id: tempId,
      role: 'user',
      content,
      contentType: contentType || 'text',
      mediaUrl: '',
      localImagePath: localImagePath || '',
      serverMediaUrl: mediaUrl || '',
      status: 'sending',
      timeText: '刚刚',
      created_at: new Date().toISOString(),
    }

    const botTempId = generateId()
    const botMessage = {
      id: botTempId,
      role: 'assistant',
      content: '',
      contentType: 'text',
      status: 'read',
      timeText: '刚刚',
      created_at: new Date().toISOString(),
      audioUrl: null,
      autoPlayAudio: false,
    }

    this.setData({
      messages: [...this.data.messages, userMessage, botMessage],
      isLoading: true,
      suggestions: [],
      showScrollBtn: false,
    })
    this._scheduleScrollToBottom()
    storage.clearDraft(this.data.conversationId || 'new')

    const botIndex = this.data.messages.length - 1

    try {
      const res = await api.post('/chat/send', {
        conversation_id: this.data.conversationId,
        content,
        content_type: contentType || 'text',
        media_url: userMessage.serverMediaUrl || null,
      })

      this.setData({
        conversationId: res.conversation_id,
        [`messages[${botIndex}].content`]: res.content || '',
        [`messages[${botIndex}].id`]: res.message_id || botTempId,
        [`messages[${botIndex}].timeText`]: formatMessageTime(res.created_at),
        isLoading: false,
      })
      this._scheduleScrollToBottom()

      const msgIndex = this.data.messages.findIndex((m) => m && m.id === tempId)
      if (msgIndex !== -1) {
        this.setData({ [`messages[${msgIndex}].status`]: 'sent' })
      }

      if (this.data.conversationId) {
        storage.saveMessages(this.data.conversationId, this.data.messages)
      }

    } catch (err) {
      const msgIndex = this.data.messages.findIndex((m) => m && m.id === tempId)
      if (msgIndex !== -1) {
        this.setData({ [`messages[${msgIndex}].status`]: 'failed' })
      }

      this.setData({
        [`messages[${botIndex}].content`]: err.message || '回复失败，请重试',
        isLoading: false,
      })
      this._scheduleScrollToBottom()

      if (err.code === -1) {
        showToast('网络连接失败，请检查网络')
      } else if (err.code === 401) {
        showToast('登录已过期，请重新登录')
      }
    }
  },

  async onVoiceSend(e) {
    const { text, duration, audioPath } = e.detail
    if (!text || !text.trim()) return

    let serverAudioUrl = null
    if (audioPath) {
      try {
        const uploadRes = await api.uploadFile('/voice/upload-audio', audioPath, 'audio')
        serverAudioUrl = uploadRes.path || null
      } catch (e) {
        console.error('[onVoiceSend] audio upload failed:', e)
      }
    }

    const tempId = generateId()
    const userMessage = {
      id: tempId,
      role: 'user',
      content: text.trim(),
      contentType: 'voice',
      mediaUrl: '',
      localImagePath: '',
      audioUrl: audioPath || '',
      serverAudioUrl: serverAudioUrl,
      duration: duration || 0,
      status: 'sending',
      timeText: '刚刚',
      created_at: new Date().toISOString(),
    }

    const botTempId = generateId()
    const botMessage = {
      id: botTempId,
      role: 'assistant',
      content: '',
      contentType: 'text',
      status: 'read',
      timeText: '刚刚',
      created_at: new Date().toISOString(),
      audioUrl: null,
      autoPlayAudio: false,
    }

    this.setData({
      messages: [...this.data.messages, userMessage, botMessage],
      isLoading: true,
      suggestions: [],
      showScrollBtn: false,
    })
    this._scheduleScrollToBottom()
    storage.clearDraft(this.data.conversationId || 'new')

    const botIndex = this.data.messages.length - 1

    try {
      const res = await api.post('/chat/send', {
        conversation_id: this.data.conversationId,
        content: text.trim(),
        content_type: 'voice',
        media_url: serverAudioUrl || null,
        duration: duration || 0,
      })

      this.setData({
        conversationId: res.conversation_id,
        [`messages[${botIndex}].content`]: res.content || '',
        [`messages[${botIndex}].id`]: res.message_id || botTempId,
        [`messages[${botIndex}].timeText`]: formatMessageTime(res.created_at),
        isLoading: false,
      })
      this._scheduleScrollToBottom()

      const msgIndex = this.data.messages.findIndex((m) => m && m.id === tempId)
      if (msgIndex !== -1) {
        this.setData({ [`messages[${msgIndex}].status`]: 'sent' })
      }

      if (this.data.conversationId) {
        storage.saveMessages(this.data.conversationId, this.data.messages)
      }

    } catch (err) {
      const msgIndex = this.data.messages.findIndex((m) => m && m.id === tempId)
      if (msgIndex !== -1) {
        this.setData({ [`messages[${msgIndex}].status`]: 'failed' })
      }

      this.setData({
        [`messages[${botIndex}].content`]: err.message || '回复失败，请重试',
        isLoading: false,
      })
      this._scheduleScrollToBottom()

      if (err.code === -1) {
        showToast('网络连接失败，请检查网络')
      } else if (err.code === 401) {
        showToast('登录已过期，请重新登录')
      }
    }
  },

  async onTyping(e) {
    const { content } = e.detail
    if (!content || content.length < 1) {
      this.setData({ suggestions: [] })
      return
    }

    try {
      const res = await api.post('/chat/typing', { content })
      this.setData({ suggestions: res.suggestions || [] })
    } catch (e) {
      console.error('Typing suggestions error:', e)
    }
  },

  formatMessage(msg) {
    if (!msg) return null
    const contentType = msg.content_type || 'text'
    const mediaUrl = msg.media_url || ''
    const duration = msg.duration || 0
    let localImagePath = ''
    let audioUrl = null

    if (contentType === 'image') {
      if (mediaUrl && (mediaUrl.startsWith('/uploads/') || mediaUrl.startsWith('http://') || mediaUrl.startsWith('https://'))) {
        const baseHost = app.globalData.baseUrl.replace('/api/v1', '')
        localImagePath = mediaUrl.startsWith('http') ? mediaUrl : `${baseHost}${mediaUrl}`
        this._downloadImage(msg.id, localImagePath)
      } else if (mediaUrl && (mediaUrl.startsWith('wxfile://') || mediaUrl.startsWith('http://tmp'))) {
        localImagePath = mediaUrl
      }
    }

    if (contentType === 'voice') {
      if (mediaUrl && (mediaUrl.startsWith('/uploads/') || mediaUrl.startsWith('http://') || mediaUrl.startsWith('https://'))) {
        const baseHost = app.globalData.baseUrl.replace('/api/v1', '')
        audioUrl = mediaUrl.startsWith('http') ? mediaUrl : `${baseHost}${mediaUrl}`
        this._downloadAudio(msg.id, audioUrl)
      } else if (mediaUrl && (mediaUrl.startsWith('wxfile://') || mediaUrl.startsWith('http://tmp'))) {
        audioUrl = mediaUrl
      }
    }

    return {
      id: msg.id,
      role: msg.role,
      content: msg.content,
      contentType: contentType,
      mediaUrl: '',
      localImagePath: localImagePath,
      audioUrl: audioUrl,
      duration: duration,
      status: msg.is_read ? 'read' : 'sent',
      timeText: formatMessageTime(msg.created_at),
      created_at: msg.created_at,
      autoPlayAudio: false,
    }
  },

  _downloadImage(msgId, url) {
    wx.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode === 200) {
          const idx = this.data.messages.findIndex(m => m.id === msgId)
          if (idx !== -1) {
            this.setData({ [`messages[${idx}].localImagePath`]: res.tempFilePath })
          }
        }
      },
    })
  },

  _downloadAudio(msgId, url) {
    wx.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode === 200) {
          const idx = this.data.messages.findIndex(m => m.id === msgId)
          if (idx !== -1) {
            this.setData({ [`messages[${idx}].audioUrl`]: res.tempFilePath })
          }
        }
      },
    })
  },

  onScroll(e) {
    if (this._isAutoScrolling) return
    if (!e.detail) return
    const { scrollTop, scrollHeight, deltaY } = e.detail
    if (typeof scrollTop !== 'number' || typeof scrollHeight !== 'number') return

    wx.createSelectorQuery()
      .select('.message-list')
      .boundingClientRect()
      .exec((res) => {
        if (!res || !res[0]) return
        const viewHeight = res[0].height
        const distanceFromBottom = scrollHeight - scrollTop - viewHeight
        const atBottom = distanceFromBottom < 200
        if (atBottom && this.data.showScrollBtn) {
          this.setData({ showScrollBtn: false })
        } else if (!atBottom && !this.data.showScrollBtn && deltaY < 0) {
          this.setData({ showScrollBtn: true })
        }
      })
  },

  onTapScrollBottom() {
    this.scrollToBottom()
  },

  scrollToBottom() {
    if (this.data.messages.length === 0) return

    const query = wx.createSelectorQuery()
    query.select('.message-list').boundingClientRect()
    query.select('.message-list').scrollOffset()
    query.exec((res) => {
      if (!res || !res[0] || !res[1]) return
      const viewHeight = res[0].height
      const scrollData = res[1]
      const maxScrollTop = scrollData.scrollHeight - viewHeight
      if (maxScrollTop > 0) {
        this.setData({ scrollTop: maxScrollTop + 1 })
      }
    })
  },

  onPullDownRefresh() {
    if (this.data.conversationId && this.data.hasMore) {
      this.loadOlderMessages()
    }
    wx.stopPullDownRefresh()
  },

  async loadOlderMessages() {
    if (!this.data.hasMore || !this.data.conversationId) return

    try {
      const nextPage = this.data.page + 1
      const res = await api.get(
        `/chat/conversations/${this.data.conversationId}/messages?page=${nextPage}`
      )

      const olderMessages = res.messages.map((msg) => this.formatMessage(msg)).filter(Boolean)
      this.setData({
        messages: [...olderMessages, ...this.data.messages],
        page: nextPage,
        hasMore: res.has_more,
      })
    } catch (e) {
      console.error('Load older messages error:', e)
    }
  },
})
