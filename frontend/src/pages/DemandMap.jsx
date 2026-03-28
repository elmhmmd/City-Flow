import { useEffect, useRef, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.heat'
import api from '../api'

const AUSTIN_CENTER = [30.2672, -97.7431]
const VEHICLE_TYPES = ['scooter', 'bicycle', 'moped']

const ZONE_CENTROIDS = {
  '48453001100': [30.267, -97.743],
  '48453001200': [30.271, -97.735],
  '48453001300': [30.265, -97.750],
  '48453002100': [30.280, -97.740],
  '48453002200': [30.258, -97.745],
  '48453000902': [30.290, -97.737],
  '48453000604': [30.310, -97.750],
  '48453000603': [30.315, -97.745],
}

function HeatLayer({ points }) {
  const map = useMap()
  const heatRef = useRef(null)

  useEffect(() => {
    if (heatRef.current) map.removeLayer(heatRef.current)
    if (points.length === 0) return
    heatRef.current = L.heatLayer(points, { radius: 35, blur: 25, maxZoom: 13 }).addTo(map)
    return () => { if (heatRef.current) map.removeLayer(heatRef.current) }
  }, [points, map])

  return null
}

export default function DemandMap() {
  const [vehicleType, setVehicleType] = useState('scooter')
  const [hourOffset, setHourOffset] = useState(0)
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)

  const targetTimestamp = new Date(Date.now() + hourOffset * 3600 * 1000).toISOString()

  async function fetchPredictions() {
    setLoading(true)
    try {
      const zones = Object.keys(ZONE_CENTROIDS)
      const { data } = await api.post('/predictions/batch', {
        predictions: zones.map((zone_id) => ({
          zone_id,
          timestamp: targetTimestamp,
          vehicle_type: vehicleType,
        })),
      })
      setPredictions(data.predictions)
      const trips = data.predictions.map((p) => p.predicted_trips)
      setStats({
        total: trips.reduce((a, b) => a + b, 0).toFixed(0),
        max: Math.max(...trips).toFixed(1),
        zones: data.total,
      })
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchPredictions() }, [vehicleType, hourOffset])

  const heatPoints = predictions
    .filter((p) => ZONE_CENTROIDS[p.zone_id])
    .map((p) => [...ZONE_CENTROIDS[p.zone_id], p.predicted_trips])

  const maxTrips = predictions.length ? Math.max(...predictions.map((p) => p.predicted_trips)) : 1

  const displayTime = new Date(Date.now() + hourOffset * 3600 * 1000)
    .toLocaleString('en-US', { weekday: 'short', hour: '2-digit', minute: '2-digit' })

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-6 px-5 py-3 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-400">Vehicle</label>
          <select
            value={vehicleType}
            onChange={(e) => setVehicleType(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1 text-sm text-white"
          >
            {VEHICLE_TYPES.map((v) => <option key={v}>{v}</option>)}
          </select>
        </div>

        <div className="flex items-center gap-3 flex-1">
          <label className="text-xs text-gray-400 whitespace-nowrap">Time offset</label>
          <input
            type="range" min={0} max={23} value={hourOffset}
            onChange={(e) => setHourOffset(Number(e.target.value))}
            className="flex-1 accent-blue-500"
          />
          <span className="text-sm text-white w-32 text-right">{displayTime}</span>
        </div>

        {loading && <span className="text-xs text-blue-400">Loading...</span>}

        {stats && (
          <div className="flex gap-4 text-xs text-gray-400">
            <span>Zones: <b className="text-white">{stats.zones}</b></span>
            <span>Total trips: <b className="text-white">{stats.total}</b></span>
            <span>Peak zone: <b className="text-white">{stats.max}</b></span>
          </div>
        )}
      </div>

      <div className="flex-1">
        <MapContainer center={AUSTIN_CENTER} zoom={12} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
          />
          <HeatLayer points={heatPoints} />
          {predictions.filter((p) => ZONE_CENTROIDS[p.zone_id]).map((p) => {
            const [lat, lng] = ZONE_CENTROIDS[p.zone_id]
            const intensity = p.predicted_trips / maxTrips
            return (
              <CircleMarker
                key={p.zone_id}
                center={[lat, lng]}
                radius={6 + intensity * 10}
                pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.3, weight: 1 }}
              >
                <Popup>
                  <div className="text-sm space-y-1 min-w-[180px]">
                    <p className="font-semibold text-gray-800">Zone {p.zone_id}</p>
                    <p>Predicted trips: <b>{p.predicted_trips}</b></p>
                    <p>CI: [{p.confidence_interval.lower} – {p.confidence_interval.upper}]</p>
                    {p.weather && (
                      <div className="border-t pt-1 mt-1 text-gray-600 text-xs">
                        <p>🌡 {p.weather.temperature_c}°C</p>
                        <p>🌧 {p.weather.precipitation_mm} mm</p>
                        <p>💨 {p.weather.windspeed_kmh} km/h</p>
                      </div>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            )
          })}
        </MapContainer>
      </div>
    </div>
  )
}
