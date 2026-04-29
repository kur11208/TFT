import React from "react";
import type { Unit } from "../types";

interface Props {
  label: string;
  units: Unit[];
  onChange: (units: Unit[]) => void;
}

const STAR_OPTIONS = [1, 2, 3];

export function UnitListInput({ label, units, onChange }: Props) {
  const addUnit = () => {
    onChange([...units, { name: "", stars: 1, tags: [], items: [] }]);
  };

  const removeUnit = (idx: number) => {
    onChange(units.filter((_, i) => i !== idx));
  };

  const updateUnit = (idx: number, field: keyof Unit, value: string | number | string[]) => {
    const updated = units.map((unit, i) => {
      if (i !== idx) return unit;
      if (field === "tags") {
        return {
          ...unit,
          tags: (value as string).split(",").map((tag) => tag.trim()).filter(Boolean),
        };
      }
      return { ...unit, [field]: value };
    });
    onChange(updated);
  };

  return (
    <div className="unit-list-input">
      <div className="unit-list-header">
        <span className="field-label">{label}</span>
        <button type="button" className="btn-small btn-add" onClick={addUnit}>
          + 追加
        </button>
      </div>
      {units.length === 0 && <p className="empty-hint">ユニット未入力</p>}
      {units.map((unit, idx) => (
        <div key={idx} className="unit-row">
          <input
            type="text"
            className="unit-name"
            placeholder="ユニット名"
            value={unit.name}
            onChange={(e) => updateUnit(idx, "name", e.target.value)}
          />
          <select
            className="unit-stars"
            value={unit.stars}
            onChange={(e) => updateUnit(idx, "stars", Number(e.target.value))}
          >
            {STAR_OPTIONS.map((stars) => (
              <option key={stars} value={stars}>
                {"★".repeat(stars)}
              </option>
            ))}
          </select>
          <input
            type="text"
            className="unit-tags"
            placeholder="タグをカンマ区切りで入力"
            value={unit.tags.join(", ")}
            onChange={(e) => updateUnit(idx, "tags", e.target.value)}
          />
          <button type="button" className="btn-small btn-remove" onClick={() => removeUnit(idx)}>
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
