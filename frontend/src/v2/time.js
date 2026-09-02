// One clock for every v2 screen: the list and the editor used to disagree
// ("1m" vs "just now") about the same timestamp (CL-26).
const mins = (iso) => (iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 60000) : null)
export const ago = (iso) => {
  const m = mins(iso); if (m == null) return ''
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`
}
export const agoShort = (iso) => {
  const m = mins(iso); if (m == null) return ''
  if (m < 1) return 'now'
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return h < 24 ? `${h}h` : `${Math.floor(h / 24)}d`
}
