const app = getApp()
const api = require('../../utils/api')
const { debounce, formatMessageTime, showLoading, hideLoading } = require('../../utils/util')

Page({
  data: {
    keyword: '',
    results: [],
    total: 0,
    searched: false,
    page: 1,
  },

  onLoad() {
    this.doSearch = debounce((keyword) => {
      this.search(keyword)
    }, 500)
  },

  onInput(e) {
    const keyword = e.detail.value
    this.setData({ keyword })
    if (keyword.trim()) {
      this.doSearch(keyword)
    } else {
      this.setData({ results: [], searched: false, total: 0 })
    }
  },

  async onSearch() {
    const keyword = this.data.keyword.trim()
    if (!keyword) return
    await this.search(keyword)
  },

  async search(keyword) {
    showLoading('搜索中...')
    try {
      const res = await api.post('/chat/search', {
        keyword,
        page: 1,
        page_size: 20,
      })
      const results = res.results.map((item) => ({
        ...item,
        timeText: formatMessageTime(item.created_at),
      }))
      this.setData({
        results,
        total: res.total,
        searched: true,
        page: 1,
      })
    } catch (e) {
      this.setData({ searched: true, results: [] })
    }
    hideLoading()
  },

  clearInput() {
    this.setData({ keyword: '', results: [], searched: false, total: 0 })
  },

  goBack() {
    wx.navigateBack()
  },

  openConversation(e) {
    const id = e.currentTarget.dataset.id
    app.globalData.resumeConversationId = id
    wx.switchTab({ url: '/pages/chat/chat' })
  },

  onReachBottom() {
    if (this.data.results.length < this.data.total) {
      this.loadMore()
    }
  },

  async loadMore() {
    const nextPage = this.data.page + 1
    try {
      const res = await api.post('/chat/search', {
        keyword: this.data.keyword,
        page: nextPage,
        page_size: 20,
      })
      const newResults = res.results.map((item) => ({
        ...item,
        timeText: formatMessageTime(item.created_at),
      }))
      this.setData({
        results: [...this.data.results, ...newResults],
        page: nextPage,
      })
    } catch (e) {}
  },
})
