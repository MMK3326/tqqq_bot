import React, { useMemo } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import Panel from './Panel';
import { formatMoney, formatPercent, formatPrice, formatSignedPercent, formatUnit, getStatusClass, getValueClass, safeDisplay } from '../data/symbolRows.js';

const TEXT = {
  title: '종목별 운용 현황',
  subtitle: '보유 및 운용 중인 종목 리스트',
  countSuffix: '개 종목',
  addSymbol: '+ 종목 추가',
  symbol: '종목',
  status: '상태',
  currentPrice: '현재가',
  initialEntryPrice: '초기 진입가',
  returnRate: '수익률',
  unrealizedPnl: '평가손익',
  allocation: '비중',
  investedUnit: '투입 Unit',
  nextBuy: '다음 매수',
  nextTakeProfit: '다음 익절',
  action: '액션',
  empty: '운용 중인 종목이 없습니다. 종목 추가 버튼을 눌러 시작하세요.',
  detail: '상세',
  edit: '수정',
  delete: '삭제',
  guide: '* 행을 클릭하면 상세 정보가 표시됩니다.',
  disabled: '비활성',
};

export default function SymbolOperationsTable({
  symbols,
  selectedSymbol,
  onSelectSymbol,
  positions,
  onAdd,
  onEdit,
  onDelete,
  onToggleEnabled,
}) {
  const rows = Array.isArray(symbols) ? symbols : [];

  const positionMap = useMemo(() => {
    const map = {};
    if (Array.isArray(positions)) {
      positions.forEach((p) => { map[p.ticker] = p; });
    }
    return map;
  }, [positions]);

  function handleDelete(e, ticker) {
    e.stopPropagation();
    const pos = positionMap[ticker];
    if (!pos) return;
    if (globalThis.confirm(`"${ticker}" 종목을 삭제하면 모든 주문 이력도 삭제됩니다.\n계속하시겠습니까?`)) {
      onDelete?.(pos);
    }
  }

  function handleEdit(e, ticker) {
    e.stopPropagation();
    const pos = positionMap[ticker];
    if (pos) onEdit?.(pos);
  }

  function handleToggle(e, ticker) {
    e.stopPropagation();
    const pos = positionMap[ticker];
    if (pos) onToggleEnabled?.(pos);
  }

  return (
    <Panel
      title={TEXT.title}
      subtitle={TEXT.subtitle}
      className="symbol-table-panel"
      headerActions={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="panel-count">{rows.length}{TEXT.countSuffix}</span>
          <button type="button" className="table-add-button" onClick={() => onAdd?.()}>
            <Plus size={12} strokeWidth={2.5} />
            {TEXT.addSymbol}
          </button>
        </div>
      }
    >
      <div className="symbol-table-scroll">
        <table className="data-table symbol-table">
          <thead>
            <tr>
              <th>{TEXT.symbol}</th>
              <th>{TEXT.status}</th>
              <th className="align-right">{TEXT.currentPrice}</th>
              <th className="align-right">{TEXT.initialEntryPrice}</th>
              <th className="align-right">{TEXT.returnRate}</th>
              <th className="align-right">{TEXT.unrealizedPnl}</th>
              <th className="align-right">{TEXT.allocation}</th>
              <th className="align-right">{TEXT.investedUnit}</th>
              <th className="align-right">{TEXT.nextBuy}</th>
              <th className="align-right">{TEXT.nextTakeProfit}</th>
              <th className="align-right">{TEXT.action}</th>
            </tr>
          </thead>
          <tbody>
            {!rows.length ? (
              <tr>
                <td colSpan={11} className="empty-table-cell">{TEXT.empty}</td>
              </tr>
            ) : rows.map((row) => {
              const pos = positionMap[row.symbol];
              const isDisabled = pos && !pos.enabled;
              return (
                <tr
                  key={row.symbol}
                  className={`${selectedSymbol === row.symbol ? 'selected-row' : ''} ${isDisabled ? 'row-disabled' : ''}`}
                  onClick={() => onSelectSymbol?.(row.symbol)}
                >
                  <td>
                    <div className="symbol-name-cell">
                      <strong>{row.symbol}</strong>
                      <span>{row.name || row.description || '-'}</span>
                    </div>
                  </td>
                  <td>
                    {isDisabled ? (
                      <span className="state-pill state-waiting">{TEXT.disabled}</span>
                    ) : (
                      <span className={`state-pill ${getStatusClass(row.status)}`}>{safeDisplay(row.status)}</span>
                    )}
                  </td>
                  <td className="align-right numeric-cell">{formatPrice(row.currentPrice)}</td>
                  <td className="align-right numeric-cell tone-blue">{formatPrice(row.initialEntryPrice ?? row.firstPrice)}</td>
                  <td className={`align-right numeric-cell ${getValueClass(row.returnRate)}`}>{formatSignedPercent(row.returnRate)}</td>
                  <td className={`align-right numeric-cell ${getValueClass(row.unrealizedPnl)}`}>{formatMoney(row.unrealizedPnl)}</td>
                  <td className="align-right numeric-cell">{formatPercent(row.allocation)}</td>
                  <td className="align-right">
                    <span className="state-pill state-buy">{formatUnit(row.investedUnit ?? row.stage)}</span>
                  </td>
                  <td className="align-right numeric-cell tone-yellow">
                    {formatPrice(row.nextBuyPrice)}
                    <span className="rate-note">{formatSignedPercent(row.nextBuyRate)}</span>
                  </td>
                  <td className="align-right numeric-cell tone-green">
                    {formatPrice(row.nextTakeProfitPrice)}
                    <span className="rate-note">{formatSignedPercent(row.nextTakeProfitRate)}</span>
                  </td>
                  <td className="align-right">
                    <div className="table-action-group">
                      {pos && (
                        <button
                          type="button"
                          className={`table-toggle-button ${pos.enabled ? 'enabled' : 'disabled-state'}`}
                          title={pos.enabled ? '비활성화' : '활성화'}
                          onClick={(e) => handleToggle(e, row.symbol)}
                        >
                          {pos.enabled ? 'ON' : 'OFF'}
                        </button>
                      )}
                      <button
                        type="button"
                        className="table-icon-button"
                        title={TEXT.edit}
                        onClick={(e) => handleEdit(e, row.symbol)}
                      >
                        <Pencil size={13} strokeWidth={2} />
                      </button>
                      <button
                        type="button"
                        className="table-icon-button table-icon-delete"
                        title={TEXT.delete}
                        onClick={(e) => handleDelete(e, row.symbol)}
                      >
                        <Trash2 size={13} strokeWidth={2} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="table-guide">{TEXT.guide}</div>
    </Panel>
  );
}
