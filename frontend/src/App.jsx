import { useEffect, useState } from "react"

function App() {
  const [backend, setBackend] = useState("...")
  const [db, setDb] = useState("...")

  useEffect(() => {
    fetch("http://localhost:8000/")
      .then(r => r.json())
      .then(d => setBackend(d.status))

    fetch("http://localhost:8000/health/db")
      .then(r => r.json())
      .then(d => setDb(d.db))
  }, [])

  return (
    <div style={{ padding: 32, fontFamily: "sans-serif" }}>
      <h2>Incident Response Platform</h2>
      <p>Backend: <strong>{backend}</strong></p>
      <p>Database: <strong>{db}</strong></p>
    </div>
  )
}

export default App