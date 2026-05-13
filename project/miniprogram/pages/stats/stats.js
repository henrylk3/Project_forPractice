const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    loading: true,
    totalConversations: 0,
    totalMessages: 0,
    userMessages: 0,
    assistantMessages: 0,
    intentDistribution: {},
    contentTypeDistribution: {},
    dailyMessages: [],
    intentLabels: [],
    intentValues: [],
    contentTypeLabels: [],
    contentTypeValues: [],
  },

  onShow() {
    this.loadStats()
  },

  async loadStats() {
    try {
      const res = await api.get('/chat/stats')
      const intentLabels = Object.keys(res.intent_distribution || {})
      const intentValues = Object.values(res.intent_distribution || {})
      const contentTypeLabels = Object.keys(res.content_type_distribution || {})
      const contentTypeValues = Object.values(res.content_type_distribution || {})

      const dailyMessages = (res.daily_messages || []).reverse()
      const dailyMaxCount = Math.max(...dailyMessages.map(d => d.count), 1)

      this.setData({
        loading: false,
        totalConversations: res.total_conversations,
        totalMessages: res.total_messages,
        userMessages: res.user_messages,
        assistantMessages: res.assistant_messages,
        intentDistribution: res.intent_distribution || {},
        contentTypeDistribution: res.content_type_distribution || {},
        dailyMessages,
        dailyMaxCount,
        intentLabels,
        intentValues,
        contentTypeLabels,
        contentTypeValues,
      })
    } catch (e) {
      this.setData({ loading: false })
    }
  },

  goBack() {
    wx.navigateBack()
  },
})
