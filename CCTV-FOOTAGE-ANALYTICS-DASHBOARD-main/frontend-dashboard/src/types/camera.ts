export interface CameraStatus {
  status: 'IDLE' | 'PROCESSING' | 'COMPLETE' | 'ERROR';
  progress: number;
}

export interface Detection {
  id: string;
  top: string;
  left: string;
  width: string;
  height: string;
  timestamp: number;
}
