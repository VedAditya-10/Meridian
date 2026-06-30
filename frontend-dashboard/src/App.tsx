import React, { useState, useEffect, useCallback, useRef } from 'react';
import './styles/index.css';
import gsap from 'gsap';
import spyPeeking from './assets/spy-peeking.png';

import { Sidebar, Topbar } from './components/layout';
import { DEFAULT_STORE } from './constants';
import { ROUTES } from './app/routes';
import type { RouteId } from './app/routes';
import type { Store } from './types';
import { fetchMeridianStore } from './services/storeApi';

import OverviewPage  from './pages/Overview/OverviewPage';
import LiveFeedsPage from './pages/LiveFeeds/LiveFeedsPage';
import HeatmapsPage  from './pages/Heatmaps/HeatmapsPage';
import AnomaliesPage from './pages/Anomalies/AnomaliesPage';
import VideoInputPage from './pages/VideoInput/VideoInputPage';
import StoreManagementPage from './pages/StoreManagement/StoreManagementPage';

const DEFAULT_ROUTE: RouteId = ROUTES[0].id as RouteId;

/**
 * Meridian application root — single store, no store selector.
 */
const App: React.FC = () => {
  const [activeRoute, setActiveRoute] = useState<RouteId>(DEFAULT_ROUTE);
  const [store, setStore] = useState<Store>(DEFAULT_STORE);

  const refreshStore = useCallback(async () => {
    const data = await fetchMeridianStore();
    if (data) setStore(data);
  }, []);

  useEffect(() => {
    refreshStore();
  }, [refreshStore]);

  const peekingSpyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!peekingSpyRef.current) return;
    
    // Initial setup: hide character mostly below viewport
    gsap.set(peekingSpyRef.current, { yPercent: 85, rotation: 0 });

    // Loop animation timeline: peek up, look around, retreat
    const tl = gsap.timeline({ repeat: -1, repeatDelay: 12 });
    
    tl.to(peekingSpyRef.current, {
      yPercent: 12,
      duration: 0.6,
      ease: 'power2.out'
    })
    .to(peekingSpyRef.current, {
      rotation: -3,
      duration: 0.4,
      ease: 'power1.inOut'
    })
    .to(peekingSpyRef.current, {
      rotation: 3,
      duration: 0.5,
      ease: 'power1.inOut',
      yoyo: true,
      repeat: 3
    })
    .to(peekingSpyRef.current, {
      rotation: 0,
      duration: 0.3,
      ease: 'power1.inOut'
    })
    .to(peekingSpyRef.current, {
      yPercent: 85,
      duration: 0.5,
      ease: 'power2.in'
    });

    return () => {
      tl.kill();
    };
  }, []);

  return (
    <div className="app-wrapper theme-dark premium-glass-bg">
      <Sidebar
        activeRoute={activeRoute}
        onNavigate={(route) => setActiveRoute(route as RouteId)}
        store={store}
      />

      <main className="main-content">
        <Topbar
          activeRoute={activeRoute}
          storeName={store.name}
          timezone={store.timezone || 'Asia/Kolkata'}
        />

        <div className="viewport-scroll-area">
          {activeRoute === 'video-input' && (
            <VideoInputPage storeId={store.id} />
          )}
          {activeRoute === 'overview' && (
            <OverviewPage storeId={store.id} storeName={store.name} />
          )}
          {activeRoute === 'cameras' && (
            <LiveFeedsPage store={store} />
          )}
          {activeRoute === 'heatmaps' && (
            <HeatmapsPage storeId={store.id} storeName={store.name} />
          )}
          {activeRoute === 'anomalies' && (
            <AnomaliesPage storeId={store.id} storeName={store.name} />
          )}
          {activeRoute === 'store-management' && (
            <StoreManagementPage onStoreUpdated={refreshStore} />
          )}
        </div>
      </main>
      <div ref={peekingSpyRef} className="peeking-spy-container">
        <img src={spyPeeking} alt="Peeking Spy" />
      </div>
    </div>
  );
};

export default App;
