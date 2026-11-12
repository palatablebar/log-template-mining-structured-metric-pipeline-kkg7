import { createBrowserRouter, Navigate } from 'react-router-dom';
import { StationShell } from '../components/layout/StationShell';
import { LoginPage } from '../pages/Login';
import { SourcesPage } from '../pages/Sources';
import { TemplatesPage } from '../pages/Templates';
import { EventsPage } from '../pages/Events';
import { AlertsPage } from '../pages/Alerts';
import { ImportPage } from '../pages/Import';
import { requireAuth } from './guards';

const shell = (element: React.ReactNode) => <StationShell>{element}</StationShell>;

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/', loader: requireAuth, element: <Navigate to="/sources" replace /> },
  { path: '/sources', loader: requireAuth, element: shell(<SourcesPage />) },
  { path: '/templates', loader: requireAuth, element: shell(<TemplatesPage />) },
  { path: '/events', loader: requireAuth, element: shell(<EventsPage />) },
  { path: '/alerts', loader: requireAuth, element: shell(<AlertsPage />) },
  { path: '/import', loader: requireAuth, element: shell(<ImportPage />) },
  { path: '*', element: <Navigate to="/sources" replace /> },
]);
