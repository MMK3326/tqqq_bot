import React from 'react';

export default function Panel({ title, subtitle, children, className = '', headerActions = null }) {
  return (
    <section className={`panel ${className}`.trim()}>
      <header className="panel-header">
        <div className="panel-heading">
          <h2>{title}</h2>
          {subtitle ? <span className="panel-subtitle">{subtitle}</span> : null}
        </div>
        {headerActions ? <div className="panel-actions">{headerActions}</div> : null}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}
