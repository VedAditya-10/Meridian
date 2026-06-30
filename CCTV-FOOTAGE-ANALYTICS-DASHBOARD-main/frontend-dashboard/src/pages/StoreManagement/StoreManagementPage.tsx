import React, { useState, useEffect, useRef, useMemo } from 'react';
import { API_BASE } from '../../constants';
import {
  fetchMeridianStore,
  updateMeridianStore,
  clearAnalyticsData,
  cameraApi
} from '../../services';
import type { Camera, Zone } from '../../services/cameraApi';
import type { Store } from '../../types';

const ZONE_COLORS: Record<string, string> = {
  ENTRY_LINE: '#10b981', // Success Green
  DISPLAY: '#f97316',    // Orange
  AISLE: '#06b6d4',      // Cyan
  QUEUE: '#f59e0b',      // Amber
};

// Helper perpendicular vector logic to convert drawn line to 10px thin polygon
function convertLineToThinPolygon(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  canvasWidth: number,
  canvasHeight: number
): { x: number; y: number }[] {
  // Convert normalized to pixels
  const px1 = x1 * canvasWidth;
  const py1 = y1 * canvasHeight;
  const px2 = x2 * canvasWidth;
  const py2 = y2 * canvasHeight;

  const dx = px2 - px1;
  const dy = py2 - py1;
  const len = Math.sqrt(dx * dx + dy * dy);

  if (len === 0) {
    return [
      { x: x1, y: y1 },
      { x: x1 + 0.01, y: y1 },
      { x: x1 + 0.01, y: y1 + 0.01 },
      { x: x1, y: y1 + 0.01 }
    ];
  }

  // Unit perpendicular vector
  const ux = -dy / len;
  const uy = dx / len;

  const thickness = 10; // 10px wide

  // 4 corners in pixels
  const c1x = px1 - ux * (thickness / 2);
  const c1y = py1 - uy * (thickness / 2);
  const c2x = px1 + ux * (thickness / 2);
  const c2y = py1 + uy * (thickness / 2);
  const c3x = px2 + ux * (thickness / 2);
  const c3y = py2 + uy * (thickness / 2);
  const c4x = px2 - ux * (thickness / 2);
  const c4y = py2 - uy * (thickness / 2);

  // Normalize back to 0.0 - 1.0
  return [
    { x: c1x / canvasWidth, y: c1y / canvasHeight },
    { x: c2x / canvasWidth, y: c2y / canvasHeight },
    { x: c3x / canvasWidth, y: c3y / canvasHeight },
    { x: c4x / canvasWidth, y: c4y / canvasHeight }
  ];
}

// Reconstruct 2-point line from thin 4-vertex polygon
function getLineFromThinPolygon(points: { x: number; y: number }[]) {
  if (points.length < 4) {
    return {
      p1: points[0] || { x: 0, y: 0 },
      p2: points[points.length - 1] || { x: 0, y: 0 }
    };
  }
  const p1 = {
    x: (points[0].x + points[1].x) / 2,
    y: (points[0].y + points[1].y) / 2
  };
  const p2 = {
    x: (points[2].x + points[3].x) / 2,
    y: (points[2].y + points[3].y) / 2
  };
  return { p1, p2 };
}

interface StoreManagementPageProps {
  onStoreUpdated: () => void;
}

const StoreManagementPage: React.FC<StoreManagementPageProps> = ({ onStoreUpdated }) => {
  // Store Info form states
  const [store, setStore] = useState<Store | null>(null);
  const [storeName, setStoreName] = useState('');
  const [storeAddress, setStoreAddress] = useState('');
  const [storePhone, setStorePhone] = useState('');
  const [storeTimezone, setStoreTimezone] = useState('Asia/Kolkata');
  const [isSavingStore, setIsSavingStore] = useState(false);

  // Cameras states
  const [camerasList, setCamerasList] = useState<Camera[]>([]);
  const [camerasZonesCount, setCamerasZonesCount] = useState<Record<string, number>>({});
  const [isLoadingStore, setIsLoadingStore] = useState(true);

  // Camera Modals states
  const [isCameraModalOpen, setIsCameraModalOpen] = useState(false);
  const [cameraModalMode, setCameraModalMode] = useState<'add' | 'edit'>('add');
  const [editingCameraId, setEditingCameraId] = useState<string | null>(null);
  
  // Camera Form states
  const [camFormName, setCamFormName] = useState('');
  const [camFormType, setCamFormType] = useState<'rtsp_stream' | 'video_file' | 'webcam'>('rtsp_stream');
  const [camFormRtsp, setCamFormRtsp] = useState('');
  const [camFormFilePath, setCamFormFilePath] = useState('');
  const [camFormStatus, setCamFormStatus] = useState<'active' | 'inactive'>('active');
  const [isSavingCamera, setIsSavingCamera] = useState(false);
  
  // Connection Test states
  const [isTestingConn, setIsTestingConn] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Zones Drawing Canvas states
  const [isZonesModalOpen, setIsZonesModalOpen] = useState(false);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  const [cameraZones, setCameraZones] = useState<Zone[]>([]);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  
  // New Zone parameters
  const [zoneFormName, setZoneFormName] = useState('');
  const [zoneFormType, setZoneFormType] = useState<'ENTRY_LINE' | 'DISPLAY' | 'AISLE' | 'QUEUE'>('DISPLAY');
  const [zoneFormCategory, setZoneFormCategory] = useState('');
  const [isSavingZone, setIsSavingZone] = useState(false);
  
  // Canvas drawing states
  const [drawingMode, setDrawingMode] = useState<'select' | 'polygon' | 'line'>('select');
  const [polygonPoints, setPolygonPoints] = useState<{ x: number; y: number }[]>([]);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [cacheBuster, setCacheBuster] = useState(0);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  // Data management states
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [clearConfirmInput, setClearConfirmInput] = useState('');
  const [isClearingData, setIsClearingData] = useState(false);

  // Global Toast/Status messages
  const [statusMsg, setStatusMsg] = useState('');
  const [statusType, setStatusType] = useState<'success' | 'error' | ''>('');

  // 1. Initial load
  const loadStoreAndCameras = async () => {
    try {
      setIsLoadingStore(true);
      const storeData = await fetchMeridianStore();
      if (storeData) {
        setStore(storeData);
        setStoreName(storeData.name);
        setStoreAddress(storeData.address || '');
        setStorePhone(storeData.phone || '');
        setStoreTimezone(storeData.timezone);
      }
      
      const cameras = await cameraApi.fetchCameras();
      setCamerasList(cameras);

      // Load zones count for each camera
      const counts: Record<string, number> = {};
      for (const cam of cameras) {
        try {
          const zones = await cameraApi.fetchCameraZones(cam.id);
          counts[cam.id] = zones.length;
        } catch {
          counts[cam.id] = 0;
        }
      }
      setCamerasZonesCount(counts);
    } catch (err: any) {
      console.error(err);
      showStatus("Failed to load store settings", "error");
    } finally {
      setIsLoadingStore(false);
    }
  };

  useEffect(() => {
    loadStoreAndCameras();
  }, []);

  const showStatus = (text: string, type: 'success' | 'error') => {
    setStatusMsg(text);
    setStatusType(type);
    setTimeout(() => {
      setStatusMsg('');
      setStatusType('');
    }, 5000);
  };

  // 2. Save store metadata
  const handleSaveStoreInfo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!storeName.trim()) {
      showStatus("Store Name is required", "error");
      return;
    }
    try {
      setIsSavingStore(true);
      await updateMeridianStore({
        name: storeName,
        address: storeAddress,
        phone: storePhone,
        timezone: storeTimezone
      });
      showStatus("Store information updated successfully", "success");
      onStoreUpdated();
      loadStoreAndCameras();
    } catch (err: any) {
      showStatus(err.message || "Failed to update store info", "error");
    } finally {
      setIsSavingStore(false);
    }
  };

  // 3. Clear data handler
  const handleClearData = async () => {
    if (clearConfirmInput !== 'DELETE') {
      alert("Please type exactly 'DELETE' to confirm.");
      return;
    }
    try {
      setIsClearingData(true);
      await clearAnalyticsData('DELETE');
      showStatus("All historical analytics data has been cleared", "success");
      setIsClearModalOpen(false);
      setClearConfirmInput('');
    } catch (err: any) {
      alert(err.message || "Failed to clear analytics data");
    } finally {
      setIsClearingData(false);
    }
  };

  // 4. Camera CRUD Handlers
  const openAddCameraModal = () => {
    setCameraModalMode('add');
    setEditingCameraId(null);
    setCamFormName('');
    setCamFormType('rtsp_stream');
    setCamFormRtsp('');
    setCamFormFilePath('');
    setCamFormStatus('active');
    setTestResult(null);
    setIsCameraModalOpen(true);
  };

  const openEditCameraModal = (cam: Camera) => {
    setCameraModalMode('edit');
    setEditingCameraId(cam.id);
    setCamFormName(cam.name);
    setCamFormType(cam.camera_type);
    setCamFormRtsp(cam.rtsp_url || '');
    setCamFormFilePath(cam.video_file_path || '');
    setCamFormStatus(cam.status === 'active' ? 'active' : 'inactive');
    setTestResult(null);
    setIsCameraModalOpen(true);
  };

  const handleSaveCamera = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!camFormName.trim()) {
      showStatus("Camera name is required", "error");
      return;
    }
    if (camFormType === 'rtsp_stream' && !camFormRtsp.trim()) {
      showStatus("RTSP stream URL is required for RTSP type", "error");
      return;
    }
    if (camFormType === 'video_file' && !camFormFilePath.trim()) {
      showStatus("Video file path is required for video file type", "error");
      return;
    }

    try {
      setIsSavingCamera(true);
      const payload: Partial<Camera> = {
        name: camFormName,
        camera_type: camFormType,
        rtsp_url: camFormType === 'rtsp_stream' ? camFormRtsp : null,
        video_file_path: camFormType === 'video_file' ? camFormFilePath : null,
        status: camFormStatus
      };

      if (cameraModalMode === 'add') {
        await cameraApi.addCamera(payload);
        showStatus("New camera added successfully", "success");
      } else if (editingCameraId) {
        await cameraApi.updateCamera(editingCameraId, payload);
        showStatus("Camera configurations updated successfully", "success");
      }
      setIsCameraModalOpen(false);
      loadStoreAndCameras();
    } catch (err: any) {
      showStatus(err.message || "Failed to save camera configurations", "error");
    } finally {
      setIsSavingCamera(false);
    }
  };

  const handleRemoveCamera = async (camId: string) => {
    if (!confirm("Are you sure you want to remove this camera? Historical analytics data will be preserved, but new feeds will stop processing.")) {
      return;
    }
    try {
      await cameraApi.deleteCamera(camId);
      showStatus("Camera successfully removed (soft-deleted)", "success");
      loadStoreAndCameras();
    } catch (err: any) {
      showStatus(err.message || "Failed to delete camera", "error");
    }
  };

  const handleTestConnection = async () => {
    if (!editingCameraId) return;
    try {
      setIsTestingConn(true);
      setTestResult(null);
      const res = await cameraApi.testCameraConnection(editingCameraId);
      if (res.status === 'success') {
        setTestResult({ success: true, message: res.detail || "Successfully connected and grabbed frame!" });
      } else {
        setTestResult({ success: false, message: res.detail || "Connection failed. Please inspect feed settings." });
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "An error occurred during testing." });
    } finally {
      setIsTestingConn(false);
    }
  };

  // 5. Zone Management Handlers
  const openZonesConfig = async (cam: Camera) => {
    setSelectedCamera(cam);
    setCacheBuster(Date.now());
    setPolygonPoints([]);
    setMousePos(null);
    setDrawingMode('select');
    setSelectedZoneId(null);
    setZoneFormName('');
    setZoneFormType('DISPLAY');
    setZoneFormCategory('');
    setIsZonesModalOpen(true);
    
    // Load camera zones
    try {
      const zones = await cameraApi.fetchCameraZones(cam.id);
      setCameraZones(zones);
    } catch {
      setCameraZones([]);
    }
  };

  const handleImageLoad = () => {
    if (imageRef.current) {
      setCanvasSize({
        width: imageRef.current.clientWidth,
        height: imageRef.current.clientHeight
      });
    }
  };

  // Resize listener
  useEffect(() => {
    const handleResize = () => {
      if (imageRef.current && isZonesModalOpen) {
        setCanvasSize({
          width: imageRef.current.clientWidth,
          height: imageRef.current.clientHeight
        });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isZonesModalOpen]);

  // Redraw canvas on modifications
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || canvasSize.width === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw active existing zones
    cameraZones.forEach((zone) => {
      const isSelected = zone.id === selectedZoneId;
      ctx.lineWidth = isSelected ? 3.5 : 2;
      
      if (zone.zone_type === 'ENTRY_LINE') {
        // Draw thin polygon as a line with entry indicator arrow
        const { p1, p2 } = getLineFromThinPolygon(zone.polygon.points);
        const startX = p1.x * canvas.width;
        const startY = p1.y * canvas.height;
        const endX = p2.x * canvas.width;
        const endY = p2.y * canvas.height;

        ctx.strokeStyle = ZONE_COLORS.ENTRY_LINE;
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.stroke();

        // Midpoint
        const midX = (startX + endX) / 2;
        const midY = (startY + endY) / 2;

        // Draw perp arrow for entry direction representation
        const dx = endX - startX;
        const dy = endY - startY;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
          const ux = -dy / len;
          const uy = dx / len;
          const arrowLen = 15;
          const arrowEndX = midX + ux * arrowLen;
          const arrowEndY = midY + uy * arrowLen;

          ctx.fillStyle = ZONE_COLORS.ENTRY_LINE;
          ctx.beginPath();
          ctx.moveTo(midX, midY);
          ctx.lineTo(arrowEndX, arrowEndY);
          ctx.stroke();

          // Arrow head
          ctx.beginPath();
          ctx.arc(arrowEndX, arrowEndY, 4, 0, Math.PI * 2);
          ctx.fill();
        }
      } else {
        // Draw standard polygons
        const color = ZONE_COLORS[zone.zone_type] || '#ffffff';
        ctx.strokeStyle = color;
        ctx.fillStyle = isSelected ? `${color}4D` : `${color}1F`; // transparent fills
        ctx.beginPath();
        zone.polygon.points.forEach((pt, idx) => {
          const x = pt.x * canvas.width;
          const y = pt.y * canvas.height;
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }

      // Draw zone name label at midpoint
      if (zone.polygon.points.length > 0) {
        let sumX = 0;
        let sumY = 0;
        zone.polygon.points.forEach(pt => {
          sumX += pt.x * canvas.width;
          sumY += pt.y * canvas.height;
        });
        const midX = sumX / zone.polygon.points.length;
        const midY = sumY / zone.polygon.points.length;

        ctx.fillStyle = '#1c1c1c';
        ctx.strokeStyle = '#ffffff50';
        ctx.lineWidth = 1;
        ctx.font = 'bold 10px Inter';
        const txtWidth = ctx.measureText(zone.name).width;
        ctx.fillRect(midX - txtWidth / 2 - 4, midY - 8, txtWidth + 8, 16);
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.fillText(zone.name, midX, midY + 4);
      }
    });

    // Draw active drawing points & previews
    if (drawingMode === 'polygon' && polygonPoints.length > 0) {
      ctx.strokeStyle = ZONE_COLORS[zoneFormType] || '#10b981';
      ctx.fillStyle = `${ZONE_COLORS[zoneFormType] || '#10b981'}22`;
      ctx.lineWidth = 2.5;

      ctx.beginPath();
      polygonPoints.forEach((pt, idx) => {
        const x = pt.x * canvas.width;
        const y = pt.y * canvas.height;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      
      // Line preview to mouse
      if (mousePos) {
        ctx.lineTo(mousePos.x * canvas.width, mousePos.y * canvas.height);
      }

      ctx.stroke();

      // Draw points with index circles
      polygonPoints.forEach((pt, idx) => {
        const x = pt.x * canvas.width;
        const y = pt.y * canvas.height;
        ctx.fillStyle = ZONE_COLORS[zoneFormType] || '#10b981';
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
        
        ctx.fillStyle = '#ffffff';
        ctx.font = '9px Inter';
        ctx.textAlign = 'center';
        ctx.fillText((idx + 1).toString(), x, y - 8);
      });
    }

    if (drawingMode === 'line' && polygonPoints.length === 1 && mousePos) {
      // Line drawing preview
      ctx.strokeStyle = ZONE_COLORS.ENTRY_LINE;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(polygonPoints[0].x * canvas.width, polygonPoints[0].y * canvas.height);
      ctx.lineTo(mousePos.x * canvas.width, mousePos.y * canvas.height);
      ctx.stroke();

      // Start dot
      ctx.fillStyle = ZONE_COLORS.ENTRY_LINE;
      ctx.beginPath();
      ctx.arc(polygonPoints[0].x * canvas.width, polygonPoints[0].y * canvas.height, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();
    }
  }, [canvasSize, cameraZones, selectedZoneId, drawingMode, polygonPoints, mousePos, zoneFormType]);

  // Entrance camera warning logic
  const isEntranceCamera = (cam: Camera) => {
    return cam.name.toLowerCase().includes('entrance') || cam.name.toLowerCase().includes('entry');
  };

  const cameraHasEntryLine = (camId: string) => {
    // Check local counts / zones if loaded, otherwise check warnings
    if (selectedCamera?.id === camId && isZonesModalOpen) {
      return cameraZones.some(z => z.zone_type === 'ENTRY_LINE');
    }
    return true; // fall back to warning banner within modal only, or list warnings dynamically if needed
  };

  // Warnings lists for the active camera modal
  const cameraWarning = useMemo(() => {
    if (!selectedCamera) return null;
    if (isEntranceCamera(selectedCamera)) {
      const hasEntryLine = cameraZones.some(z => z.zone_type === 'ENTRY_LINE');
      if (!hasEntryLine) {
        return "⚠️ No Entry Line Defined: Footfall counting will be disabled for this entrance feed. Add an ENTRY_LINE zone to track footfall.";
      }
    }
    return null;
  }, [selectedCamera, cameraZones]);

  // Canvas Mouse Actions
  const handleCanvasClick = async (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !selectedCamera) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    if (drawingMode === 'polygon') {
      // Check if clicking near first point to close
      if (polygonPoints.length >= 3) {
        const first = polygonPoints[0];
        const dist = Math.sqrt(Math.pow(x - first.x, 2) + Math.pow(y - first.y, 2));
        if (dist < 0.03) {
          // Close polygon and trigger save
          handleSaveNewZone(polygonPoints);
          return;
        }
      }
      setPolygonPoints([...polygonPoints, { x, y }]);
    } else if (drawingMode === 'line') {
      if (polygonPoints.length === 0) {
        setPolygonPoints([{ x, y }]);
      } else if (polygonPoints.length === 1) {
        // Line completed, convert to thin polygon and save
        const lineStart = polygonPoints[0];
        const thinPoly = convertLineToThinPolygon(
          lineStart.x,
          lineStart.y,
          x,
          y,
          canvasRef.current.width,
          canvasRef.current.height
        );
        handleSaveNewZone(thinPoly);
      }
    } else if (drawingMode === 'select') {
      // Find clicked zone
      let clickedZoneId: string | null = null;
      // Loop backwards to check top layer zones first
      for (let i = cameraZones.length - 1; i >= 0; i--) {
        const zone = cameraZones[i];
        if (isPointInPolygon({ x, y }, zone.polygon.points)) {
          clickedZoneId = zone.id;
          break;
        }
      }
      setSelectedZoneId(clickedZoneId);
    }
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setMousePos({ x, y });
  };

  // Simple Ray-Casting Algorithm to detect clicks inside polygon
  const isPointInPolygon = (point: { x: number; y: number }, vs: { x: number; y: number }[]) => {
    const x = point.x, y = point.y;
    let inside = false;
    for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
      const xi = vs[i].x, yi = vs[i].y;
      const xj = vs[j].x, yj = vs[j].y;
      const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  };

  const handleSaveNewZone = async (points: { x: number; y: number }[]) => {
    if (!selectedCamera) return;
    const name = zoneFormName.trim() || `${zoneFormType} Zone ${cameraZones.length + 1}`;
    
    try {
      setIsSavingZone(true);
      await cameraApi.createCameraZone(selectedCamera.id, {
        name,
        zone_type: zoneFormType,
        polygon: {
          camera_ids: [selectedCamera.id],
          points
        },
        product_category: zoneFormType === 'DISPLAY' && zoneFormCategory.trim() ? zoneFormCategory.trim() : null
      });

      // Reload zones
      const zones = await cameraApi.fetchCameraZones(selectedCamera.id);
      setCameraZones(zones);
      
      // Reset
      setPolygonPoints([]);
      setZoneFormName('');
      setZoneFormCategory('');
      setDrawingMode('select');
      
      // Update camera zones counts
      setCamerasZonesCount(prev => ({
        ...prev,
        [selectedCamera.id]: zones.length
      }));
    } catch (err: any) {
      alert(err.message || "Failed to create zone");
    } finally {
      setIsSavingZone(false);
    }
  };

  const handleDeleteZone = async (zoneId: string) => {
    if (!confirm("Are you sure you want to delete this zone? Historical analytics logs for this zone will remain intact, but new events won't be triggered.")) {
      return;
    }
    try {
      await cameraApi.deleteZone(zoneId);
      if (selectedCamera) {
        const zones = await cameraApi.fetchCameraZones(selectedCamera.id);
        setCameraZones(zones);
        setCamerasZonesCount(prev => ({
          ...prev,
          [selectedCamera.id]: zones.length
        }));
      }
      setSelectedZoneId(null);
    } catch (err: any) {
      alert(err.message || "Failed to delete zone");
    }
  };

  return (
    <div className="page-fade-in sm-page">
      <style>{`
        .settings-container {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 24px;
        }
        @media(max-width: 1024px) {
          .settings-container {
            grid-template-columns: 1fr;
          }
        }
        .cam-grid {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .cam-card {
          padding: 16px;
          border-radius: var(--radius-md);
          background: var(--color-bg-secondary);
          border: 1px solid var(--color-border);
          transition: all var(--transition-fast);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .cam-card:hover {
          border-color: var(--color-border-hover);
        }
        .cam-info {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .cam-name-line {
          font-weight: 600;
          font-size: 0.95rem;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .cam-status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .cam-status-dot.active { background: var(--color-success); box-shadow: 0 0 8px var(--color-success); }
        .cam-status-dot.inactive { background: var(--color-text-muted); }
        .cam-status-dot.error { background: var(--color-danger); box-shadow: 0 0 8px var(--color-danger); }
        
        .cam-meta-line {
          font-size: 0.8rem;
          color: var(--color-text-muted);
        }
        .cam-actions {
          display: flex;
          gap: 8px;
        }
        
        /* Modal Backdrop */
        .modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.65);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 100;
          animation: modalFadeIn 0.2s ease-out;
        }
        @keyframes modalFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        
        .modal-box {
          background: var(--color-bg-secondary);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: 24px;
          width: 90%;
          max-width: 500px;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .modal-box-large {
          max-width: 950px;
          width: 95%;
          height: 90vh;
          max-height: 800px;
        }
        
        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: 12px;
        }
        .modal-header h3 {
          font-size: 1.2rem;
          font-weight: 600;
        }
        .modal-close-btn {
          background: none;
          border: none;
          color: var(--color-text-secondary);
          font-size: 1.2rem;
          cursor: pointer;
        }
        .modal-close-btn:hover { color: var(--color-text-primary); }

        .modal-body {
          flex: 1;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding-right: 4px;
        }

        .modal-footer {
          border-top: 1px solid var(--color-border);
          padding-top: 16px;
          display: flex;
          justify-content: flex-end;
          gap: 12px;
        }
        
        /* Zones Grid inside Canvas Modal */
        .canvas-workspace {
          display: grid;
          grid-template-columns: 1.5fr 1fr;
          gap: 20px;
          height: 100%;
          overflow: hidden;
        }
        @media(max-width: 768px) {
          .canvas-workspace {
            grid-template-columns: 1fr;
            overflow-y: auto;
          }
        }
        
        .canvas-toolbar {
          display: flex;
          gap: 6px;
          background: var(--color-bg-primary);
          padding: 6px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--color-border);
        }
        
        .toolbar-btn {
          flex: 1;
          background: none;
          border: none;
          color: var(--color-text-secondary);
          padding: 6px 12px;
          font-size: 0.8rem;
          font-weight: 500;
          border-radius: var(--radius-xs);
          cursor: pointer;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }
        .toolbar-btn:hover {
          color: var(--color-text-primary);
          background: rgba(255, 255, 255, 0.03);
        }
        .toolbar-btn.active {
          color: var(--color-accent);
          background: rgba(234, 88, 12, 0.12);
        }
        
        .zone-list-scroll {
          max-height: 230px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .zone-item {
          padding: 10px 12px;
          background: var(--color-bg-primary);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          display: flex;
          justify-content: space-between;
          align-items: center;
          cursor: pointer;
          transition: border-color var(--transition-fast);
        }
        .zone-item:hover {
          border-color: var(--color-border-hover);
        }
        .zone-item.selected {
          border-color: var(--color-accent);
          background: rgba(234, 88, 12, 0.04);
        }
        
        .warning-banner {
          background: rgba(245, 158, 11, 0.08);
          border: 1px solid rgba(245, 158, 11, 0.25);
          color: var(--color-warning);
          padding: 10px 14px;
          border-radius: var(--radius-md);
          font-size: 0.8rem;
          line-height: 1.5;
        }
      `}</style>

      {/* Page Header */}
      <div className="page-header">
        <h1 className="page-title">Meridian Settings</h1>
        <p className="page-subtitle">
          Configure single-store configurations, cameras, zones, and clear historical data.
        </p>
      </div>

      {statusMsg && (
        <div className={`vi-msg ${statusType === 'error' ? 'vi-msg-error' : 'vi-msg-success'}`} style={{ marginBottom: 20 }}>
          {statusMsg}
        </div>
      )}

      {isLoadingStore ? (
        <div className="no-data-state">
          <div className="icon">⏳</div>
          <p>Loading Meridian store configuration...</p>
        </div>
      ) : (
        <div className="settings-container">
          
          {/* Left Column: Store Metadata + Data Purging */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            
            {/* Store Information Card */}
            <section className="vi-card frosted-glass">
              <div className="vi-card-header">
                <span style={{ fontSize: '1.4rem' }}>📍</span>
                <div>
                  <h2>Store Information</h2>
                  <p>Basic details & localized parameters</p>
                </div>
              </div>

              <form onSubmit={handleSaveStoreInfo} className="vi-live-body">
                <div className="vi-input-group">
                  <label htmlFor="st-name">Store Name *</label>
                  <input
                    id="st-name"
                    type="text"
                    value={storeName}
                    onChange={(e) => setStoreName(e.target.value)}
                    placeholder="e.g. My Flagship Store"
                    className="vi-input"
                  />
                </div>

                <div className="vi-input-group">
                  <label htmlFor="st-address">Address</label>
                  <textarea
                    id="st-address"
                    value={storeAddress}
                    onChange={(e) => setStoreAddress(e.target.value)}
                    placeholder="e.g. 123 Main St, Mumbai, India"
                    className="vi-input"
                    style={{ minHeight: '80px', resize: 'vertical', fontFamily: 'inherit' }}
                  />
                </div>

                <div className="vi-input-group">
                  <label htmlFor="st-phone">Phone Number</label>
                  <input
                    id="st-phone"
                    type="text"
                    value={storePhone}
                    onChange={(e) => setStorePhone(e.target.value)}
                    placeholder="e.g. +91 98765 43210"
                    className="vi-input"
                  />
                </div>

                <div className="vi-input-group">
                  <label htmlFor="st-tz">TimeZone</label>
                  <select
                    id="st-tz"
                    value={storeTimezone}
                    onChange={(e) => setStoreTimezone(e.target.value)}
                    className="premium-select"
                  >
                    <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                    <option value="America/New_York">America/New_York (EST)</option>
                    <option value="Europe/London">Europe/London (GMT)</option>
                    <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
                    <option value="UTC">UTC</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={isSavingStore}
                  className="vi-btn vi-btn-primary"
                  style={{ alignSelf: 'flex-start', marginTop: 8 }}
                >
                  {isSavingStore ? 'Saving Changes...' : 'Save Store Info'}
                </button>
              </form>
            </section>

            {/* Data Management Card */}
            <section className="vi-card frosted-glass" style={{ borderColor: 'rgba(239,68,68,0.2)' }}>
              <div className="vi-card-header">
                <span style={{ fontSize: '1.4rem' }}>🗑️</span>
                <div>
                  <h2>Data Management</h2>
                  <p>Purge analytics logs from storage</p>
                </div>
              </div>

              <div className="vi-live-body" style={{ gap: 14 }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                  Clearing store analytics will permanently delete all visitors, event timelines, daily summaries, 
                  and transaction mappings. Store info, cameras, and zones are preserved. <strong>This action cannot be undone.</strong>
                </p>
                
                <button
                  onClick={() => setIsClearModalOpen(true)}
                  className="vi-btn"
                  style={{
                    alignSelf: 'flex-start',
                    background: 'rgba(239, 68, 68, 0.12)',
                    color: 'var(--color-danger)',
                    border: '1px solid rgba(239, 68, 68, 0.3)'
                  }}
                >
                  Clear All Data
                </button>
              </div>
            </section>
          </div>

          {/* Right Column: Camera Management */}
          <div>
            <section className="vi-card frosted-glass">
              <div className="vi-card-header" style={{ justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: '1.4rem' }}>🎥</span>
                  <div>
                    <h2>Camera Management</h2>
                    <p>{camerasList.length}/6 active video sources</p>
                  </div>
                </div>
                <button
                  onClick={openAddCameraModal}
                  disabled={camerasList.length >= 6}
                  className="vi-btn vi-btn-ghost vi-btn-sm"
                >
                  + Add Camera
                </button>
              </div>

              <div className="vi-live-body">
                {camerasList.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px 10px', color: 'var(--color-text-muted)' }}>
                    <span style={{ fontSize: '2rem', display: 'block', marginBottom: 12 }}>📹</span>
                    <p style={{ fontSize: '0.85rem' }}>No active cameras. Click "+ Add Camera" to onboard your first feed.</p>
                  </div>
                ) : (
                  <div className="cam-grid">
                    {camerasList.map((cam) => {
                      const isEntrance = isEntranceCamera(cam);
                      const warning = isEntrance && camerasZonesCount[cam.id] === 0;

                      return (
                        <div key={cam.id} className="cam-card">
                          <div className="cam-info">
                            <div className="cam-name-line">
                              <span className={`cam-status-dot ${cam.status === 'active' ? 'active' : 'inactive'}`} />
                              {cam.name}
                              {isEntrance && (
                                <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: 'rgba(62,207,142,0.1)', color: 'var(--color-success)', borderRadius: 4, fontWeight: 600 }}>
                                  Entrance
                                </span>
                              )}
                              {warning && (
                                <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: 'rgba(245,158,11,0.15)', color: 'var(--color-warning)', borderRadius: 4, fontWeight: 600 }} title="Entrance feeds require an ENTRY_LINE to count visitors">
                                  ⚠️ No Entry Line
                                </span>
                              )}
                            </div>
                            <div className="cam-meta-line">
                              {cam.camera_type === 'rtsp_stream' && `RTSP: ${cam.rtsp_url}`}
                              {cam.camera_type === 'video_file' && `File: ${cam.video_file_path}`}
                              {cam.camera_type === 'webcam' && `Webcam Device`}
                            </div>
                            <div className="cam-meta-line" style={{ marginTop: 2, display: 'flex', alignItems: 'center', gap: 12 }}>
                              <span>Index: {cam.position_index || 'N/A'}</span>
                              <span>Zones: {camerasZonesCount[cam.id] || 0} configured</span>
                            </div>
                          </div>

                          <div className="cam-actions">
                            <button
                              onClick={() => openEditCameraModal(cam)}
                              className="vi-btn vi-btn-ghost vi-btn-sm"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => openZonesConfig(cam)}
                              className="vi-btn vi-btn-ghost vi-btn-sm"
                              style={{ color: 'var(--color-accent)', borderColor: 'rgba(62,207,142,0.2)' }}
                            >
                              Zones
                            </button>
                            <button
                              onClick={() => handleRemoveCamera(cam.id)}
                              className="vi-btn vi-btn-ghost vi-btn-sm"
                              style={{ color: 'var(--color-danger)' }}
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>
          </div>

        </div>
      )}

      {/* ───────────────────────────────────────────────────────────────────────
          MODAL: ADD/EDIT CAMERA
          ─────────────────────────────────────────────────────────────────────── */}
      {isCameraModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsCameraModalOpen(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{cameraModalMode === 'add' ? 'Add New Camera Feed' : 'Edit Camera configurations'}</h3>
              <button className="modal-close-btn" onClick={() => setIsCameraModalOpen(false)}>✕</button>
            </div>
            
            <form onSubmit={handleSaveCamera} className="modal-body">
              <div className="vi-input-group">
                <label>Camera Name *</label>
                <input
                  type="text"
                  value={camFormName}
                  onChange={(e) => setCamFormName(e.target.value)}
                  placeholder="e.g. Store Entry Camera"
                  className="vi-input"
                />
              </div>

              <div className="vi-input-group">
                <label>Source Type</label>
                <select
                  value={camFormType}
                  onChange={(e) => setCamFormType(e.target.value as any)}
                  className="premium-select"
                >
                  <option value="rtsp_stream">RTSP Stream (IP Camera)</option>
                  <option value="video_file">Local Video File (MP4/MKV)</option>
                  <option value="webcam">System Webcam</option>
                </select>
              </div>

              {camFormType === 'rtsp_stream' && (
                <div className="vi-input-group">
                  <label>RTSP URL *</label>
                  <input
                    type="text"
                    value={camFormRtsp}
                    onChange={(e) => setCamFormRtsp(e.target.value)}
                    placeholder="rtsp://admin:password@192.168.1.100:554/stream1"
                    className="vi-input"
                  />
                </div>
              )}

              {camFormType === 'video_file' && (
                <div className="vi-input-group">
                  <label>Local Video File Path *</label>
                  <input
                    type="text"
                    value={camFormFilePath}
                    onChange={(e) => setCamFormFilePath(e.target.value)}
                    placeholder="e.g. C:/Users/Downloads/footage.mp4"
                    className="vi-input"
                  />
                </div>
              )}

              {camFormType === 'webcam' && (
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', fontStyle: 'italic', background: 'var(--color-bg-primary)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}>
                  Webcam mode accesses local video capture index 0. Perfect for development, debugging, and testing overlays.
                </p>
              )}

              <div className="vi-input-group">
                <label>Pipeline Status</label>
                <select
                  value={camFormStatus}
                  onChange={(e) => setCamFormStatus(e.target.value as any)}
                  className="premium-select"
                >
                  <option value="active">Active (Processing enabled)</option>
                  <option value="inactive">Inactive (Suspended)</option>
                </select>
              </div>

              {cameraModalMode === 'edit' && (
                <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Connection Diagnostic</span>
                    <button
                      type="button"
                      onClick={handleTestConnection}
                      disabled={isTestingConn}
                      className="vi-btn vi-btn-ghost vi-btn-sm"
                    >
                      {isTestingConn ? 'Testing Feed...' : 'Test Connection'}
                    </button>
                  </div>
                  {testResult && (
                    <div
                      style={{
                        padding: '10px 12px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.75rem',
                        lineHeight: 1.4,
                        border: '1px solid',
                        background: testResult.success ? 'rgba(62,207,142,0.1)' : 'rgba(239,68,68,0.1)',
                        borderColor: testResult.success ? 'var(--color-success)' : 'var(--color-danger)',
                        color: testResult.success ? 'var(--color-success)' : 'var(--color-danger)'
                      }}
                    >
                      {testResult.message}
                    </div>
                  )}
                </div>
              )}

              <div className="modal-footer">
                <button
                  type="button"
                  onClick={() => setIsCameraModalOpen(false)}
                  className="vi-btn vi-btn-ghost"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingCamera}
                  className="vi-btn vi-btn-primary"
                >
                  {isSavingCamera ? 'Saving...' : 'Save Camera'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────────────────
          MODAL: CONFIGURE CAMERA ZONES
          ─────────────────────────────────────────────────────────────────────── */}
      {isZonesModalOpen && selectedCamera && (
        <div className="modal-backdrop" onClick={() => setIsZonesModalOpen(false)}>
          <div className="modal-box modal-box-large" onClick={(e) => e.stopPropagation()} style={{ display: 'flex', flexDirection: 'column' }}>
            
            <div className="modal-header">
              <div>
                <h3>Configure Zones — {selectedCamera.name}</h3>
                <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                  Draw spatial boundaries. Click coordinates on snapshot feed below.
                </p>
              </div>
              <button className="modal-close-btn" onClick={() => setIsZonesModalOpen(false)}>✕</button>
            </div>

            <div className="modal-body" style={{ flex: 1, minHeight: 0 }}>
              
              {cameraWarning && (
                <div className="warning-banner" style={{ marginBottom: 4 }}>
                  {cameraWarning}
                </div>
              )}

              <div className="canvas-workspace">
                
                {/* Visual Canvas Panel */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  
                  {/* Drawing Mode Selector Toolbar */}
                  <div className="canvas-toolbar">
                    <button
                      onClick={() => { setDrawingMode('select'); setPolygonPoints([]); }}
                      className={`toolbar-btn ${drawingMode === 'select' ? 'active' : ''}`}
                    >
                      <span>🔍</span> Select/Highlight
                    </button>
                    <button
                      onClick={() => { setDrawingMode('polygon'); setPolygonPoints([]); }}
                      className={`toolbar-btn ${drawingMode === 'polygon' ? 'active' : ''}`}
                    >
                      <span>⬡</span> Draw Polygon
                    </button>
                    <button
                      onClick={() => { setDrawingMode('line'); setPolygonPoints([]); }}
                      className={`toolbar-btn ${drawingMode === 'line' ? 'active' : ''}`}
                    >
                      <span>╱</span> Draw Entry Line
                    </button>
                  </div>

                  {/* Canvas Container */}
                  <div
                    style={{
                      position: 'relative',
                      width: '100%',
                      background: '#040711',
                      border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-md)',
                      overflow: 'hidden'
                    }}
                  >
                    <img
                      ref={imageRef}
                      src={`${API_BASE}/cameras/${selectedCamera.id}/snapshot?t=${cacheBuster}`}
                      alt="Camera Frame Background"
                      onLoad={handleImageLoad}
                      className="w-full h-auto block"
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    />
                    
                    {canvasSize.width > 0 && (
                      <canvas
                        ref={canvasRef}
                        width={canvasSize.width}
                        height={canvasSize.height}
                        onClick={handleCanvasClick}
                        onMouseMove={handleCanvasMouseMove}
                        className="absolute top-0 left-0 w-full h-full cursor-crosshair"
                      />
                    )}
                  </div>

                  {drawingMode === 'polygon' && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                        Placed: {polygonPoints.length} vertices (min 3 to close). Click first vertex point to close.
                      </span>
                      {polygonPoints.length >= 3 && (
                        <button
                          onClick={() => handleSaveNewZone(polygonPoints)}
                          disabled={isSavingZone}
                          className="vi-btn vi-btn-ghost vi-btn-sm"
                          style={{ color: 'var(--color-accent)', borderColor: 'rgba(62,207,142,0.2)' }}
                        >
                          Complete Polygon
                        </button>
                      )}
                    </div>
                  )}

                  {drawingMode === 'line' && (
                    <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                      {polygonPoints.length === 0 ? "Click to set Start point." : "Click to set End point. Will auto-convert to a thin rectangle region."}
                    </span>
                  )}
                  
                  {drawingMode === 'select' && (
                    <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                      Click on canvas to highlight a zone and inspect its properties.
                    </span>
                  )}
                </div>

                {/* Zones Info Panel */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  
                  {/* Zone list scroll area */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Configured Zones</span>
                    <div className="zone-list-scroll">
                      {cameraZones.length === 0 ? (
                        <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontStyle: 'italic', padding: '16px 0', textAlign: 'center' }}>
                          No zones defined on this camera yet. Choose a drawing tool.
                        </div>
                      ) : (
                        cameraZones.map((zone) => (
                          <div
                            key={zone.id}
                            onClick={() => { setDrawingMode('select'); setSelectedZoneId(zone.id); }}
                            className={`zone-item ${zone.id === selectedZoneId ? 'selected' : ''}`}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ width: 8, height: 8, borderRadius: '50%', background: ZONE_COLORS[zone.zone_type] }} />
                              <div>
                                <div style={{ fontSize: '0.85rem', fontWeight: 500 }}>{zone.name}</div>
                                <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
                                  {zone.zone_type} {zone.product_category ? `(${zone.product_category})` : ''}
                                </div>
                              </div>
                            </div>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDeleteZone(zone.id); }}
                              style={{ background: 'none', border: 'none', color: 'var(--color-danger)', cursor: 'pointer', fontSize: '0.9rem' }}
                            >
                              ✕
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Add zone setup (when drawing tool is selected) */}
                  {drawingMode !== 'select' && (
                    <div style={{ background: 'var(--color-bg-primary)', padding: 14, borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>New Zone Details</span>
                      
                      <div className="vi-input-group">
                        <label>Zone Name (Optional)</label>
                        <input
                          type="text"
                          value={zoneFormName}
                          onChange={(e) => setZoneFormName(e.target.value)}
                          placeholder="e.g. Makeup Counter A"
                          className="vi-input"
                          style={{ padding: '6px 10px', fontSize: '0.85rem' }}
                        />
                      </div>

                      {drawingMode === 'polygon' && (
                        <div className="vi-input-group">
                          <label>Zone Type</label>
                          <select
                            value={zoneFormType}
                            onChange={(e) => setZoneFormType(e.target.value as any)}
                            className="premium-select"
                            style={{ padding: '6px 10px', fontSize: '0.85rem' }}
                          >
                            <option value="DISPLAY">DISPLAY (Dwell engagement)</option>
                            <option value="AISLE">AISLE (Foot traffic flow)</option>
                            <option value="QUEUE">QUEUE (Queue tracking)</option>
                          </select>
                        </div>
                      )}

                      {drawingMode === 'polygon' && zoneFormType === 'DISPLAY' && (
                        <div className="vi-input-group">
                          <label>Product Category (for KPI mappings)</label>
                          <input
                            type="text"
                            value={zoneFormCategory}
                            onChange={(e) => setZoneFormCategory(e.target.value)}
                            placeholder="e.g. makeup, skincare"
                            className="vi-input"
                            style={{ padding: '6px 10px', fontSize: '0.85rem' }}
                          />
                        </div>
                      )}

                      {drawingMode === 'line' && (
                        <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                          <strong>Type:</strong> ENTRY_LINE. Used by counting logic to monitor entering/exiting visitors.
                        </p>
                      )}
                    </div>
                  )}

                  {/* Selected zone details (when select mode is highlighted) */}
                  {drawingMode === 'select' && selectedZoneId && (
                    (() => {
                      const zone = cameraZones.find(z => z.id === selectedZoneId);
                      if (!zone) return null;
                      return (
                        <div style={{ background: 'var(--color-bg-primary)', padding: 14, borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: 8, fontSize: '0.8rem' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-secondary)', borderBottom: '1px solid var(--color-border)', paddingBottom: 6 }}>
                            Zone Properties
                          </span>
                          <div><strong>Name:</strong> {zone.name}</div>
                          <div><strong>Type:</strong> {zone.zone_type}</div>
                          {zone.product_category && <div><strong>Category:</strong> {zone.product_category}</div>}
                          <div><strong>Vertices:</strong> {zone.polygon.points.length} coordinates</div>
                          <button
                            onClick={() => handleDeleteZone(zone.id)}
                            className="vi-btn"
                            style={{
                              marginTop: 8,
                              background: 'rgba(239, 68, 68, 0.12)',
                              color: 'var(--color-danger)',
                              border: '1px solid rgba(239, 68, 68, 0.3)',
                              padding: '6px 12px',
                              fontSize: '0.78rem'
                            }}
                          >
                            Delete Zone
                          </button>
                        </div>
                      );
                    })()
                  )}

                </div>

              </div>

            </div>

            <div className="modal-footer">
              <button
                type="button"
                onClick={() => setIsZonesModalOpen(false)}
                className="vi-btn vi-btn-primary"
              >
                Close Configurations
              </button>
            </div>

          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────────────────
          MODAL: CLEAR ALL DATA CONFIRMATION
          ─────────────────────────────────────────────────────────────────────── */}
      {isClearModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsClearModalOpen(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header" style={{ borderBottomColor: 'rgba(239,68,68,0.2)' }}>
              <h3 style={{ color: 'var(--color-danger)' }}>Clear Store Analytics</h3>
              <button className="modal-close-btn" onClick={() => setIsClearModalOpen(false)}>✕</button>
            </div>

            <div className="modal-body">
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                This is a highly destructive system operation. ALL historical visitor logs, conversions, hourly trends,
                heatmap tracking, and billing statistics will be deleted from the database. Store details and camera zones remain.
              </p>
              <div className="vi-input-group" style={{ marginTop: 8 }}>
                <label style={{ color: 'var(--color-danger)', fontWeight: 600 }}>
                  To confirm, type "DELETE" in the input below:
                </label>
                <input
                  type="text"
                  value={clearConfirmInput}
                  onChange={(e) => setClearConfirmInput(e.target.value)}
                  placeholder="DELETE"
                  className="vi-input"
                  style={{ borderColor: 'rgba(239,68,68,0.3)', color: 'var(--color-danger)' }}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                onClick={() => { setIsClearModalOpen(false); setClearConfirmInput(''); }}
                className="vi-btn vi-btn-ghost"
              >
                Cancel
              </button>
              <button
                onClick={handleClearData}
                disabled={clearConfirmInput !== 'DELETE' || isClearingData}
                className="vi-btn"
                style={{
                  background: clearConfirmInput === 'DELETE' ? 'var(--color-danger)' : 'rgba(239, 68, 68, 0.4)',
                  color: '#ffffff',
                  border: 'none',
                  cursor: clearConfirmInput === 'DELETE' ? 'pointer' : 'not-allowed'
                }}
              >
                {isClearingData ? 'Purging logs...' : 'I understand, delete data'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default StoreManagementPage;
