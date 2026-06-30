import React from 'react';
import type { LiveEvent, CameraStatus } from '../../types';

interface EventLogProps {
  events: LiveEvent[];
  processingCamera: [string, CameraStatus] | undefined;
  completedCameras: number;
  totalCameras: number;
}

/**
 * Scrollable live domain-event log with a status badge.
 */
export const EventLog: React.FC<EventLogProps> = ({
  events,
  processingCamera,
  completedCameras,
  totalCameras,
}) => (
  <div className="event-log-section">
    <div className="event-log-header">
      <span className="event-log-title">Live Domain Events</span>
      <div className="live-badge">
        <div
          className={`pulse-indicator ${processingCamera ? 'healthy' : ''}`}
        />
        {processingCamera
          ? 'Streaming'
          : completedCameras === totalCameras
          ? 'Complete'
          : 'Waiting'}
      </div>
    </div>
    <div className="event-log-list" id="event-log">
      {events.length === 0 ? (
        <div
          style={{ padding: '20px', textAlign: 'center', color: 'var(--color-text-muted)' }}
        >
          Awaiting live domain events from the pipeline...
        </div>
      ) : (
        events.map((ev) => (
          <div className="event-log-item" key={ev.id}>
            <span className={`event-type-chip ${ev.event_type}`}>
              {ev.event_type.replace(/_/g, ' ')}
            </span>
            <span className="event-log-detail">{ev.detail}</span>
            <span className="event-log-time">{ev.time}</span>
          </div>
        ))
      )}
    </div>
  </div>
);
