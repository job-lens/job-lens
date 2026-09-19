import { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { createBrowserRouter, Link, Outlet, RouterProvider } from 'react-router';
import { LoginPage, SessionGate } from '@/features/auth/public';
import { ErrorPanel } from '@/shared/ui/AsyncState';
import { PlatformContext } from '@/shared/platform/context';
import { webPlatform } from '@/shared/platform/web';
import { createQueryClient } from './query';
import { featureRoutes } from './routes.generated';
import { StatusPage } from './StatusPage';
import styles from './App.module.css';

function Shell() {
  return (
    <div className={styles.shell}>
      <a href="#main" className="skip-link">
        跳到主要内容
      </a>
      <header className={styles.header}>
        <strong>融职境</strong>
        <nav aria-label="主导航">
          <Link to="/">工程入口</Link>
          <Link to="/learner">学员端</Link>
          <Link to="/counselor">辅导员端</Link>
        </nav>
      </header>
      <main id="main" className={styles.main} tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
export function App() {
  const [queryClient] = useState(createQueryClient);
  const [router] = useState(() =>
    createBrowserRouter([
      {
        element: <Shell />,
        errorElement: <ErrorPanel message="页面未能加载" />,
        children: [
          { index: true, element: <StatusPage /> },
          { path: '/login', element: <LoginPage /> },
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
