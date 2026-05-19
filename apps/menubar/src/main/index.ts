import { join } from 'path'
import { app, BrowserWindow, ipcMain, shell, screen } from 'electron'
import WS from 'ws'

// ── constants ────────────────────────────────────────────────
const NOTCH_W    = 250   // wide enough to cover MacBook Pro notch (~230 DIPs)
const NOTCH_H    = 38    // slightly taller than menubar so window is definitely in notch
const PANEL_W    = 420
const PANEL_H    = 560   // panel content height below menubar
const WEB_APP_URL = 'http://localhost:13000'
const API_WS_BASE = 'ws://localhost:18000/api/v1/agents'

// ── globals ──────────────────────────────────────────────────
let win: BrowserWindow | null = null
let agentWs: InstanceType<typeof WS> | null = null
let currentAgentId: string | null = null
let collapseTimer: NodeJS.Timeout | null = null

// ── app setup ────────────────────────────────────────────────
app.whenReady().then(() => {
  app.dock?.hide()
  createWindow()
  registerIpcHandlers()
})

app.on('window-all-closed', (e: Event) => e.preventDefault())

// ── window ───────────────────────────────────────────────────
function createWindow(): void {
  win = new BrowserWindow({
    width: NOTCH_W,
    height: NOTCH_H,
    show: false,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    transparent: true,
    hasShadow: false,
    // No vibrancy here — pill must be invisible (blends with black hardware notch).
    // Vibrancy is enabled dynamically when the panel expands.
    roundedCorners: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  // 'screen-saver' level puts window above the menu bar — same as boringNotch's .mainMenu + 3
  win.setAlwaysOnTop(true, 'screen-saver')
  positionWindow(NOTCH_W)

  win.webContents.once('did-finish-load', () => {
    const { workArea } = screen.getPrimaryDisplay()
    win?.webContents.send('display:info', { menubarH: workArea.y })
    positionWindow(NOTCH_W)
    win?.show()
  })

  if (process.env['ELECTRON_RENDERER_URL']) {
    win.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// ── positioning ──────────────────────────────────────────────
// Always at y=0 (inside the notch). Window grows downward on expand — no position jump.
function positionWindow(width: number): void {
  if (!win) return
  const primary = screen.getPrimaryDisplay()
  const x = Math.round(primary.bounds.width / 2 - width / 2)
  win.setPosition(x, primary.bounds.y)  // y=0 always
}

// ── IPC ───────────────────────────────────────────────────────
function registerIpcHandlers(): void {
  ipcMain.on('window:expand', () => {
    if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null }
    if (!win) return
    const primary = screen.getPrimaryDisplay()
    // Total height = transparent menubar area + panel content
    const totalH = primary.workArea.y + PANEL_H
    win.setSize(PANEL_W, totalH)
    win.setHasShadow(true)
    // No vibrancy — macOS vibrancy forces a LIGHT background that overrides dark CSS.
    // The panel uses CSS backdrop-filter for its own blur/glass effect.
    positionWindow(PANEL_W)
  })

  ipcMain.on('window:collapse', () => {
    collapseTimer = setTimeout(() => {
      if (!win) return
      win.setSize(NOTCH_W, NOTCH_H)
      win.setHasShadow(false)
      win.setVibrancy(null)           // remove frosted glass → pill invisible in notch
      positionWindow(NOTCH_W)
      collapseTimer = null
    }, 300)
  })

  ipcMain.on('window:keep-open', () => {
    if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null }
  })

  ipcMain.handle('open-web-app', (_e, path = '') => {
    shell.openExternal(`${WEB_APP_URL}${path}`)
  })

  ipcMain.handle('app:quit', () => app.quit())

  ipcMain.handle('ws:connect', (_e, agentId: string) => {
    connectAgentWs(agentId)
    return { ok: true }
  })

  ipcMain.handle('ws:disconnect', () => disconnectAgentWs())
}

// ── WebSocket bridge ─────────────────────────────────────────
function connectAgentWs(agentId: string): void {
  if (agentWs) agentWs.terminate()
  currentAgentId = agentId

  const url = `${API_WS_BASE}/${agentId}/ws-observability`
  agentWs = new WS(url)

  agentWs.on('open', () => {
    win?.webContents.send('ws:status', { connected: true, agentId })
  })
  agentWs.on('message', (raw) => {
    try {
      const event = JSON.parse(raw.toString())
      win?.webContents.send('ws:event', event)
    } catch {}
  })
  agentWs.on('close', () => {
    win?.webContents.send('ws:status', { connected: false, agentId })
    setTimeout(() => {
      if (currentAgentId === agentId) connectAgentWs(agentId)
    }, 3000)
  })
  agentWs.on('error', () => {})
}

function disconnectAgentWs(): void {
  currentAgentId = null
  agentWs?.terminate()
  agentWs = null
}
