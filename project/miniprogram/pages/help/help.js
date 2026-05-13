const api = require('../../utils/api')

Page({
  data: {
    faqItems: [],
    helpItems: [],
  },

  onLoad() {
    this.loadFaq()
    this.loadHelp()
  },

  async loadFaq() {
    try {
      const res = await api.get('/settings/faq')
      const faqItems = res.items.map((item) => ({
        ...item,
        expanded: false,
      }))
      this.setData({ faqItems })
    } catch (e) {
      this.setData({
        faqItems: [
          { id: '1', question: '如何开始对话？', answer: '在聊天界面输入问题即可开始对话，也可以点击麦克风按钮使用语音输入', expanded: false },
          { id: '2', question: '如何查看历史对话？', answer: '在历史记录页面可以查看所有对话，支持搜索和删除', expanded: false },
          { id: '3', question: '支持哪些消息类型？', answer: '目前支持文字消息、语音消息和图片消息', expanded: false },
          { id: '4', question: '如何修改个人信息？', answer: '在"我的"页面点击头像区域即可修改昵称和头像', expanded: false },
        ],
      })
    }
  },

  async loadHelp() {
    try {
      const res = await api.get('/settings/help')
      this.setData({ helpItems: res.items })
    } catch (e) {
      this.setData({
        helpItems: [
          { title: '快速入门', content: '输入问题即可开始对话，AI会智能理解你的需求并给出回复' },
          { title: '语音输入', content: '点击麦克风按钮开始录音，再次点击停止并发送，系统会自动将语音转为文字' },
          { title: '消息类型', content: '支持文字、表情、图片和语音消息' },
          { title: '历史记录', content: '所有对话都会自动保存，可在历史记录页面查看和管理' },
        ],
      })
    }
  },

  toggleFaq(e) {
    const index = e.currentTarget.dataset.index
    this.setData({
      [`faqItems[${index}].expanded`]: !this.data.faqItems[index].expanded,
    })
  },
})
