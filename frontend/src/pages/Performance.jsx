import { useEffect, useState } from 'react'
import {
  BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import api from '../api'

const COLORS = { RMSE: '#3b82f6', MAE: '#10b981', MAPE: '#f59e0b', R2: '#8b5cf6', RMSLE: '#ef4444' }
const DRIFT_MAPE_THRESHOLD = 30

function StatCard({ label, value, unit = '' }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">
        {value}<span className="text-sm text-gray-400 ml-1">{unit}</span>
      </p>
    </div>
  )
}

export default function Performance() {
  const [runs, setRuns] = useState([])
  const [actualVsPredicted, setActualVsPredicted] = useState([])
  const [loading, setLoading] = useState(true)
  const [avpLoading, setAvpLoading] = useState(true)

  useEffect(() => {
    async function fetchRuns() {
      try {
        const res = await fetch('http://localhost:5000/api/2.0/mlflow/runs/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ experiment_ids: ['1'], max_results: 50 }),
        })
        const data = await res.json()
        const parsed = (data.runs || []).map((run) => {
          const metrics = {}
          ;(run.data?.metrics || []).forEach((m) => { metrics[m.key] = m.value })
          return { name: run.info.run_name, ...metrics }
        })
        setRuns(parsed)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    async function fetchActualVsPredicted() {
      try {
        const { data } = await api.get('/performance/actual-vs-predicted?n=300')
        setActualVsPredicted(data.data)
      } catch (err) {
        console.error(err)
      } finally {
        setAvpLoading(false)
      }
    }

    fetchRuns()
    fetchActualVsPredicted()
  }, [])

  const best = runs.length ? runs.reduce((a, b) => (a.RMSE < b.RMSE ? a : b)) : null
  const driftDetected = best && best.MAPE > DRIFT_MAPE_THRESHOLD

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Model Performance</h2>
        {driftDetected && (
          <div className="flex items-center gap-2 bg-red-900/40 border border-red-700 text-red-400 text-sm px-4 py-2 rounded-lg">
            ⚠ Drift detected — MAPE {best.MAPE?.toFixed(1)}% exceeds threshold ({DRIFT_MAPE_THRESHOLD}%)
          </div>
        )}
      </div>

      {loading && <p className="text-gray-400 text-sm">Loading runs from MLflow...</p>}

      {best && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Best Model" value={best.name} />
          <StatCard label="RMSE" value={best.RMSE?.toFixed(4)} />
          <StatCard label="MAE" value={best.MAE?.toFixed(4)} />
          <StatCard label="MAPE" value={best.MAPE?.toFixed(2)} unit="%" />
          <StatCard label="R²" value={best.R2?.toFixed(4)} />
        </div>
      )}

      {runs.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h3 className="text-sm font-medium text-gray-300 mb-4">RMSE & MAE by Model</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={runs} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />
              <Legend />
              <Bar dataKey="RMSE" fill={COLORS.RMSE} radius={[4, 4, 0, 0]} />
              <Bar dataKey="MAE" fill={COLORS.MAE} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-300 mb-4">Predicted vs Actual Trip Count</h3>
        {avpLoading ? (
          <p className="text-gray-400 text-sm">Loading...</p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="actual" name="Actual" type="number"
                tick={{ fill: '#9ca3af', fontSize: 11 }} label={{ value: 'Actual', fill: '#6b7280', position: 'insideBottom', offset: -2 }}
              />
              <YAxis
                dataKey="predicted" name="Predicted" type="number"
                tick={{ fill: '#9ca3af', fontSize: 11 }} label={{ value: 'Predicted', fill: '#6b7280', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                contentStyle={{ background: '#111827', border: '1px solid #374151' }}
                formatter={(v) => v.toFixed(2)}
              />
              <ReferenceLine
                segment={[{ x: 0, y: 0 }, { x: Math.max(...actualVsPredicted.map(d => d.actual), 1), y: Math.max(...actualVsPredicted.map(d => d.actual), 1) }]}
                stroke="#4b5563" strokeDasharray="4 4"
              />
              <Scatter data={actualVsPredicted} fill="#3b82f6" fillOpacity={0.6} />
            </ScatterChart>
          </ResponsiveContainer>
        )}
        <p className="text-xs text-gray-500 mt-2">Dashed line = perfect prediction. Points close to it indicate good accuracy.</p>
      </div>
    </div>
  )
}
