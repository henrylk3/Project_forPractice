function parseMarkdown(md) {
  if (!md) return []
  const nodes = []
  const lines = md.split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.match(/^```/)) {
      const lang = line.replace(/^```\s*/, '').trim()
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].match(/^```/)) {
        codeLines.push(lines[i])
        i++
      }
      i++
      nodes.push({
        type: 'code',
        lang,
        content: codeLines.join('\n'),
      })
      continue
    }

    if (line.match(/^###\s+/)) {
      nodes.push({ type: 'h3', content: line.replace(/^###\s+/, '') })
      i++
      continue
    }

    if (line.match(/^##\s+/)) {
      nodes.push({ type: 'h2', content: line.replace(/^##\s+/, '') })
      i++
      continue
    }

    if (line.match(/^#\s+/)) {
      nodes.push({ type: 'h1', content: line.replace(/^#\s+/, '') })
      i++
      continue
    }

    if (line.match(/^[-*]\s+/)) {
      const items = []
      while (i < lines.length && lines[i].match(/^[-*]\s+/)) {
        items.push(lines[i].replace(/^[-*]\s+/, ''))
        i++
      }
      nodes.push({ type: 'ul', items })
      continue
    }

    if (line.match(/^\d+\.\s+/)) {
      const items = []
      while (i < lines.length && lines[i].match(/^\d+\.\s+/)) {
        items.push(lines[i].replace(/^\d+\.\s+/, ''))
        i++
      }
      nodes.push({ type: 'ol', items })
      continue
    }

    if (line.match(/^>\s+/)) {
      const quoteLines = []
      while (i < lines.length && lines[i].match(/^>\s*/)) {
        quoteLines.push(lines[i].replace(/^>\s*/, ''))
        i++
      }
      nodes.push({ type: 'quote', content: quoteLines.join('\n') })
      continue
    }

    if (line.match(/^---+$/)) {
      nodes.push({ type: 'hr' })
      i++
      continue
    }

    if (line.trim() === '') {
      i++
      continue
    }

    nodes.push({ type: 'p', content: line })
    i++
  }

  return nodes
}

function inlineFormat(text) {
  if (!text) return text
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[(.+?)\]\((.+?)\)/g, '$1')
}

module.exports = { parseMarkdown, inlineFormat }
