import { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { createBrowserRouter, RouterProvider } from 'react-router';
import {
  LoginPage,
  RegisterPage,
  ForgotPasswordPage,
  ResetPasswordPage,
  SessionGate,
} from '@/features/auth/public';
import { ErrorPanel } from '@/shared/ui/AsyncState';
import { PlatformContext } from '@/shared/platform/context';
import { webPlatform } from '@/shared/platform/web';
import { createQueryClient } from './query';
import { featureRoutes } from './routes.generated';
import { LandingPage } from './LandingPage';
import { StatusPage } from './StatusPage';
import { WorkspaceShell } from './WorkspaceShell';

export function App() {
  const [queryClient] = useState(createQueryClient);
  const [router] = useState(() =>
    createBrowserRouter([
      { path: '/', element: <LandingPage />, errorElement: <ErrorPanel message="页面未能加载" /> },
      {
        path: '/login',
        element: <LoginPage />,
        errorElement: <ErrorPanel message="页面未能加载" />,
      },
      {
        path: '/register',
        element: <RegisterPage />,
        errorElement: <ErrorPanel message="页面未能加载" />,
      },
      {
        path: '/forgot-password',
        element: <ForgotPasswordPage />,
        errorElement: <ErrorPanel message="页面未能加载" />,
      },
      {
        path: '/reset-password',
        element: <ResetPasswordPage />,
        errorElement: <ErrorPanel message="页面未能加载" />,
      },
      {
        element: <WorkspaceShell />,
        errorElement: <ErrorPanel message="页面未能加载" />,
        children: [
          { path: '/status', element: <StatusPage /> },
          ...featureRoutes.map(({ role, ...route }) => ({
            element: <SessionGate role={role} />,
            children: [route],
          })),
          { path: '*', element: <ErrorPanel message="页面不存在" /> },
        ],
      },
    ]),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <PlatformContext.Provider value={webPlatform}>
        <RouterProvider router={router} />
      </PlatformContext.Provider>
    </QueryClientProvider>
  );
}
