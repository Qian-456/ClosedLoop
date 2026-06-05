import { Navigate, createBrowserRouter } from 'react-router-dom'
import PhoneDemoPage from '../pages/PhoneDemoPage'
import HomePage from '../pages/HomePage'
import SharePage from '../pages/SharePage'

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/demo" replace /> },
  { path: '/demo', element: <PhoneDemoPage /> },
  { path: '/app', element: <HomePage /> },
  { path: '/share/:shareId', element: <SharePage /> },
])
