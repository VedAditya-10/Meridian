import React from 'react';
import { ANOMALY_META } from '../../constants';
import type { Anomaly } from '../../types';

interface AnomalyCardProps {
  anomaly: Anomaly;
  index: number;
}

/**
 * Single anomaly card with severity styling, icon, title, message,
 * and a detection timestamp.
 */
export const AnomalyCard: React.FC<AnomalyCardProps> = ({ anomaly, index }) => {
  const meta = ANOMALY_META[anomaly.type] ?? { icon: '⚡', title: anomaly.type };
  const sev  = anomaly.severity?.toLowerCase() as 'high' | 'medium' | 'low';
  const now  = new Date().toLocaleTimeString();

  return (
    <div className={`anomaly-card ${sev}`} id={`anomaly-${index}`}>
      <div className="anomaly-icon">{meta.icon}</div>
      <div className="anomaly-content">
        <div className="anomaly-title">{meta.title}</div>
        <div className="anomaly-message">{anomaly.message}</div>
        <div className="anomaly-meta">
          <span className={`severity-badge ${sev}`}>{anomaly.severity}</span>
          <span className="anomaly-time">Detected at {now}</span>
        </div>
      </div>
    </div>
  );
};
