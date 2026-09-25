"""
DSS Engine - Runtime Inference Module
Thực thi toàn bộ quy trình DSS từ Machine Input -> ML Inference -> Calibrated AHP -> TOPSIS -> Decision Engine -> Explainability.
"""

import os
import sys
import json
import joblib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Standard Feature and Criteria Definitions
FEATURE_COLS = ["Type", "Air_temperature_K", "Process_temperature_K",
                "Rotational_speed_rpm", "Torque_Nm", "Tool_wear_min"]

CRITERIA_COLS = ["Failure_Probability", "Tool_wear_min", "Torque_Nm",
                 "Process_temperature_K", "Rotational_speed_rpm", "Air_temperature_K"]

EXPLAIN_LABELS = {
    "Failure_Probability": "Xác suất hỏng hóc dự báo cao (High failure probability)",
    "Tool_wear_min": "Độ mòn dụng cụ cao (High tool wear)",
    "Torque_Nm": "Mô-men xoắn hoạt động cao (High torque)",
    "Process_temperature_K": "Nhiệt độ quy trình gia công cao (High process temp)",
    "Rotational_speed_rpm": "Tốc độ quay bất thường (Rotational speed risk profile)",
    "Air_temperature_K": "Nhiệt độ môi trường tăng cao (Air temp risk profile)",
}

RISK_METADATA = {
    "CRITICAL": {
        "action": "Immediate Maintenance",
        "action_vi": "Bảo trì khẩn cấp ngay lập tức",
        "color": "#DC2626", # Red
        "badge_class": "bg-danger",
        "order": 1
    },
    "HIGH": {
        "action": "Schedule Maintenance",
        "action_vi": "Lập kế hoạch bảo trì sớm",
        "color": "#EA580C", # Orange
        "badge_class": "bg-warning text-dark",
        "order": 2
    },
    "MEDIUM": {
        "action": "Inspection",
        "action_vi": "Kiểm tra / Giám sát định kỳ",
        "color": "#EAB308", # Yellow
        "badge_class": "bg-info text-dark",
        "order": 3
    },
    "NORMAL": {
        "action": "Continue Operation",
        "action_vi": "Tiếp tục vận hành bình thường",
        "color": "#16A34A", # Green
        "badge_class": "bg-success",
        "order": 4
    }
}


@dataclass
class MachineInput:
    machine_id: str
    type: str                   # 'L', 'M', 'H'
    air_temperature: float      # K (~300)
    process_temperature: float  # K (~310)
    rotational_speed: float     # rpm (~1500)
    torque: float               # Nm (~40)
    tool_wear: float            # min (0 - 250)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MachineInput":
        return cls(
            machine_id=str(d.get("machine_id", "M_UNK")).strip(),
            type=str(d.get("type", "L")).strip().upper(),
            air_temperature=float(d.get("air_temperature", 300.0)),
            process_temperature=float(d.get("process_temperature", 310.0)),
            rotational_speed=float(d.get("rotational_speed", 1500.0)),
            torque=float(d.get("torque", 40.0)),
            tool_wear=float(d.get("tool_wear", 0.0)),
        )


class DSSEngine:
    def __init__(self, artifact_dirs: Optional[List[str]] = None):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.candidate_dirs = [
            self.base_dir / "outputnotebook",
            self.base_dir / "output_notebook",
            self.base_dir / "output_notebook" / "dss_artifacts",
            self.base_dir / "dss_artifacts",
            Path("outputnotebook"),
            Path("output_notebook"),
            Path("dss_artifacts"),
        ]
        if artifact_dirs:
            self.candidate_dirs = [Path(p) for p in artifact_dirs] + self.candidate_dirs
        
        self.loaded_artifact_dir: Optional[Path] = None
        self.type_encoder = None
        self.scaler = None
        self.ml_model = None
        self.ahp_weights: Optional[pd.Series] = None
        self.crit_min: Optional[pd.Series] = None
        self.crit_max: Optional[pd.Series] = None
        self.thresholds: Dict[str, Any] = {}
        
        self._load_artifacts()

    def _load_artifacts(self):
        """Tìm và nạp các artifact cần thiết."""
        for cdir in self.candidate_dirs:
            if not cdir.exists():
                continue
            
            p_enc = cdir / "type_encoder.joblib"
            p_scl = cdir / "scaler.joblib"
            p_mod = cdir / "ml_model.joblib"
            p_ahp = cdir / "ahp_weights.json"
            p_cmin = cdir / "criteria_min.json"
            p_cmax = cdir / "criteria_max.json"
            p_thr = cdir / "decision_thresholds.json"
            
            if (p_enc.exists() and p_scl.exists() and p_mod.exists() and 
                p_ahp.exists() and p_cmin.exists() and p_cmax.exists() and p_thr.exists()):
                try:
                    self.type_encoder = joblib.load(p_enc)
                    self.scaler = joblib.load(p_scl)
                    self.ml_model = joblib.load(p_mod)
                    self.ahp_weights = pd.read_json(p_ahp, typ="series")
                    self.crit_min = pd.read_json(p_cmin, typ="series")
                    self.crit_max = pd.read_json(p_cmax, typ="series")
                    with open(p_thr, "r", encoding="utf-8") as f:
                        self.thresholds = json.load(f)
                    
                    self.loaded_artifact_dir = cdir
                    print(f"[DSS Engine] Đã nạp thành công artifacts từ: {cdir.resolve()}")
                    return
                except Exception as e:
                    print(f"[DSS Engine] Thất bại khi nạp từ {cdir}: {e}")
                    continue

        print("[DSS Engine] Cảnh báo: Chưa tìm thấy đủ artifacts. Khởi tạo fallback tự động...")
        from download_output import generate_local_artifacts
        fallback_dir = self.base_dir / "outputnotebook"
        if generate_local_artifacts(fallback_dir):
            self._load_artifacts()
        else:
            raise RuntimeError("Không thể tìm thấy hoặc khởi tạo DSS artifacts.")

    def get_model_info(self) -> Dict[str, Any]:
        """Trả về thông tin metadata của model & DSS."""
        return {
            "artifact_dir": str(self.loaded_artifact_dir.resolve()) if self.loaded_artifact_dir else "None",
            "model_type": self.thresholds.get("final_model", "Random Forest Classifier"),
            "data_source": self.thresholds.get("data_source", "AI4I 2020"),
            "thresholds": {
                "t_medium": float(self.thresholds.get("t_medium", 0.40)),
                "t_high": float(self.thresholds.get("t_high", 0.58)),
                "t_critical": float(self.thresholds.get("t_critical", 0.67)),
            },
            "ahp_weights": self.ahp_weights.to_dict() if self.ahp_weights is not None else {},
            "criteria_cols": CRITERIA_COLS,
            "feature_cols": FEATURE_COLS
        }

    def generate_demo_machines(self, n: int = 10, seed: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Sinh ngẫu nhiên n máy mô phỏng theo phân phối AI4I 2020.
        Gồm cả máy trạng thái bình thường lẫn máy có dấu hiệu rủi ro cao.
        """
        rng = np.random.default_rng(seed)
        machines = []
        for i in range(n):
            t = rng.choice(["L", "M", "H"], p=[0.6, 0.3, 0.1])
            air_t = float(rng.normal(300, 2))
            proc_t = air_t + float(rng.normal(10, 1.2))
            speed = float(rng.normal(1538, 220))
            torque = float(rng.normal(40, 12))
            wear = float(rng.uniform(0, 253))
            
            # Để demo sinh động, tạo một vài máy có nguy cơ cao (độ mòn lớn, torque cao, nhiệt độ cao hoặc tốc độ bất thường)
            if i == 0:
                wear = float(rng.uniform(210, 250))
                torque = float(rng.uniform(62, 75))
            elif i == 1:
                proc_t = air_t + float(rng.uniform(6.0, 8.0)) # Chênh nhiệt độ thấp -> HDF risk
                speed = float(rng.uniform(1200, 1350))
                wear = float(rng.uniform(160, 210))
            elif i == 2:
                torque = float(rng.uniform(65, 76))
                speed = float(rng.uniform(1800, 2200)) # PWF risk
            elif i == 3:
                wear = float(rng.uniform(190, 240))
                torque = float(rng.uniform(50, 65))

            m = {
                "machine_id": f"M{i+1:03d}",
                "type": str(t),
                "air_temperature": round(air_t, 1),
                "process_temperature": round(proc_t, 1),
                "rotational_speed": round(max(speed, 1000), 0),
                "torque": round(max(torque, 3.0), 1),
                "tool_wear": round(max(wear, 0.0), 0)
            }
            machines.append(m)
            
        return machines

    def process_single_machine(self, m: MachineInput) -> Tuple[float, pd.Series]:
        """Chạy pipeline ML cho 1 máy đơn lẻ."""
        raw = pd.DataFrame([{
            "Type": m.type,
            "Air_temperature_K": m.air_temperature,
            "Process_temperature_K": m.process_temperature,
            "Rotational_speed_rpm": m.rotational_speed,
            "Torque_Nm": m.torque,
            "Tool_wear_min": m.tool_wear,
        }])

        enc = raw.copy()
        enc["Type"] = self.type_encoder.transform(raw[["Type"]])
        scaled = pd.DataFrame(self.scaler.transform(enc[FEATURE_COLS]), columns=FEATURE_COLS)

        failure_proba = float(self.ml_model.predict_proba(scaled)[:, 1][0])

        criteria_row = pd.Series({
            "Failure_Probability": failure_proba,
            "Tool_wear_min": m.tool_wear,
            "Torque_Nm": m.torque,
            "Process_temperature_K": m.process_temperature,
            "Rotational_speed_rpm": m.rotational_speed,
            "Air_temperature_K": m.air_temperature,
        })[CRITERIA_COLS]

        return failure_proba, criteria_row

    def minmax_normalize(self, df_crit: pd.DataFrame) -> pd.DataFrame:
        """Min-Max normalization dựa trên tham số fit offline."""
        ref_min = self.crit_min
        ref_max = self.crit_max
        norm = (df_crit - ref_min) / (ref_max - ref_min + 1e-9)
        # Giới hạn về [0, 1] nếu gặp ngoại lai ngoài phân phối
        return norm.clip(0.0, 1.0)

    def calculate_topsis(self, criteria_df: pd.DataFrame) -> pd.Series:
        """Tính TOPSIS score cho toàn bộ tập máy."""
        norm = self.minmax_normalize(criteria_df)
        weights = self.ahp_weights[CRITERIA_COLS]
        weighted = norm.values * weights.values # shape: (n, k)

        pis = weighted.max(axis=0) # Ideal solution (Rủi ro cao nhất)
        nis = weighted.min(axis=0) # Anti-ideal (Rủi ro thấp nhất)

        dist_pos = np.sqrt(((weighted - pis) ** 2).sum(axis=1))
        dist_neg = np.sqrt(((weighted - nis) ** 2).sum(axis=1))

        score = dist_neg / (dist_pos + dist_neg + 1e-12)
        return pd.Series(score, index=criteria_df.index, name="TOPSIS_Score")

    def classify_risk(self, score: float) -> Tuple[str, str, str, str, str]:
        """Phân loại mức độ rủi ro dựa trên ngưỡng calibrated."""
        t_m = float(self.thresholds.get("t_medium", 0.40))
        t_h = float(self.thresholds.get("t_high", 0.58))
        t_c = float(self.thresholds.get("t_critical", 0.67))

        if score >= t_c:
            level = "CRITICAL"
        elif score >= t_h:
            level = "HIGH"
        elif score >= t_m:
            level = "MEDIUM"
        else:
            level = "NORMAL"

        meta = RISK_METADATA[level]
        return level, meta["action"], meta["action_vi"], meta["color"], meta["badge_class"]

    def explain_machine(self, criteria_row: pd.Series, top_k: int = 3) -> List[Dict[str, Any]]:
        """Giải thích các yếu tố đóng góp lớn nhất vào priority score."""
        norm = (criteria_row - self.crit_min) / (self.crit_max - self.crit_min + 1e-9)
        norm = norm.clip(0.0, 1.0)
        contribution = norm * self.ahp_weights[CRITERIA_COLS]
        top_contrib = contribution.sort_values(ascending=False).head(top_k)

        explanations = []
        for col, val in top_contrib.items():
            explanations.append({
                "criterion": col,
                "label": EXPLAIN_LABELS.get(col, col),
                "raw_value": round(float(criteria_row[col]), 2 if col != "Rotational_speed_rpm" else 0),
                "normalized_value": round(float(norm[col]), 3),
                "weight": round(float(self.ahp_weights[col]), 3),
                "contribution_score": round(float(val), 4)
            })
        return explanations

    def evaluate_batch(self, machines_raw: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Đánh giá toàn diện danh sách máy:
        ML inference -> Decision Matrix -> TOPSIS Ranking -> Explanations -> Thống kê.
        """
        if not machines_raw:
            return {"error": "Danh sách máy trống."}

        machine_objs: List[MachineInput] = []
        for i, item in enumerate(machines_raw):
            if not item.get("machine_id"):
                item["machine_id"] = f"M{i+1:03d}"
            machine_objs.append(MachineInput.from_dict(item))

        # 1. Chạy ML và tạo criteria matrix
        proba_list = []
        criteria_rows = []
        for m in machine_objs:
            p, c_row = self.process_single_machine(m)
            proba_list.append(p)
            criteria_rows.append(c_row)

        criteria_df = pd.DataFrame(criteria_rows)
        criteria_df.index = [m.machine_id for m in machine_objs]

        # 2. Tính TOPSIS scores
        topsis_scores = self.calculate_topsis(criteria_df)

        # 3. Chuẩn hóa cho Radar / Bar chart (0-1)
        norm_criteria_df = self.minmax_normalize(criteria_df)

        # 4. Gom kết quả và xếp hạng
        results_list = []
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "NORMAL": 0}

        for i, m in enumerate(machine_objs):
            mid = m.machine_id
            score = float(topsis_scores.loc[mid])
            proba = float(proba_list[i])
            c_row = criteria_df.loc[mid]
            
            level, action_en, action_vi, color, badge = self.classify_risk(score)
            counts[level] += 1
            
            factors = self.explain_machine(c_row, top_k=3)
            
            # Radar criteria values (normalized)
            radar_dict = {
                col: round(float(norm_criteria_df.loc[mid, col]), 3)
                for col in CRITERIA_COLS
            }

            results_list.append({
                "machine_id": mid,
                "type": m.type,
                "raw_inputs": asdict(m),
                "failure_probability": round(proba, 4),
                "failure_probability_pct": round(proba * 100, 1),
                "topsis_score": round(score, 4),
                "risk_level": level,
                "action": action_en,
                "action_vi": action_vi,
                "color": color,
                "badge_class": badge,
                "contributing_factors": factors,
                "normalized_criteria": radar_dict
            })

        # Sắp xếp theo TOPSIS score giảm dần (Ưu tiên cao nhất lên đầu)
        results_list.sort(key=lambda x: x["topsis_score"], reverse=True)
        for rank, r in enumerate(results_list, start=1):
            r["priority_rank"] = rank

        top_machine = results_list[0] if results_list else None

        return {
            "total_machines": len(results_list),
            "counts": counts,
            "top_priority_machine": top_machine["machine_id"] if top_machine else "None",
            "top_machine_details": top_machine,
            "ranking": results_list,
            "ahp_weights": {k: round(float(v), 3) for k, v in self.ahp_weights.items()},
            "thresholds": self.thresholds,
        }


# Singleton engine instance
_engine_instance: Optional[DSSEngine] = None

def get_dss_engine() -> DSSEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DSSEngine()
    return _engine_instance
