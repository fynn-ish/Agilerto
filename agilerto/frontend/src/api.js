// Thin API client. Responses are mirrored to localStorage so the last result
// still shows if the connection to the backend drops mid-emergency.
const read = (key) => {
  try { return JSON.parse(localStorage.getItem(key)) } catch { return null }
}
const write = (key, value) => {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* storage full or blocked */ }
}

async function getJson(url, signal) {
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return res.json()
}

export async function fetchFacilities({ lat, lng, radius }, signal) {
  const key = `cache:facilities:${lat.toFixed(2)},${lng.toFixed(2)},${radius}`
  try {
    const data = await getJson(`/api/facilities?lat=${lat}&lng=${lng}&radius_km=${radius}`, signal)
    write(key, { data, savedAt: new Date().toISOString() })
    return { data, fromCache: false }
  } catch (err) {
    if (err.name === 'AbortError') throw err
    const cached = read(key)
    if (cached) return { data: cached.data, fromCache: true, savedAt: cached.savedAt }
    throw err
  }
}

export async function fetchHotlines() {
  try {
    const data = await getJson('/api/emergency-numbers')
    write('cache:hotlines', data)
    return data.numbers
  } catch {
    return read('cache:hotlines')?.numbers ?? null
  }
}

// Weather + earthquakes + sync status for a location. Mirrored to localStorage like facilities.
export async function fetchDashboard({ lat, lng }, signal) {
  const key = `cache:dashboard:${lat.toFixed(2)},${lng.toFixed(2)}`
  try {
    const data = await getJson(`/api/dashboard?lat=${lat}&lng=${lng}`, signal)
    write(key, { data, savedAt: new Date().toISOString() })
    return { data, fromCache: false }
  } catch (err) {
    if (err.name === 'AbortError') throw err
    const cached = read(key)
    if (cached) return { data: cached.data, fromCache: true, savedAt: cached.savedAt }
    throw err
  }
}

// "Refresh now" button: asks the backend to re-download weather and earthquakes.
export async function triggerRefresh() {
  const res = await fetch('/api/refresh', { method: 'POST' })
  if (!res.ok) throw new Error(`Refresh failed (${res.status})`)
  return res.json()
}
