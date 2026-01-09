import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { MissionControlPage } from './pages/MissionControlPage'
import { PackageDetailPage } from './pages/PackageDetailPage'
import { EvidencePage } from './pages/EvidencePage'
import { SettingsPage } from './pages/SettingsPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/mission-control" replace />} />
        <Route path="/mission-control" element={<MissionControlPage />} />
        <Route path="/packages/:packageId" element={<PackageDetailPage />} />
        <Route path="/packages/:packageId/invoices/:invoiceId/evidence" element={<EvidencePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Layout>
  )
}

export default App
