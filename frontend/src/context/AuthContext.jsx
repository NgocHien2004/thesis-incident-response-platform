import { createContext, useContext, useState } from 'react'
import { login as loginApi, getMe } from '../api'

const AuthContext = createContext(null)

function readUser() {
  try {
    const token = localStorage.getItem('access_token')
    const saved = localStorage.getItem('user')
    return token && saved ? JSON.parse(saved) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readUser)

  const login = async (username, password) => {
    const res = await loginApi({ username, password })
    localStorage.setItem('access_token', res.data.access_token)
    const me = await getMe()
    localStorage.setItem('user', JSON.stringify(me.data))
    setUser(me.data)
    return me.data
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext)
