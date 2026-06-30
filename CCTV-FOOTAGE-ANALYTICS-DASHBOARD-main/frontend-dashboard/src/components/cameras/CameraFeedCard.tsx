import React from 'react';
import type { CameraStatus, Detection } from '../../types';

interface CameraFeedCardProps {
  camKey: string;
  name: string;
  fps: number;
  cameraStatus: CameraStatus;
  trackCount: number;
  detections: Detection[];
}

/**
 * Simulated CCTV camera feed card with detection overlays,
 * scan-line animation, and pipeline progress bar.
 */
export const CameraFeedCard: React.FC<CameraFeedCardProps> = ({
  camKey,
  name,
  fps,
  cameraStatus,
  detections,
}) => {
  const statusColor =
    cameraStatus.status === 'COMPLETE'
      ? '#10b981'
      : cameraStatus.status === 'PROCESSING'
        ? '#f59e0b'
        : cameraStatus.status === 'ERROR'
          ? '#ef4444'
          : '#6b7280';

  const statusLabel =
    cameraStatus.status === 'COMPLETE'
      ? '✅ Complete'
      : cameraStatus.status === 'PROCESSING'
        ? `⏳ Processing ${cameraStatus.progress.toFixed(0)}%`
        : cameraStatus.status === 'ERROR'
          ? '❌ Error'
          : '⏸ Waiting';

  return (
    <div className="camera-feed-card frosted-glass">
      <div
        className="camera-feed-preview"
        style={{ position: 'relative', overflow: 'hidden', width: '100%', paddingBottom: '56.25%' }}
      >
        {/* Dark CCTV-style background */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'radial-gradient(ellipse at 50% 50%, #0d1824 0%, #050a0e 100%)',
            zIndex: 1,
          }}
        />
        <div className="camera-grid-overlay" style={{ zIndex: 2, pointerEvents: 'none' }} />
        <div
          className="camera-scan-line"
          style={{
            animationDuration: `${2 + parseFloat(camKey.split('-')[1] ?? '1') * 0.5}s`,
            zIndex: 3,
            pointerEvents: 'none',
          }}
        />

        {/* Camera label */}
        <div
          className="camera-feed-label"
          style={{
            zIndex: 10,
            position: 'absolute',
            top: 10,
            left: 10,
            background: 'rgba(0,0,0,0.6)',
            padding: '2px 6px',
            borderRadius: 4,
          }}
        >
          {camKey.toUpperCase()}
        </div>

        {/* Status badge */}
        <div
          style={{
            zIndex: 10,
            position: 'absolute',
            top: 10,
            right: 10,
            background: 'rgba(0,0,0,0.7)',
            padding: '3px 8px',
            borderRadius: 4,
            fontSize: '0.65rem',
            fontWeight: 700,
            color: statusColor,
            border: `1px solid ${statusColor}40`,
          }}
        >
          {statusLabel}
        </div>

        {/* Detection bounding boxes */}
        <div
          className="detection-boxes"
          style={{ zIndex: 10, position: 'absolute', inset: 0, pointerEvents: 'none' }}
        >
          {detections.map((d) => (
            <div
              key={d.id}
              className="det-box"
              data-id={d.id}
              style={{
                position: 'absolute',
                top: d.top,
                left: d.left,
                width: d.width,
                height: d.height,
                border: '2px solid #ea580c',
                boxShadow: '0 0 8px #ea580c',
                transition: 'all 0.2s ease-out',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: -18,
                  left: -2,
                  background: '#ea580c',
                  color: '#fff',
                  fontSize: '0.6rem',
                  fontWeight: 700,
                  padding: '1px 4px',
                  borderRadius: '2px 2px 0 0',
                  whiteSpace: 'nowrap',
                }}
              >
                {d.id}
              </span>
            </div>
          ))}
        </div>

        {/* Track count overlay */}
        <div
          style={{
            position: 'absolute',
            bottom: 10,
            left: 12,
            fontSize: '0.7rem',
            color: 'rgba(16,185,129,0.9)',
            fontWeight: 700,
            background: 'rgba(0,0,0,0.6)',
            padding: '2px 8px',
            borderRadius: 4,
            zIndex: 10,
          }}
        >
          {detections.length} tracked
        </div>

        {/* Progress bar */}
        {cameraStatus.status === 'PROCESSING' && (
          <div
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              height: 3,
              background: 'rgba(255,255,255,0.1)',
              zIndex: 15,
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${cameraStatus.progress}%`,
                background: 'linear-gradient(90deg, #f59e0b, #ea580c)',
                transition: 'width 0.5s ease-out',
              }}
            />
          </div>
        )}
      </div>

      <div className="camera-feed-info">
        <div className="camera-feed-header">
          <span className="camera-name">{name}</span>
          <span
            className={`camera-status-pill ${cameraStatus.status === 'PROCESSING' || cameraStatus.status === 'COMPLETE'
              ? 'live'
              : ''
              }`}
          >
            ●{' '}
            {cameraStatus.status === 'PROCESSING'
              ? 'Processing'
              : cameraStatus.status === 'COMPLETE'
                ? 'Done'
                : 'Idle'}
          </span>
        </div>
        <div className="camera-meta">
          <span>🎬 {fps} FPS (sampled)</span>
          <span>📁 Direct File</span>
          <span>🔍 YOLOv8n</span>
        </div>
      </div>
    </div>
  );
};
