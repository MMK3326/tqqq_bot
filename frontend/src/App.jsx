import React, { useEffect, useMemo, useState } from 'react';
import Toolbar from './components/Toolbar';
import PortfolioSummaryPanel from './components/PortfolioSummaryPanel';
import SymbolOperationsTable from './components/SymbolOperationsTable';
import SymbolDetailCard from './components/SymbolDetailCard';
import PerformanceKpiStrip from './components/PerformanceKpiStrip';
import HistoryPanel from './components/HistoryPanel';
import { useDashboardData } from './hooks/useDashboardData';
import { controlClose, controlPause, controlRefresh, controlRunOnce, controlStart } from './api/controlClient.js';
import { buildSymbolRows } from './data/symbolRows.js';

export default function App() {
  const [activeTab, setActiveTab] = useState('trades');
  const [selectedSymbol, setSelectedSymbol] = useState('TQQQ');
  const [busyAction, setBusyAction] = useState(null);
  const { data, applyControlResult } = useDashboardData();
  const symbolRows = useMemo(() => buildSymbolRows(data), [data]);
  const selectedSymbolData = symbolRows.find((row) => row.symbol === selectedSymbol) || symbolRows[0] || null;

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
        case 'start':
          result = await controlStart();
          break;
        case 'pause':
          result = await controlPause();
          break;
        case 'run-once':
          result = await controlRunOnce();
          break;
        case 'refresh':
          result = await controlRefresh();
          break;
        case 'close':
          result = await controlClose();
          break;
        default:
          return;
      }

      applyControlResult(result);
    } finally {
      setBusyAction(null);
    }
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
    </div>
  );
}
