const app = getApp()
const api = require('../../utils/api')
const storage = require('../../utils/storage')
const { formatMessageTime, showConfirm, showToast, showLoading, hideLoading } = require('../../utils/util')

Page({
  data: {
    conversations: [],
    pinnedConversations: [],
    normalConversations: [],
    page: 1,
    total: 0,
    hasMore: false,
    loaded: false,
    showRenamePanel: false,
    renameValue: '',
    renameId: '',
    renameIndex: -1,
  },

  onShow() {
    this.setData({ page: 1, loaded: false })
    this.loadConversations()
  },

  async loadConversations() {
    try {
      const res = await api.get('/chat/conversations', {
        page: this.data.page,
        page_size: 20,
      })
      const conversations = res.conversations.map((conv) => ({
        ...conv,
        timeText: formatMessageTime(conv.updated_at),
        lastMessage: '',
      }))

      const total = res.total
      const hasMore = conversations.length < total

      this.setData({
        conversations,
        total,
        hasMore,
        loaded: true,
      })

      this.splitConversations()
      this.loadLastMessages()
    } catch (e) {
      const localConvs = storage.getConversations()
      this.setData({
        conversations: localConvs,
        loaded: true,
      })
      this.splitConversations()
    }
  },

  splitConversations() {
    const pinned = []
    const normal = []
    for (const conv of this.data.conversations) {
      if (conv.is_pinned) {
        pinned.push(conv)
      } else {
        normal.push(conv)
      }
    }
    this.setData({
      pinnedConversations: pinned,
      normalConversations: normal,
    })
  },

  async loadLastMessages() {
    const convsWithMessages = this.data.conversations.filter(
      (conv) => conv.message_count > 0 && !conv.lastMessage
    )
    const toLoad = convsWithMessages.slice(0, 5)

    const promises = toLoad.map(async (conv) => {
      try {
        const res = await api.get(`/chat/conversations/${conv.id}/messages`, {
          page: 1,
          page_size: 1,
        })
        if (res.messages && res.messages.length > 0) {
          const lastMsg = res.messages[res.messages.length - 1]
          conv.lastMessage = lastMsg.content.substring(0, 30) + (lastMsg.content.length > 30 ? '...' : '')
        }
      } catch (e) {}
    })

    await Promise.all(promises)
    this.setData({ conversations: this.data.conversations })
    this.splitConversations()
  },

  openConversation(e) {
    const id = e.currentTarget.dataset.id
    app.globalData.resumeConversationId = id
    wx.switchTab({ url: '/pages/chat/chat' })
  },

  async togglePin(e) {
    const { id, pinned } = e.currentTarget.dataset
    const newPinned = pinned !== 'true' && pinned !== true

    try {
      await api.put(`/chat/conversations/${id}`, { is_pinned: newPinned })
      showToast(newPinned ? '已置顶' : '已取消置顶')
      this.loadConversations()
    } catch (e) {
      showToast('操作失败')
    }
  },

  showRename(e) {
    const { id, title } = e.currentTarget.dataset
    this.setData({
      showRenamePanel: true,
      renameValue: title,
      renameId: id,
    })
  },

  hideRename() {
    this.setData({ showRenamePanel: false })
  },

  onRenameInput(e) {
    this.setData({ renameValue: e.detail.value })
  },

  async confirmRename() {
    const { renameId, renameValue } = this.data
    const title = renameValue.trim()

    if (!title) {
      showToast('标题不能为空')
      return
    }

    try {
      await api.put(`/chat/conversations/${renameId}`, { title })
      showToast('已重命名')
      this.hideRename()
      this.loadConversations()
    } catch (e) {
      showToast('重命名失败')
    }
  },

  async deleteConversation(e) {
    const { id } = e.currentTarget.dataset

    const confirmed = await showConfirm('确定要删除这个对话吗？删除后不可恢复。')
    if (!confirmed) return

    try {
      await api.del(`/chat/conversations/${id}`)
      showToast('对话已删除')
      this.loadConversations()
    } catch (e) {
      showToast('删除失败')
    }
  },

  async exportConversation(e) {
    const { id } = e.currentTarget.dataset
    try {
      wx.showLoading({ title: '导出中...' })
      const res = await api.get(`/chat/conversations/${id}/export`)
      wx.hideLoading()
      if (!res || !res.content) {
        wx.showModal({ title: '导出失败', content: '返回数据为空', showCancel: false })
        return
      }
      wx.showModal({
        title: res.title || '对话记录',
        content: res.content.length > 800 ? res.content.substring(0, 800) + '...' : res.content,
        confirmText: '复制',
        cancelText: '关闭',
        success(modalRes) {
          if (modalRes.confirm) {
            wx.setClipboardData({
              data: res.content,
              success() {
                wx.showToast({ title: '已复制到剪贴板', icon: 'success' })
              },
            })
          }
        },
      })
    } catch (err) {
      wx.hideLoading()
      wx.showModal({
        title: '导出失败',
        content: String(err.message || err.code || JSON.stringify(err)),
        showCancel: false,
      })
    }
  },

  async clearAll() {
    const confirmed = await showConfirm('确定要清空所有对话吗？删除后不可恢复。')
    if (!confirmed) return

    showLoading('清空中...')
    try {
      for (const conv of this.data.conversations) {
        await api.del(`/chat/conversations/${conv.id}`)
      }
      hideLoading()
      showToast('已清空全部对话')
      this.setData({ conversations: [], pinnedConversations: [], normalConversations: [], total: 0 })
    } catch (e) {
      hideLoading()
      showToast('清空失败')
    }
  },

  goSearch() {
    wx.navigateTo({ url: '/pages/search/search' })
  },

  goChat() {
    wx.switchTab({ url: '/pages/chat/chat' })
  },

  async loadMore() {
    if (!this.data.hasMore) return

    this.setData({ page: this.data.page + 1 })

    try {
      const res = await api.get('/chat/conversations', {
        page: this.data.page,
        page_size: 20,
      })
      const newConvs = res.conversations.map((conv) => ({
        ...conv,
        timeText: formatMessageTime(conv.updated_at),
        lastMessage: '',
      }))

      this.setData({
        conversations: [...this.data.conversations, ...newConvs],
        hasMore: this.data.conversations.length + newConvs.length < res.total,
      })
      this.splitConversations()
    } catch (e) {
      showToast('加载失败')
    }
  },

  onPullDownRefresh() {
    this.setData({ page: 1 })
    this.loadConversations()
    wx.stopPullDownRefresh()
  },
})
