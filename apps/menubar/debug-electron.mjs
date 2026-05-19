import _electron from 'electron'
console.log('typeof _electron:', typeof _electron)
console.log('_electron:', JSON.stringify(_electron, null, 2)?.slice(0, 200))
if (typeof _electron === 'object' && _electron) {
  console.log('keys:', Object.keys(_electron).slice(0, 10))
}
process.exit(0)
