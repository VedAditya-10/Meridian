import React from 'react';

interface PageHeaderProps {
  title: string;
  subtitle: string;
}

/**
 * Reusable page header with a title and subtitle line.
 */
export const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle }) => (
  <div className="page-header">
    <h2 className="page-title">{title}</h2>
    <p className="page-subtitle">{subtitle}</p>
  </div>
);
