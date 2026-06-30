import React, { useEffect, useState } from 'react';
import { PageHeader } from '../../components/layout';
import { CameraFeedCard, EventLog } from '../../components/cameras';
import { useEventStream, useCameraTracking } from '../../hooks';
import type { Store } from '../../types';
import { cameraApi } from '../../services/cameraApi';
import type { Camera } from '../../services/cameraApi';
import storeLayout from '../../assets/store-layout.png';

const CAMERA_MAP_POSITIONS: Record<number, { top: string; left: string; defaultLabel: string }> = {
  0: { left: '50%', top: '91%', defaultLabel: 'Main Entrance' },
  1: { left: '52%', top: '56%', defaultLabel: 'Cashier Desk' },
  2: { left: '64%', top: '28%', defaultLabel: 'Display Lounge' },
  3: { left: '26%', top: '84%', defaultLabel: 'Left Display' },
  4: { left: '76%', top: '84%', defaultLabel: 'Right Display' },
  5: { left: '32%', top: '22%', defaultLabel: 'Store Backroom' },
};

interface LiveFeedsPageProps {
  store: Store;
}

/**
 * Live Feeds page — real-time CCTV feed simulation with detection overlays,
 * pipeline status tracking, and domain event log driven by SSE.
 */
const LiveFeedsPage: React.FC<LiveFeedsPageProps> = ({ store }) => {
  const { events, cameraStatuses, liveDetections } = useEventStream(store.id);
  const { cameras, completedCameras, processingCamera } = useCameraTracking(
    store.cameras,
    cameraStatuses
  );
  
  const [dbCameras, setDbCameras] = useState<Camera[]>([]);

  useEffect(() => {
    cameraApi.fetchCameras()
      .then(setDbCameras)
      .catch((err) => console.error('Failed to fetch cameras:', err));
  }, []);

  return (
    <div className="page-fade-in" id="live-feeds-page">
      <PageHeader
        title="Store Cam processing"
      />

      {cameras.length === 0 ? (
        <div className="no-data-state" style={{ margin: '40px 0', border: '1px dashed var(--color-border)', borderRadius: 'var(--radius-lg)', padding: '60px 20px' }}>
          <div className="icon" style={{ fontSize: '3rem', marginBottom: '12px' }}>📹</div>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No active cameras configured. Please go to Store Settings to add cameras.</p>
        </div>
      ) : (
        <div
          className="feeds-grid"
          style={{
            display: 'grid',
            gridTemplateColumns:
              cameras.length <= 2
                ? '1fr'
                : cameras.length <= 4
                ? 'repeat(2, minmax(0, 1fr))'
                : 'repeat(3, minmax(0, 1fr))',
            gap: '20px',
            marginTop: '24px'
          }}
        >
          {cameras.map((cam) => (
            <CameraFeedCard
              key={cam.key}
              camKey={cam.key}
              name={cam.name}
              fps={cam.fps}
              cameraStatus={cameraStatuses[cam.key] ?? { status: 'IDLE', progress: 0 }}
              trackCount={liveDetections[cam.key]?.length ?? 0}
              detections={liveDetections[cam.key] ?? []}
            />
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '32px' }}>
        {/* Live Store Layout Card */}
        <div className="hud-frame" style={{ minHeight: '360px', display: 'flex', flexDirection: 'column' }}>
          <div className="corner-accent corner-tl"></div>
          <div className="corner-accent corner-tr"></div>
          <div className="corner-accent corner-bl"></div>
          <div className="corner-accent corner-br"></div>
          
          <h3 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Live Store Radar Map
          </h3>
          
          <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0a0a0a', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.04)', overflow: 'hidden', minHeight: '320px' }}>
            {/* The Blueprint Map Image with Inverted Orange-Glow Filter */}
            <img 
              src={storeLayout} 
              alt="Store Layout" 
              style={{ 
                maxWidth: '92%', 
                maxHeight: '92%', 
                objectFit: 'contain',
                filter: 'invert(0.92) sepia(0.3) saturate(1.8) hue-rotate(345deg) brightness(0.95) contrast(1.15)' 
              }} 
            />
            
            {/* Dynamic camera dots driven by position_index */}
            {dbCameras.filter(c => c.status === 'active' && c.position_index !== null && c.position_index !== undefined).map(cam => {
              const pos = CAMERA_MAP_POSITIONS[cam.position_index!];
              if (!pos) return null;
              
              // Check if camera is currently processing/active in event stream
              const streamStatus = cameraStatuses[cam.id] || cameraStatuses[cam.name.toLowerCase().replace(/\s+/g, '-')] || { status: 'IDLE' };
              const isProcessing = streamStatus.status === 'PROCESSING';
              
              return (
                <div 
                  key={cam.id} 
                  style={{
                    position: 'absolute',
                    left: pos.left,
                    top: pos.top,
                    transform: 'translate(-50%, -50%)',
                    cursor: 'pointer',
                    zIndex: 10
                  }}
                  title={`${cam.name} (${cam.camera_type}) - Status: ${streamStatus.status}`}
                >
                  {/* Outer pulsing ring */}
                  <div style={{
                    position: 'absolute',
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    background: isProcessing ? 'rgba(234, 88, 12, 0.4)' : 'rgba(249, 115, 22, 0.2)',
                    transform: 'translate(-50%, -50%)',
                    animation: 'pulse-glow 2s infinite ease-in-out'
                  }} />
                  {/* Inner active dot */}
                  <div style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: isProcessing ? '#f97316' : '#ea580c',
                    border: '1.5px solid #fff',
                    transform: 'translate(-50%, -50%)'
                  }} />
                  {/* Small tooltip tag */}
                  <div style={{
                    position: 'absolute',
                    left: '12px',
                    top: '-12px',
                    background: 'rgba(0,0,0,0.85)',
                    color: 'var(--color-accent-soft)',
                    border: '1px solid rgba(234,88,12,0.3)',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    fontSize: '0.62rem',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.5)'
                  }}>
                    {cam.name}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        
        {/* Live event log */}
        <EventLog
          events={events}
          processingCamera={processingCamera}
          completedCameras={completedCameras}
          totalCameras={cameras.length}
        />
      </div>
    </div>
  );
};

export default LiveFeedsPage;
