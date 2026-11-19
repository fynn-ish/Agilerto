// Facility types: color + letter + shape together identify each type.
export const FACILITY_TYPES = [
  { key: 'hospital', label: 'Hospitals', single: 'Hospital', letter: 'H', color: '#b83227' },
  { key: 'evacuation_center', label: 'Evacuation centers', single: 'Evacuation center', letter: 'E', color: '#1d7448' },
  { key: 'fire_station', label: 'Fire stations', single: 'Fire station', letter: 'F', color: '#c4620a' },
  { key: 'police_station', label: 'Police stations', single: 'Police station', letter: 'P', color: '#2a5aa0' },
]
export const TYPE_BY_KEY = Object.fromEntries(FACILITY_TYPES.map((t) => [t.key, t]))

// Fallback when geolocation is blocked or unavailable. Approximate city-center coordinates.
export const PLACES = [
  { name: 'Lipa City', lat: 13.9411, lng: 121.1631 },
  { name: 'Tanauan City', lat: 14.0859, lng: 121.1497 },
  { name: 'Santo Tomas', lat: 14.1078, lng: 121.1414 },
  { name: 'Batangas City', lat: 13.7565, lng: 121.0583 },
  { name: 'Tagaytay City', lat: 14.1153, lng: 120.9621 },
  { name: 'Calamba City', lat: 14.2117, lng: 121.1653 },
  { name: 'Santa Rosa City', lat: 14.3122, lng: 121.1114 },
  { name: 'San Pablo City', lat: 14.0683, lng: 121.3253 },
  { name: 'Lucena City', lat: 13.9373, lng: 121.6171 },
  { name: 'Imus City', lat: 14.4297, lng: 120.9367 },
]
export const DEFAULT_LOCATION = { lat: 13.9411, lng: 121.1631, label: 'Lipa City', source: 'default' }
export const RADIUS_OPTIONS = [3, 5, 10, 20]

// Map tiles. Step 5 replaces this with locally served offline tiles (PMTiles).
export const TILE_URL = import.meta.env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
export const TILE_ATTRIBUTION = '&copy; OpenStreetMap contributors'
