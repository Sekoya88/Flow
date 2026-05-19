import { contextBridge, ipcRenderer } from 'electron'

export type AgentEvent = {
  type: string
  [key: string]: unknown
}

export type WsStatus = {
  connected: boolean
  agentId: string
}

const api = {
  openWebApp: (path = '')            => ipcRenderer.invoke('open-web-app', path),
  quit:       ()                     => ipcRenderer.invoke('app:quit'),
  wsConnect:  (agentId: string)      => ipcRenderer.invoke('ws:connect', agentId),
  wsDisconnect: ()                   => ipcRenderer.invoke('ws:disconnect'),
  keepOpen:   ()                     => ipcRenderer.send('window:keep-open'),
  allowClose: ()                     => ipcRenderer.send('window:allow-close'),
  expand:     ()                     => ipcRenderer.send('window:expand'),
  collapse:   ()                     => ipcRenderer.send('window:collapse'),

  onDisplayInfo: (cb: (info: { menubarH: number }) => void) =>
    ipcRenderer.once('display:info', (_ipc, info) => cb(info)),

  onEvent:    (cb: (e: AgentEvent) => void) =>
    ipcRenderer.on('ws:event', (_ipc, e) => cb(e)),

  onStatus:   (cb: (s: WsStatus) => void) =>
    ipcRenderer.on('ws:status', (_ipc, s) => cb(s)),

  onExpand:   (cb: () => void) =>
    ipcRenderer.on('window:expand',   () => cb()),

  onCollapse: (cb: () => void) =>
    ipcRenderer.on('window:collapse', () => cb()),

  removeAllListeners: () => {
    ipcRenderer.removeAllListeners('ws:event')
    ipcRenderer.removeAllListeners('ws:status')
    ipcRenderer.removeAllListeners('window:expand')
    ipcRenderer.removeAllListeners('window:collapse')
  }
}

contextBridge.exposeInMainWorld('flowAPI', api)

declare global {
  interface Window {
    flowAPI: typeof api
  }
}
