"""
History Manager - Lưu trữ & Quản lý lịch sử các lần chạy demo DSS
Lưu trữ dưới dạng file JSON cục bộ trong web/data/history.json
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"


class HistoryManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not HISTORY_FILE.exists():
            self._save_raw([])

    def _load_raw(self) -> List[Dict[str, Any]]:
        try:
            if not HISTORY_FILE.exists():
                return []
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_raw(self, items: List[Dict[str, Any]]):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def save_run(self, results: Dict[str, Any], raw_inputs: List[Dict[str, Any]]) -> str:
        """Lưu một lần chạy phân tích mới vào lịch sử."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        top_details = results.get("top_machine_details", {}) or {}
        
        record = {
            "run_id": run_id,
            "created_at": now_str,
            "timestamp": datetime.now().isoformat(),
            "total_machines": results.get("total_machines", len(raw_inputs)),
            "counts": results.get("counts", {}),
            "top_priority_machine": results.get("top_priority_machine", "N/A"),
            "top_machine_risk": top_details.get("risk_level", "NORMAL"),
            "top_machine_score": top_details.get("topsis_score", 0.0),
            "inputs": raw_inputs,
            "results": results,
        }

        all_records = self._load_raw()
        # Thêm mới nhất lên đầu danh sách
        all_records.insert(0, record)
        # Giữ tối đa 100 lần chạy gần nhất
        all_records = all_records[:100]
        self._save_raw(all_records)
        return run_id

    def get_all_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách tóm tắt các lần chạy."""
        all_records = self._load_raw()
        summaries = []
        for r in all_records[:limit]:
            summaries.append({
                "run_id": r["run_id"],
                "created_at": r["created_at"],
                "total_machines": r["total_machines"],
                "counts": r["counts"],
                "top_priority_machine": r["top_priority_machine"],
                "top_machine_risk": r["top_machine_risk"],
                "top_machine_score": r["top_machine_score"]
            })
        return summaries

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết đầy đủ của một lần chạy."""
        all_records = self._load_raw()
        for r in all_records:
            if r["run_id"] == run_id:
                return r
        return None

    def delete_run(self, run_id: str) -> bool:
        """Xoá một lần chạy."""
        all_records = self._load_raw()
        initial_len = len(all_records)
        all_records = [r for r in all_records if r["run_id"] != run_id]
        if len(all_records) < initial_len:
            self._save_raw(all_records)
            return True
        return False

    def clear_all(self):
        """Xoá toàn bộ lịch sử."""
        self._save_raw([])


# Singleton history manager
_history_instance: Optional[HistoryManager] = None

def get_history_manager() -> HistoryManager:
    global _history_instance
    if _history_instance is None:
        _history_instance = HistoryManager()
    return _history_instance
