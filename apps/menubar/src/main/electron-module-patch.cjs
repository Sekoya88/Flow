/**
 * Electron 29 module resolution patch.
 *
 * Problem: node_modules/electron shadows Electron's runtime module.
 * Module._resolveFilename('electron') returns the npm package path
 * BEFORE Electron's Module._load intercept can fire.
 *
 * Fix: intercept _resolveFilename so 'electron' stays as the string
 * 'electron' (not a file path), letting Electron's _load handler
 * return the actual runtime APIs.
 */
const Module = require('module')
const _original = Module._resolveFilename.bind(Module)
Module._resolveFilename = function (request, ...args) {
  if (request === 'electron') return 'electron'
  return _original(request, ...args)
}
