import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './AuthContext'
import Login from './pages/Login'
import Layout from './pages/Layout'
import DemandMap from './pages/DemandMap'
import Performance from './pages/Performance'

function PrivateRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route index element={<Navigate to="/map" replace />} />
        <Route path="map" element={<DemandMap />} />
        <Route path="performance" element={<Performance />} />
      </Route>
    </Routes>
  )
}
