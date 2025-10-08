'use client'
import { useState } from 'react'

export default function LoginPage() {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [error, setError] = useState('')

  const login = () => {
    if (user === 'admin' && pass === '123456') {
      localStorage.setItem('auth', 'true')
      window.location.href = '/chat'
    } else {
      setError('Λάθος στοιχεία')
    }
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen">
      <h1 className="text-2xl mb-4 font-bold">Login</h1>
      <input className="border p-2 mb-2" placeholder="username" onChange={e => setUser(e.target.value)} />
      <input className="border p-2 mb-2" placeholder="password" type="password" onChange={e => setPass(e.target.value)} />
      <button className="bg-blue-500 text-white px-4 py-2 rounded" onClick={login}>Σύνδεση</button>
      {error && <p className="text-red-500 mt-2">{error}</p>}
    </div>
  )
}
