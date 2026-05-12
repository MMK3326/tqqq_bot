import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Toolbar from './components/Toolbar';
import PortfolioSummaryPanel from './components/PortfolioSummaryPanel';
import SymbolOperationsTable from './components/SymbolOperationsTable';
import SymbolDetailCard from './components/SymbolDetailCard';
import PerformanceKpiStrip from './components/PerformanceKpiStrip';
import HistoryPanel from './components/HistoryPanel';
import PositionFormModal from './components/PositionFormModal';
import { useDashboardData } from './hooks/useDashboardData';
import {
  controlClose,
  controlKillSwitch,
  controlKillSwitchReset,
  controlPause,
  controlRefresh,
  controlRunOnce,
  controlStart,
} from './api/controlClient.js';
import { createPosition, deletePosition, fetchPositions, updatePosition } from './api/positionsClient.js';
import { buildSymbolRows } from './data/symbolRows.js';

export default function App() {
  const [activeTab, setActiveTab] = useState('trades');
  const [selectedSymbol, setSelectedSymbol] = useState('TQQQ');
  const [busyAction, setBusyAction] = useState(null);
  const { data, applyControlResult, refreshDashboard } = useDashboardData();
  const symbolRows = useMemo(() => buildSymbolRows(data), [data]);
  const selectedSymbolData = symbolRows.find((row) => row.symbol === selectedSymbol) || symbolRows[0] || null;

  const [positions, setPositions] = useState([]);
  const [posModal, setPosModal] = useState(null); // null | { mode: 'add' | 'edit', position: {...} | null }

  const loadPositions = useCallback(() => {
    fetchPositions().then(setPositions).catch(() => {});
  }, []);

  useEffect(() => {
    loadPositions();
  }, [loadPositions]);

  useEffect(() => {
    if (!symbolRows.length) return;
    const hasSelected = symbolRows.some((row) => row.symbol === selectedSymbol);
    if (!hasSelected) {
      const tqqq = symbolRows.find((row) => row.symbol === 'TQQQ');
      setSelectedSymbol((tqqq || symbolRows[0]).symbol);
    }
  }, [selectedSymbol, symbolRows]);

  const handleAction = async (action) => {
    if (busyAction) return;
    setBusyAction(action);

    try {
      let result = null;
      switch (action) {
        case 'start':       result = await controlStart(); break;
        case 'pause':       result = await controlPause(); break;
        case 'run-once':    result = await controlRunOnce(); break;
        case 'refresh':     result = await controlRefresh(); break;
        case 'close':       result = await controlClose(); break;
        case 'kill-switch': result = await controlKillSwitch(); break;
        case 'kill-switch-reset': result = await controlKillSwitchReset(); break;
        default: return;
      }
      if (result) applyControlResult(result);
    } finally {
      setBusyAction(null);
    }
  };

  const handlePositionSaved = async (formData) => {
    if (posModal?.mode === 'edit' && posModal.position) {
      await updatePosition(posModal.position.id, formData);
    } else {
      await createPosition(formData);
    }
    setPosModal(null);
    loadPositions();
    refreshDashboard();
  };

  const handleDelete = async (pos) => {
    await deletePosition(pos.id);
    loadPositions();
    refreshDashboard();
  };

  const handleToggleEnabled = async (pos) => {
    await updatePosition(pos.id, { enabled: !pos.enabled });
    loadPositions();
    refreshDashboard();
  };

  return (
    <div className="app-shell">
      <Toolbar data={data} onAction={handleAction} busyAction={busyAction} />

      <main className="operations-layout">
        <aside className="portfolio-column">
          <PortfolioSummaryPanel data={data} />
        </aside>

        <div className="operations-column">
          <SymbolOperationsTable
            symbols={symbolRows}
            selectedSymbol={selectedSymbol}
            onSelectSymbol={setSelectedSymbol}
            positions={positions}
            onAdd={() => setPosModal({ mode: 'add', position: null })}
            onEdit={(pos) => setPosModal({ mode: 'edit', position: pos })}
            onDelete={handleDelete}
            onToggleEnabled={handleToggleEnabled}
          />
          <SymbolDetailCard symbol={selectedSymbolData} />
        </div>
      </main>

      <PerformanceKpiStrip rows={data.performanceRows} />

      <HistoryPanel
        activeTab={activeTab}
        onTabChange={setActiveTab}
        tradeTabs={data.tradeTabs}
        trades={data.trades}
        messages={data.messages}
      />

      {posModal && (
        <PositionFormModal
          mode={posModal.mode}
          position={posModal.position}
          onSave={handlePositionSaved}
          onClose={() => setPosModal(null)}
        />
      )}
    </div>
  );
}
