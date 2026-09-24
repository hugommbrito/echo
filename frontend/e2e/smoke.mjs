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
  // the spoken question may legitimately be unavailable (no TTS key in CI): 503 on /audio/ is fine
  if (r.status() >= 500 && !(r.status() === 503 && r.url().includes('/audio/')))
    errors.push(`HTTP ${r.status()} ${r.url()}`)
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

  step('activate French in Settings › Idiomas (idempotent)')
  await page.goto(`${BASE}/settings?tab=languages`)
  await page.getByRole('tab', { name: 'Idiomas' }).waitFor({ timeout: 15000 })
  await page.waitForTimeout(800)
  const activate = page.getByRole('button', { name: 'Ativar', exact: true })
  if (await activate.isVisible().catch(() => false)) {
    await activate.click()
    await page.getByRole('radio', { name: /A1 — Iniciante/ }).waitFor({ timeout: 5000 })
    await page.getByRole('button', { name: 'Ativar idioma' }).click()
  }
  await page.getByRole('switch', { name: /Pausar francês/ }).waitFor({ timeout: 15000 })
  await shot('02a-settings-languages')

  step('start or continue the session (1 new card per language)')
  await page.goto(`${BASE}/today`)
  await page.waitForTimeout(800)
  const start = page.getByRole('button', { name: /Começar/ })
  if (await start.isVisible().catch(() => false)) {
    await page.locator('#new-cards-target-en').fill('1')
    await page.locator('#new-cards-target-fr').fill('1')
    await page.waitForTimeout(900) // debounced projection
    await shot('02b-today-mixed')
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
    step('filter the queue by language')
    const languageGroup = page.getByRole('radiogroup', { name: 'Idioma' })
    if (await languageGroup.isVisible().catch(() => false)) {
      const french = languageGroup.getByRole('radio', { name: /Francês/ })
      await french.click()
      await page.waitForTimeout(800)
      const frenchCard = page.locator('article[aria-label="Pergunta"][data-language="fr"]')
      if (await frenchCard.isVisible().catch(() => false)) {
        if ((await frenchCard.locator('[lang="fr-CA"]').count()) === 0)
          errors.push('French card without lang="fr-CA"')
        await shot('03a-session-french')
      } else {
        console.log('   (no French card left today — showing all languages)')
      }
      await languageGroup.getByRole('radio', { name: /Todos/ }).click()
      await page.waitForTimeout(600)
    }
    await shot('03-session-card')

    step('thinking timer + spoken question (Ler e ouvir)')
    const timer = page.getByRole('timer', { name: 'Tempo para começar' })
    if (!(await timer.isVisible().catch(() => false))) errors.push('thinking timer not visible on the card')
    const modeGroup = page.getByRole('radiogroup', { name: 'Como ver a pergunta' })
    if (await modeGroup.isVisible().catch(() => false)) {
      await modeGroup.getByRole('radio', { name: 'Ler e ouvir' }).click()
      const listen = page.getByRole('button', { name: 'Ouvir pergunta' })
      await listen.waitFor({ state: 'visible', timeout: 10000 })
      await listen.click()
      await page.waitForTimeout(2500)
      await shot('03b-listen')
      if ((await page.getByText(/ouviu 1×/).count()) === 0)
        console.log('   (question audio did not play — TTS unavailable here?)')
    }

    step('record 4 s with the fake microphone')
    await record.click()
    await page.getByRole('button', { name: 'Parar gravação' }).waitFor({ timeout: 20000 })
    await page.waitForTimeout(4000)
    await shot('04-recording')
    await page.getByRole('button', { name: 'Parar gravação' }).click()
    const frozen = await timer.textContent().catch(() => null)
    await page.waitForTimeout(700)
    if (frozen !== null && frozen !== (await timer.textContent().catch(() => null)))
      errors.push('thinking timer kept running after the record press')
    const send = page.getByRole('button', { name: /Enviar/ })
    await send.waitFor({ state: 'visible', timeout: 5000 })
    await shot('05-preview')
    await send.click()

    step('wait for the evaluation')
    await page.getByRole('region', { name: 'Avaliação' }).waitFor({ state: 'visible', timeout: 90000 })
    await page.waitForTimeout(500)
    if (
      !(await page
        .getByRole('region', { name: 'Tempo para começar' })
        .isVisible()
        .catch(() => false))
    )
      errors.push('evaluation without the thinking-time summary')
    await shot('06-evaluation')
    const modeGroupAfter = page.getByRole('radiogroup', { name: 'Como ver a pergunta' })
    if (await modeGroupAfter.isVisible().catch(() => false))
      await modeGroupAfter.getByRole('radio', { name: 'Ler', exact: true }).click() // restore the default

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
  await page.goto(`${BASE}/cards?language=fr`)
  await page.waitForTimeout(1200)
  const frenchItems = await page.locator('a[href^="/cards/"] [data-language="fr"]').count()
  const allItems = await page.locator('a[href^="/cards/"]').count()
  if (allItems !== frenchItems)
    errors.push(`cards?language=fr shows ${allItems} items, ${frenchItems} French`)
  await shot('09a-cards-french')
  await page.goto(`${BASE}/cards`)
  await page.waitForTimeout(800)
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
  const statsLanguages = page.getByRole('radiogroup', { name: 'Idioma' })
  if (await statsLanguages.isVisible().catch(() => false)) {
    await statsLanguages.getByRole('radio', { name: /Francês/ }).click()
    await page.waitForTimeout(1200)
    await shot('11a-stats-french')
    await statsLanguages.getByRole('radio', { name: /Todos/ }).click()
    await page.waitForTimeout(1200)
    const levelChart = page.locator('figure', {
      has: page.getByRole('heading', { name: 'Evolução do nível' }),
    })
    for (const label of ['Inglês', 'Francês']) {
      if ((await levelChart.getByText(label, { exact: true }).count()) === 0)
        errors.push(`level chart legend without ${label}`)
    }
  }
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
  await page.getByRole('tab', { name: 'IA e custos' }).click()
  await page.getByText('Custo estimado').waitFor({ timeout: 15000 })
  await page.waitForTimeout(600)
  await shot('16-settings-ai')
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
