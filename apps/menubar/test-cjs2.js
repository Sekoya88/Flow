const m = require('electron')
console.log('type:', typeof m)
if (typeof m === 'object' && m) {
  console.log('has app:', 'app' in m)
  console.log('keys:', Object.keys(m).slice(0,5))
} else {
  console.log('value:', String(m).slice(0,60))
}
