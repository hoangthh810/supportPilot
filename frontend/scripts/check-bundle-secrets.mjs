import { readdir, readFile } from 'node:fs/promises'
import { extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const forbiddenPatterns = [
  'INTERNAL_SERVICE_TOKEN',
  'GEMINI_API_KEY',
  'JWT_SIGNING_KEY',
  'SUPPORT_DATABASE_URL',
  '/internal/v1',
  'generativelanguage.googleapis.com',
]
const textExtensions = new Set(['.css', '.html', '.js', '.json', '.map', '.svg', '.txt'])
const distDirectory = fileURLToPath(new URL('../dist', import.meta.url))

async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) files.push(...(await filesUnder(path)))
    else if (textExtensions.has(extname(entry.name))) files.push(path)
  }
  return files
}

const violations = []
for (const path of await filesUnder(distDirectory)) {
  const content = await readFile(path, 'utf8')
  for (const pattern of forbiddenPatterns) {
    if (content.includes(pattern)) violations.push(`${path}: ${pattern}`)
  }
}

if (violations.length > 0) {
  throw new Error(`Forbidden frontend bundle content:\n${violations.join('\n')}`)
}

console.log('Frontend bundle secret scan passed.')
