/**
 * Browser smoke test for Echo (run against a server that serves the built SPA):
 *   BASE_URL=http://localhost:8000 E2E_EMAIL=... E2E_PASSWORD=... node e2e/smoke.mjs [screenshot-dir]
 * Uses Chromium's fake microphone so the MediaRecorder flow really runs.
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = process.env.BASE_URL ?? 'http://localhost:8000'
const EMAIL = process.env.E2E_EMAIL ?? 'aluna@echo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'echo-aluna-dev'
const OUT = process.argv[2] ?? 'e2e/screenshots'
mkdirSync(OUT, { recursive: true })

const errors = []
const browser = await chromium.launch({
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
})
const context = await browser.newContext({
  viewport: { width: 1280, height: 900 },
  permissions: ['microphone'],
  locale: 'pt-BR',
  colorScheme: 'light',
})
const page = await context.newPage()
page.on('console', (m) => {
  // expected API answers the browser still logs as errors: 403 from the anonymous /me/ probe,
  // 404 from /sessions/today/ before the day's session exists
  if (m.type() === 'error' && !/status of (403|404)/.test(m.text())) errors.push(`console: ${m.text()}`)
})
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
page.on('response', (r) => {
  if (r.status() >= 500) errors.push(`HTTP ${r.status()} ${r.url()}`)
})

const shot = async (name) => {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  console.log(`📸 ${name}`)
}
const step = (msg) => console.log(`→ ${msg}`)

try {
  step('login')
  await page.goto(`${BASE}/login`)
  await page.locator('#email').fill(EMAIL)
  await page.locator('#password').fill(PASSWORD)
  await shot('01-login')
  await page.getByRole('button', { name: /Entrar/ }).click()
  await page.waitForURL('**/today', { timeout: 15000 })
  await page.waitForTimeout(800)
  await shot('02-today')

  step('start or continue the session')
  const start = page.getByRole('button', { name: /Começar/ })
  if (await start.isVisible().catch(() => false)) {
    await start.click()
  } else {
    await page.getByRole('link', { name: /Continuar|Ver resumo/ }).click()
  }
  await page.waitForURL('**/session/**', { timeout: 15000 })
  const record = page.getByRole('button', { name: 'Gravar resposta' })
  const completed = page.getByText(/Sessão concluída/)
  await Promise.race([
    record.waitFor({ state: 'visible', timeout: 45000 }),
    completed.waitFor({ state: 'visible', timeout: 45000 }),
  ])
  if (await record.isVisible().catch(() => false)) {
    await shot('03-session-card')

    step('record 4 s with the fake microphone')
    await record.click()
    await page.getByRole('button', { name: 'Parar gravação' }).waitFor({ timeout: 20000 })
    await page.waitForTimeout(4000)
    await shot('04-recording')
    await page.getByRole('button', { name: 'Parar gravação' }).click()
    const send = page.getByRole('button', { name: /Enviar/ })
    await send.waitFor({ state: 'visible', timeout: 5000 })
    await shot('05-preview')
    await send.click()

    step('wait for the evaluation')
    await page.getByRole('region', { name: 'Avaliação' }).waitFor({ state: 'visible', timeout: 90000 })
    await page.waitForTimeout(500)
    await shot('06-evaluation')

    step('improved answer on demand')
    const improve = page.getByRole('button', { name: 'Sugestão de resposta melhorada' })
    if (await improve.isVisible().catch(() => false)) {
      await improve.click()
      await page.waitForTimeout(1500)
      await shot('07-improved-answer')
    } else {
      console.log('   (improved-answer button not visible — insufficient speech?)')
    }

    step('next card')
    await page.getByRole('button', { name: /Próximo/ }).click()
    await page.waitForTimeout(1200)
    await shot('08-next-card')
  } else {
    console.log("   (today's session is already completed — skipping the recording steps)")
    await shot('03-session-completed')
  }

  step('cards')
  await page.goto(`${BASE}/cards`)
  await page.waitForTimeout(1200)
  await shot('09-cards')
  const firstCard = page.locator('a[href^="/cards/"]').first()
  if (await firstCard.isVisible().catch(() => false)) {
    await firstCard.click()
    await page.waitForTimeout(1200)
    await shot('10-card-detail')
  }

  step('stats (light)')
  await page.goto(`${BASE}/stats`)
  await page.getByText('Evolução do nível').waitFor({ timeout: 20000 })
  await page.waitForTimeout(1500)
  await shot('11-stats-light')
  await page.getByRole('radio', { name: /7 dias/ }).click()
  await page.waitForTimeout(1200)
  await shot('12-stats-7d')
  await page.getByRole('tab', { name: 'Calendário' }).click()
  await page.waitForTimeout(600)
  await page.getByRole('button', { name: 'Ver tabela' }).first().click()
  await page.waitForTimeout(400)
  await shot('13-stats-calendar-and-table')

  step('stats (dark)')
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.waitForTimeout(800)
  await shot('14-stats-dark')
  await page.emulateMedia({ colorScheme: 'light' })

  step('settings')
  await page.goto(`${BASE}/settings`)
  await page.waitForTimeout(1200)
  await shot('15-settings')
} catch (error) {
  errors.push(`script: ${error.message}`)
  await shot('99-failure').catch(() => {})
} finally {
  await browser.close()
}

if (errors.length) {
  console.log('\n❌ problems:')
  for (const e of errors) console.log(' -', e)
  process.exit(1)
}
console.log('\n✅ smoke flow completed without console/page errors')
