import { Navigate, createBrowserRouter } from 'react-router-dom'
import PhoneDemoPage from '../pages/PhoneDemoPage'
import HomePage from '../pages/HomePage'

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/demo" replace /> },
  { path: '/demo', element: <PhoneDemoPage /> },
  { path: '/app', element: <HomePage /> },
])
