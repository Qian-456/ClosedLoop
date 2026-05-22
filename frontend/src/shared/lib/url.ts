export function buildApiUrl(path: string, base?: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const rawBase = (base ?? '').trim()
  if (!rawBase) return normalizedPath
  const normalizedBase = rawBase.replace(/\/+$/, '')
  return `${normalizedBase}${normalizedPath}`
}

