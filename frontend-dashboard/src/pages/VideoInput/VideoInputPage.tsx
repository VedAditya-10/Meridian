import React, { useState, useRef, useCallback, useEffect } from 'react';
import { API_BASE } from '../../constants';
import spyNewspaper from '../../assets/spy-newspaper.webp';

/* ─────────────────────────────────────────────────────────────────────────────
   Types
   ───────────────────────────────────────────────────────────────────────────── */
// ... types block omitted for clarity, keeping unchanged ...
interface PipelineJob {
  camera_id: string;
  store_id: string;
  source_type: 'file' | 'live';
  source: string;
  status: string;
  progress: number;
  error: string | null;
  started_at: number;
}

interface VideoInputPageProps {
  storeId: string;
}

/* ─────────────────────────────────────────────────────────────────────────────
   SVG Icons (inline — no external deps)
   ───────────────────────────────────────────────────────────────────────────── */

const UploadIcon = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const CameraIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
    <circle cx="12" cy="13" r="4" />
  </svg>
);

const StopIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <rect x="4" y="4" width="16" height="16" rx="2" />
  </svg>
);

const TrashIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </svg>
);

const PlayIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

/* ─────────────────────────────────────────────────────────────────────────────
   Component
   ───────────────────────────────────────────────────────────────────────────── */

const VideoInputPage: React.FC<VideoInputPageProps> = ({ storeId }) => {
  // ── Upload state ──
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadCameraId, setUploadCameraId] = useState('cam-1');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadMsg, setUploadMsg] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Live camera state ──
  const [liveDeviceIndex, setLiveDeviceIndex] = useState(0);
  const [liveCameraId, setLiveCameraId] = useState('cam-live');
  const [liveStatus, setLiveStatus] = useState<'idle' | 'starting' | 'active' | 'stopping'>('idle');

  // ── Jobs state ──
  const [jobs, setJobs] = useState<PipelineJob[]>([]);

  /* ── Poll jobs every 3s ── */
  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch(`${API_BASE}/pipeline/status`);
        if (res.ok) {
          const data: PipelineJob[] = await res.json();
          setJobs(data);

          // Auto-update live status based on active jobs
          const liveJob = data.find(
            (j) => j.camera_id === liveCameraId && j.source_type === 'live'
          );
          if (liveJob) {
            if (liveJob.status === 'PROCESSING') setLiveStatus('active');
            else if (liveJob.status === 'STOPPED' || liveJob.status === 'ERROR')
              setLiveStatus('idle');
          }
        }
      } catch {
        /* silently ignore — API may not be up yet */
      }
    };

    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, [liveCameraId]);

  /* ── Drag & drop handlers ── */
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragOver(false), []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setUploadFile(file);
      setUploadMsg('');
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadFile(file);
      setUploadMsg('');
    }
  }, []);

  /* ── Upload video ── */
  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadProgress(0);
    setUploadMsg('');

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('camera_id', uploadCameraId);
    formData.append('store_id', storeId);

    try {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/pipeline/upload`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          setUploadProgress(Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          setUploadMsg('Pipeline started — tracking below.');
          setUploadFile(null);
          if (fileInputRef.current) fileInputRef.current.value = '';
        } else {
          const errData = JSON.parse(xhr.responseText);
          setUploadMsg(`Error: ${errData.detail || xhr.statusText}`);
        }
        setUploading(false);
        setUploadProgress(0);
      };

      xhr.onerror = () => {
        setUploadMsg('Network error — is the backend running?');
        setUploading(false);
        setUploadProgress(0);
      };

      xhr.send(formData);
    } catch (err: any) {
      setUploadMsg(`Upload failed: ${err.message}`);
      setUploading(false);
    }
  };

  /* ── Start live camera ── */
  const handleStartLive = async () => {
    setLiveStatus('starting');
    try {
      const res = await fetch(`${API_BASE}/pipeline/start-live`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          camera_id: liveCameraId,
          store_id: storeId,
          device_index: liveDeviceIndex,
        }),
      });
      if (res.ok) {
        setLiveStatus('active');
      } else {
        const data = await res.json();
        alert(data.detail || 'Failed to start camera');
        setLiveStatus('idle');
      }
    } catch {
      alert('Network error — is the backend running?');
      setLiveStatus('idle');
    }
  };

  /* ── Stop a pipeline ── */
  const handleStop = async (cameraId: string) => {
    try {
      await fetch(`${API_BASE}/pipeline/stop/${cameraId}`, { method: 'POST' });
      if (cameraId === liveCameraId) setLiveStatus('stopping');
    } catch {
      /* ignore */
    }
  };

  /* ── Clear finished jobs ── */
  const handleClear = async () => {
    try {
      await fetch(`${API_BASE}/pipeline/clear`, { method: 'DELETE' });
    } catch {
      /* ignore */
    }
  };

  /* ── Helpers ── */
  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const statusClass = (s: string) => {
    if (s === 'PROCESSING') return 'status-processing';
    if (s === 'COMPLETE') return 'status-complete';
    if (s === 'ERROR') return 'status-error';
    if (s === 'STOPPED') return 'status-stopped';
    return 'status-queued';
  };

  const activeJobs = jobs.filter((j) => j.status === 'PROCESSING' || j.status === 'QUEUED');
  const finishedJobs = jobs.filter((j) => j.status !== 'PROCESSING' && j.status !== 'QUEUED');

  /* ─────────────────────────────────────────────────────────────────────────
     Render
     ─────────────────────────────────────────────────────────────────────── */

  return (
    <div className="page-fade-in vi-page-layout" style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '32px', alignItems: 'start' }}>
      {/* Left Column: Branding and Spy HUD frame */}
      <aside style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title">Video Input</h1>
          <p className="page-subtitle" style={{ marginTop: '12px', lineHeight: 1.6 }}>
            Upload CCTV footage or connect a live camera to start the analytics pipeline.
          </p>
        </div>

        {/* HUD Frame for Spy illustration */}
        <div className="hud-frame" style={{ textAlign: 'center' }}>
          <div className="corner-accent corner-tl"></div>
          <div className="corner-accent corner-tr"></div>
          <div className="corner-accent corner-bl"></div>
          <div className="corner-accent corner-br"></div>
          
          <img 
            src={spyNewspaper} 
            alt="Surveillance Agent" 
            style={{ 
              width: '100%', 
              height: 'auto', 
              borderRadius: 'var(--radius-sm)', 
              border: '1px solid rgba(255,255,255,0.06)',
              marginBottom: '16px',
              background: '#0a0a0a',
              display: 'block'
            }} 
          />
          <div style={{ fontSize: '0.75rem', letterSpacing: '0.08em', color: 'var(--color-accent-soft)', fontWeight: 700, textTransform: 'uppercase' }}>
            AGENT ACTIVE // MONITORING SECTOR
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', marginTop: '6px' }}>
            SECTOR: MERIDIAN-LIVE-FEED
          </div>
        </div>
      </aside>

      {/* Right Column: Grid and table */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
        <div className="vi-grid" style={{ marginTop: '4px' }}>
        {/* ─── Upload Section ─── */}
        <section className="vi-card frosted-glass">
          <div className="vi-card-header">
            <UploadIcon />
            <div>
              <h2>Upload Video File</h2>
              <p>Drag and drop a .mp4, .avi, .mkv, or .mov file</p>
            </div>
          </div>

          {/* Dropzone */}
          <div
            className={`vi-dropzone ${dragOver ? 'drag-over' : ''} ${uploadFile ? 'has-file' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload video file"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp4,.avi,.mkv,.mov,.wmv,.m4v"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            {uploadFile ? (
              <div className="vi-file-info">
                <span className="vi-file-name">{uploadFile.name}</span>
                <span className="vi-file-size">
                  {(uploadFile.size / 1024 / 1024).toFixed(1)} MB
                </span>
              </div>
            ) : (
              <div className="vi-drop-prompt">
                <UploadIcon />
                <span>Click or drag a video file here</span>
              </div>
            )}
          </div>

          {/* Camera ID + Upload btn */}
          <div className="vi-controls-row">
            <div className="vi-input-group">
              <label htmlFor="upload-cam-id">Camera ID</label>
              <input
                id="upload-cam-id"
                type="text"
                value={uploadCameraId}
                onChange={(e) => setUploadCameraId(e.target.value)}
                placeholder="cam-1"
                className="vi-input"
              />
            </div>
            <button
              className="vi-btn vi-btn-primary"
              onClick={handleUpload}
              disabled={!uploadFile || uploading}
            >
              {uploading ? 'Uploading…' : 'Start Processing'}
            </button>
          </div>

          {/* Upload progress */}
          {uploading && (
            <div className="vi-progress-container">
              <div className="vi-progress-bar">
                <div className="vi-progress-fill" style={{ width: `${uploadProgress}%` }} />
              </div>
              <span className="vi-progress-label">{uploadProgress}%</span>
            </div>
          )}

          {/* Status message */}
          {uploadMsg && (
            <div className={`vi-msg ${uploadMsg.startsWith('Error') ? 'vi-msg-error' : 'vi-msg-success'}`}>
              {uploadMsg}
            </div>
          )}
        </section>

        {/* ─── Live Camera Section ─── */}
        <section className="vi-card frosted-glass">
          <div className="vi-card-header">
            <CameraIcon />
            <div>
              <h2>Live Camera Feed</h2>
              <p>Connect a webcam or USB camera</p>
            </div>
          </div>

          <div className="vi-live-body">
            {/* Device selector */}
            <div className="vi-device-grid">
              {[0, 1, 2].map((idx) => (
                <button
                  key={idx}
                  className={`vi-device-btn ${liveDeviceIndex === idx ? 'selected' : ''}`}
                  onClick={() => setLiveDeviceIndex(idx)}
                  disabled={liveStatus === 'active'}
                >
                  <CameraIcon />
                  <span>{idx === 0 ? 'Default Webcam' : `USB Camera ${idx}`}</span>
                </button>
              ))}
            </div>

            {/* Camera ID input */}
            <div className="vi-input-group">
              <label htmlFor="live-cam-id">Camera ID</label>
              <input
                id="live-cam-id"
                type="text"
                value={liveCameraId}
                onChange={(e) => setLiveCameraId(e.target.value)}
                placeholder="cam-live"
                className="vi-input"
                disabled={liveStatus === 'active'}
              />
            </div>

            {/* Start / Stop */}
            <div className="vi-live-actions">
              {liveStatus === 'idle' || liveStatus === 'stopping' ? (
                <button
                  className="vi-btn vi-btn-primary"
                  onClick={handleStartLive}
                  disabled={liveStatus === 'stopping'}
                >
                  <PlayIcon /> {liveStatus === 'stopping' ? 'Stopping…' : 'Start Feed'}
                </button>
              ) : (
                <button
                  className="vi-btn vi-btn-danger"
                  onClick={() => handleStop(liveCameraId)}
                  disabled={liveStatus === 'starting'}
                >
                  <StopIcon /> {liveStatus === 'starting' ? 'Starting…' : 'Stop Feed'}
                </button>
              )}

              <div className={`vi-live-badge ${liveStatus}`}>
                <div className="vi-live-dot" />
                {liveStatus === 'active' ? 'LIVE' : liveStatus.toUpperCase()}
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* ─── Active Jobs Table ─── */}
      <section className="vi-jobs-section">
        <div className="vi-jobs-header">
          <h2>Pipeline Jobs</h2>
          <div className="vi-jobs-actions">
            <span className="vi-jobs-count">
              {activeJobs.length} active · {finishedJobs.length} finished
            </span>
            {finishedJobs.length > 0 && (
              <button className="vi-btn vi-btn-ghost" onClick={handleClear}>
                <TrashIcon /> Clear Finished
              </button>
            )}
          </div>
        </div>

        {jobs.length === 0 ? (
          <div className="vi-empty-jobs frosted-glass">
            <span className="vi-empty-icon">📭</span>
            <p>No pipeline jobs yet. Upload a video or start a camera to begin.</p>
          </div>
        ) : (
          <div className="vi-jobs-table-wrapper frosted-glass">
            <table className="vi-jobs-table">
              <thead>
                <tr>
                  <th>Camera</th>
                  <th>Source</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Started</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={`${job.camera_id}-${job.started_at}`}>
                    <td className="vi-cell-cam">{job.camera_id}</td>
                    <td className="vi-cell-source" title={job.source}>{job.source}</td>
                    <td>
                      <span className={`vi-type-chip ${job.source_type}`}>
                        {job.source_type === 'file' ? '📁 File' : '📹 Live'}
                      </span>
                    </td>
                    <td>
                      <span className={`vi-status-chip ${statusClass(job.status)}`}>
                        {job.status}
                      </span>
                    </td>
                    <td>
                      {job.source_type === 'file' ? (
                        <div className="vi-cell-progress">
                          <div className="vi-mini-bar">
                            <div
                              className="vi-mini-fill"
                              style={{ width: `${job.progress}%` }}
                            />
                          </div>
                          <span>{job.progress}%</span>
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="text-muted">{formatTime(job.started_at)}</td>
                    <td>
                      {(job.status === 'PROCESSING' || job.status === 'QUEUED') && (
                        <button
                          className="vi-btn vi-btn-sm vi-btn-danger"
                          onClick={() => handleStop(job.camera_id)}
                          title="Stop pipeline"
                        >
                          <StopIcon />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Error display */}
        {jobs.some((j) => j.error) && (
          <div className="vi-errors">
            {jobs
              .filter((j) => j.error)
              .map((j) => (
                <div key={j.camera_id} className="vi-error-item">
                  <strong>{j.camera_id}:</strong> {j.error}
                </div>
              ))}
          </div>
        )}
      </section>
      </div>
    </div>
  );
};

export default VideoInputPage;
