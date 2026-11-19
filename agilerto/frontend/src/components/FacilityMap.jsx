import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { TILE_ATTRIBUTION, TILE_URL, TYPE_BY_KEY } from '../constants'

function facilityIcon(f, selected) {
  const t = TYPE_BY_KEY[f.type]
  return L.divIcon({
    className: '',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
    html: `<div class="fmark fmark--${f.type}${selected ? ' is-selected' : ''}">
             <span class="shape" style="background:${t.color}">${t.letter}</span>
           </div>`,
  })
}

// Popup content is built with DOM nodes (textContent), never HTML strings,
// so names coming from imported data can't inject markup.
function popupNode(f) {
  const t = TYPE_BY_KEY[f.type]
  const root = document.createElement('div')
  const add = (tag, text, cls) => {
    const el = document.createElement(tag)
    el.textContent = text
    if (cls) el.className = cls
    root.appendChild(el)
    return el
  }
  add('strong', f.name, 'block text-base')
  add('div', `${t.single}, ${f.distance_km} km away`)
  if (f.address) add('div', f.address)
  if (f.phone) add('div', f.phone)
  return root
}

export default function FacilityMap({ center, radiusKm, facilities, selectedId, onSelect, onPick }) {
  const elRef = useRef(null)
  const mapRef = useRef(null)
  const layersRef = useRef({ markers: L.layerGroup(), you: null, ring: null })
  const markerById = useRef(new Map())
  const onPickRef = useRef(onPick)
  const onSelectRef = useRef(onSelect)
  onPickRef.current = onPick
  onSelectRef.current = onSelect

  // Create the map once.
  useEffect(() => {
    const map = L.map(elRef.current, { zoomControl: true }).setView([center.lat, center.lng], 13)
    L.tileLayer(TILE_URL, { maxZoom: 18, attribution: TILE_ATTRIBUTION }).addTo(map)
    layersRef.current.markers.addTo(map)
    map.on('click', (e) => onPickRef.current({ lat: e.latlng.lat, lng: e.latlng.lng }))
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Your position + search ring; re-frame when they change.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const L_ = layersRef.current
    L_.you?.remove()
    L_.ring?.remove()
    L_.you = L.marker([center.lat, center.lng], {
      icon: L.divIcon({ className: '', html: '<div class="you-dot"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }),
      keyboard: false,
      interactive: false,
    }).addTo(map)
    L_.ring = L.circle([center.lat, center.lng], {
      radius: radiusKm * 1000, color: '#17212b', weight: 1.5, dashArray: '6 6', fillOpacity: 0.04, interactive: false,
    }).addTo(map)
    map.fitBounds(L_.ring.getBounds(), { padding: [12, 12] })
  }, [center.lat, center.lng, radiusKm])

  // Facility markers.
  useEffect(() => {
    const group = layersRef.current.markers
    group.clearLayers()
    markerById.current.clear()
    facilities.forEach((f) => {
      const m = L.marker([f.lat, f.lng], { icon: facilityIcon(f, false), title: f.name, riseOnHover: true })
      m.bindPopup(popupNode(f))
      m.on('click', () => onSelectRef.current(f.id))
      m.addTo(group)
      markerById.current.set(f.id, { marker: m, facility: f })
    })
  }, [facilities])

  // Highlight the selected facility.
  useEffect(() => {
    markerById.current.forEach(({ marker, facility }, id) => {
      const on = id === selectedId
      marker.setIcon(facilityIcon(facility, on))
      marker.setZIndexOffset(on ? 1000 : 0)
      if (on) {
        marker.openPopup()
        mapRef.current?.panTo(marker.getLatLng())
      }
    })
  }, [selectedId, facilities])

  return (
    <div
      ref={elRef}
      className="map-surface h-full min-h-72 w-full rounded-md border border-line"
      role="application"
      aria-label="Map of nearby facilities. Tap the map to set your location."
    />
  )
}
