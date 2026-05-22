import { Navigate, createBrowserRouter } from 'react-router-dom'
import PhoneDemoPage from '../pages/PhoneDemoPage'
import HomePage from '../pages/HomePage'
import GeneratingPage from '../pages/GeneratingPage'
import PlansPage from '../pages/PlansPage'
import PlanDetailPage from '../pages/PlanDetailPage'
import ExecutingPage from '../pages/ExecutingPage'
import JourneyReadyPage from '../pages/JourneyReadyPage'

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/demo" replace /> },
  { path: '/demo', element: <PhoneDemoPage /> },
  { path: '/app', element: <HomePage /> },
  { path: '/app/generating', element: <GeneratingPage /> },
  { path: '/app/plans', element: <PlansPage /> },
  { path: '/app/plans/:planId', element: <PlanDetailPage /> },
  { path: '/app/executing/:planId', element: <ExecutingPage /> },
  { path: '/app/journey/:planId', element: <JourneyReadyPage /> },
])
