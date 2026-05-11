import React, { useEffect, useReducer, useState } from 'react';
import { X } from 'lucide-react';
import { fetchStrategies } from '../api/positionsClient.js';

const MARKETS = [
  { value: 'US', label: '미국 (US)' },
  { value: 'KR', label: '한국 (KR)' },
];

function initForm(position) {
  if (!position) {
    return { ticker: '', market: 'US', name: '', strategy: '', params: {}, budget: '', enabled: true };
  }
  return {
    ticker: position.ticker || '',
    market: position.market || 'US',
    name: position.name || '',
    strategy: position.strategy || '',
    params: { ...(position.params || {}) },
    budget: String(position.budget ?? ''),
    enabled: position.enabled !== false,
  };
}

function buildDefaultParams(schema) {
  const result = {};
  for (const [key, def] of Object.entries(schema || {})) {
    result[key] = def.default ?? '';
  }
  return result;
}

function formReducer(state, action) {
  switch (action.type) {
    case 'set':
      return { ...state, [action.field]: action.value };
    case 'setParam':
      return { ...state, params: { ...state.params, [action.key]: action.value } };
    case 'setStrategy':
      return { ...state, strategy: action.name, params: action.defaults };
    default:
      return state;
  }
}

function ParamField({ fieldKey, schema, value, onChange }) {
  const { type, label, min, max } = schema;
  const step = type === 'int' ? 1 : 0.001;

  if (type === 'bool') {
    return (
      <div className="form-group form-group-inline">
        <label className="form-checkbox-label">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(e.target.checked)}
          />
          <span>{label || fieldKey}</span>
        </label>
      </div>
    );
  }

  return (
    <div className="form-group">
      <label className="form-label">{label || fieldKey}</label>
      <input
        className="form-input"
        type="number"
        value={value ?? ''}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const raw = e.target.value;
          onChange(type === 'int' ? (raw === '' ? '' : parseInt(raw, 10)) : (raw === '' ? '' : parseFloat(raw)));
        }}
      />
    </div>
  );
}

export default function PositionFormModal({ mode, position, onSave, onClose }) {
  const [form, dispatch] = useReducer(formReducer, position, initForm);
  const [strategies, setStrategies] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const isEdit = mode === 'edit';

  useEffect(() => {
    fetchStrategies()
      .then((list) => {
        setStrategies(Array.isArray(list) ? list : []);
        if (!isEdit && !form.strategy && list.length > 0) {
          const first = list[0];
          dispatch({ type: 'setStrategy', name: first.name, defaults: buildDefaultParams(first.params_schema) });
        }
      })
      .catch(() => {});
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const selectedStrategy = strategies.find((s) => s.name === form.strategy);

  function handleStrategyChange(e) {
    const name = e.target.value;
    const strat = strategies.find((s) => s.name === name);
    dispatch({ type: 'setStrategy', name, defaults: buildDefaultParams(strat?.params_schema) });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.ticker.trim()) { setError('종목 코드를 입력하세요.'); return; }
    if (!form.strategy) { setError('전략을 선택하세요.'); return; }
    const budget = parseFloat(form.budget);
    if (Number.isNaN(budget) || budget <= 0) { setError('예산은 0보다 큰 숫자여야 합니다.'); return; }

    setSaving(true);
    setError('');
    try {
      await onSave({
        ticker: form.ticker.trim().toUpperCase(),
        market: form.market,
        name: form.name.trim() || null,
        strategy: form.strategy,
        params: form.params,
        budget,
        enabled: form.enabled,
      });
    } catch (err) {
      setError(err.message || '저장 실패');
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{isEdit ? '종목 수정' : '종목 추가'}</h2>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="닫기">
            <X size={16} />
          </button>
        </div>

        <form className="modal-body" onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group form-group-grow">
              <label className="form-label">종목 코드 *</label>
              <input
                className="form-input"
                type="text"
                value={form.ticker}
                onChange={(e) => dispatch({ type: 'set', field: 'ticker', value: e.target.value })}
                placeholder="TQQQ, 005930"
                autoFocus={!isEdit}
                disabled={isEdit}
              />
            </div>
            <div className="form-group">
              <label className="form-label">시장 *</label>
              <select
                className="form-input form-select"
                value={form.market}
                onChange={(e) => dispatch({ type: 'set', field: 'market', value: e.target.value })}
                disabled={isEdit}
              >
                {MARKETS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">표시 이름</label>
            <input
              className="form-input"
              type="text"
              value={form.name}
              onChange={(e) => dispatch({ type: 'set', field: 'name', value: e.target.value })}
              placeholder="대시보드에 표시될 이름 (선택)"
            />
          </div>

          <div className="form-group">
            <label className="form-label">전략 *</label>
            <select
              className="form-input form-select"
              value={form.strategy}
              onChange={handleStrategyChange}
            >
              <option value="">전략 선택…</option>
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>{s.display_name || s.name}</option>
              ))}
            </select>
          </div>

          {selectedStrategy && Object.keys(selectedStrategy.params_schema || {}).length > 0 && (
            <div className="form-params-section">
              <div className="form-section-title">전략 파라미터</div>
              {Object.entries(selectedStrategy.params_schema).map(([key, schema]) => (
                <ParamField
                  key={key}
                  fieldKey={key}
                  schema={schema}
                  value={form.params[key] ?? schema.default}
                  onChange={(val) => dispatch({ type: 'setParam', key, value: val })}
                />
              ))}
            </div>
          )}

          <div className="form-row">
            <div className="form-group form-group-grow">
              <label className="form-label">예산 ($) *</label>
              <input
                className="form-input"
                type="number"
                value={form.budget}
                min={0}
                step={0.01}
                onChange={(e) => dispatch({ type: 'set', field: 'budget', value: e.target.value })}
                placeholder="0.00"
              />
            </div>
            <div className="form-group form-group-inline form-group-center">
              <label className="form-checkbox-label">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => dispatch({ type: 'set', field: 'enabled', value: e.target.checked })}
                />
                <span>활성화</span>
              </label>
            </div>
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="modal-footer">
            <button type="button" className="modal-btn modal-btn-cancel" onClick={onClose}>
              취소
            </button>
            <button type="submit" className="modal-btn modal-btn-save" disabled={saving}>
              {saving ? '저장 중…' : '저장'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
