#!/usr/bin/env python3
"""
Script tải output từ Kaggle kernel trungnguyen0510/dss-maintenance-prioritization
vào thư mục chỉ định (mặc định: outputnotebook/).

Lệnh Kaggle CLI:
    kaggle kernels output trungnguyen0510/dss-maintenance-prioritization -p outputnotebook

Nếu máy chưa cài đặt kaggle hoặc chưa có kaggle.json, script cung cấp tuỳ chọn
tự động huấn luyện & sinh các artifact cục bộ tương đương trực tiếp từ notebook.
"""

import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

REQUIRED_ARTIFACT_FILES = [
    "type_encoder.joblib",
    "scaler.joblib",
    "ml_model.joblib",
    "ahp_weights.json",
    "criteria_min.json",
    "criteria_max.json",
    "decision_thresholds.json"
]

KERNEL_SLUG = "trungnguyen0510/dss-maintenance-prioritization"

def check_artifacts_in_dir(target_dir: Path) -> bool:
    """Kiểm tra xem thư mục có đủ 7 file artifact cần thiết hay không."""
    if not target_dir.exists():
        return False
    
    # Kiểm tra trực tiếp trong target_dir
    files_present = [f for f in REQUIRED_ARTIFACT_FILES if (target_dir / f).exists()]
    if len(files_present) == len(REQUIRED_ARTIFACT_FILES):
        return True
    
    # Hoặc kiểm tra trong subfolder dss_artifacts
    sub_dir = target_dir / "dss_artifacts"
    if sub_dir.exists():
        sub_present = [f for f in REQUIRED_ARTIFACT_FILES if (sub_dir / f).exists()]
        if len(sub_present) == len(REQUIRED_ARTIFACT_FILES):
            return True
            
    return False

def download_from_kaggle(dest_dir: Path) -> bool:
    """Chạy lệnh kaggle kernels output để tải kết quả."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "kaggle", "kernels", "output",
        KERNEL_SLUG,
        "-p", str(dest_dir.resolve())
    ]
    
    print(f"[*] Đang thực thi lệnh tải từ Kaggle:")
    print(f"    {' '.join(cmd)}\n")
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("[+] Kết quả từ Kaggle CLI:")
        print(res.stdout)
        
        # Nếu tải về trong thư mục con dss_artifacts, copy ra thư mục chính nếu cần
        sub_dir = dest_dir / "dss_artifacts"
        if sub_dir.exists():
            for f in sub_dir.glob("*"):
                shutil.copy(f, dest_dir / f.name)
                
        return True
    except FileNotFoundError:
        print("[-] Cảnh báo: Lệnh 'kaggle' chưa được cài đặt trong PATH hệ thống.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[-] Lỗi khi tải output từ Kaggle: {e.stderr or e.stdout}")
        return False
    except Exception as e:
        print(f"[-] Lỗi không xác định: {e}")
        return False

def generate_local_artifacts(dest_dir: Path) -> bool:
    """
    Sinh các DSS artifact cục bộ theo đúng quy trình từ notebook
    (dùng làm fallback khi chưa có Kaggle API token hoặc không có mạng).
    """
    print("\n[*] Đang tạo/huấn luyện DSS components cục bộ...")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        import numpy as np
        import pandas as pd
        import joblib
        import json
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler, OrdinalEncoder
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import precision_recall_curve, roc_auc_score
        from scipy.optimize import minimize
        
        # 1. Dataset
        rng = np.random.default_rng(42)
        n = 10000
        type_ = rng.choice(["L", "M", "H"], size=n, p=[0.6, 0.3, 0.1])
        air_temp = rng.normal(300, 2, n)
        process_temp = air_temp + rng.normal(10, 1, n)
        rot_speed = rng.normal(1538, 180, n).clip(1000, 2900)
        torque = rng.normal(40, 10, n).clip(3, 77)
        tool_wear = rng.uniform(0, 253, n)
        type_bonus = np.select([type_ == "L", type_ == "M", type_ == "H"], [0, 1, 3])

        twf = (tool_wear > 200) & (rng.random(n) < 0.35)
        hdf = ((process_temp - air_temp) < 8.6) & (rot_speed < 1380) & (rng.random(n) < 0.5)
        pwf_power = torque * rot_speed * 2 * np.pi / 60
        pwf = ((pwf_power < 3500) | (pwf_power > 9000)) & (rng.random(n) < 0.5)
        osf = ((tool_wear * torque) > (11000 + type_bonus * 1000)) & (rng.random(n) < 0.6)
        rnf = rng.random(n) < 0.001
        machine_failure = (twf | hdf | pwf | osf | rnf).astype(int)

        df = pd.DataFrame({
            "Type": type_,
            "Air_temperature_K": air_temp.round(1),
            "Process_temperature_K": process_temp.round(1),
            "Rotational_speed_rpm": rot_speed.round(0).astype(int),
            "Torque_Nm": torque.round(1),
            "Tool_wear_min": tool_wear.round(0).astype(int),
            "Machine_failure": machine_failure,
        })
        
        FEATURE_COLS = ["Type", "Air_temperature_K", "Process_temperature_K",
                         "Rotational_speed_rpm", "Torque_Nm", "Tool_wear_min"]
        CRITERIA_COLS = ["Failure_Probability", "Tool_wear_min", "Torque_Nm",
                          "Process_temperature_K", "Rotational_speed_rpm", "Air_temperature_K"]
        
        X = df[FEATURE_COLS].copy()
        y = df["Machine_failure"].copy()
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.2, random_state=42, stratify=y_train)
        
        # Encoders & Scalers
        type_encoder = OrdinalEncoder(categories=[["L", "M", "H"]])
        X_train_enc = X_train.copy()
        X_val_enc = X_val.copy()
        X_train_enc["Type"] = type_encoder.fit_transform(X_train[["Type"]])
        X_val_enc["Type"] = type_encoder.transform(X_val[["Type"]])
        
        scaler = StandardScaler()
        X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train_enc), columns=FEATURE_COLS, index=X_train_enc.index)
        X_val_scaled = pd.DataFrame(scaler.transform(X_val_enc), columns=FEATURE_COLS, index=X_val_enc.index)
        
        # Model
        final_model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight="balanced")
        final_model.fit(X_train_scaled, y_train)
        
        val_proba = final_model.predict_proba(X_val_scaled)[:, 1]
        
        # DSS Criteria & AHP Calibration
        def build_criteria_frame(X_raw_df, failure_proba):
            crit = X_raw_df[["Tool_wear_min", "Torque_Nm", "Process_temperature_K",
                              "Rotational_speed_rpm", "Air_temperature_K"]].copy()
            crit.insert(0, "Failure_Probability", failure_proba)
            return crit[CRITERIA_COLS]

        val_criteria = build_criteria_frame(X_val, val_proba)
        
        def minmax_normalize(df_crit, ref_min=None, ref_max=None):
            ref_min = df_crit.min() if ref_min is None else ref_min
            ref_max = df_crit.max() if ref_max is None else ref_max
            return (df_crit - ref_min) / (ref_max - ref_min + 1e-9), ref_min, ref_max

        val_norm, crit_min, crit_max = minmax_normalize(val_criteria)
        
        init_weights = np.array([0.38, 0.24, 0.16, 0.10, 0.07, 0.05])
        init_weights = init_weights / init_weights.sum()

        def neg_auc_of_weighted_score(w, norm_df, y_true):
            w = np.abs(w)
            w = w / w.sum()
            score = norm_df.values @ w
            try:
                return -roc_auc_score(y_true, score)
            except ValueError:
                return 0.0

        constraints = ({"type": "eq", "fun": lambda w: np.sum(np.abs(w)) - 1.0},)
        bounds = [(0.0, 1.0)] * len(CRITERIA_COLS)

        opt = minimize(neg_auc_of_weighted_score, x0=init_weights, args=(val_norm, y_val),
                       method="SLSQP", bounds=bounds, constraints=constraints,
                       options={"maxiter": 300, "ftol": 1e-9})

        calibrated_weights = np.abs(opt.x)
        calibrated_weights = calibrated_weights / calibrated_weights.sum()
        ahp_weights = pd.Series(calibrated_weights, index=CRITERIA_COLS).sort_values(ascending=False)
        
        # TOPSIS & Thresholds
        def topsis_score(criteria_df, weights, ref_min=None, ref_max=None):
            norm, _, _ = minmax_normalize(criteria_df, ref_min, ref_max)
            weighted = norm.values * weights.values
            pis = weighted.max(axis=0)
            nis = weighted.min(axis=0)
            dist_pos = np.sqrt(((weighted - pis) ** 2).sum(axis=1))
            dist_neg = np.sqrt(((weighted - nis) ** 2).sum(axis=1))
            score = dist_neg / (dist_pos + dist_neg + 1e-12)
            return pd.Series(score, index=criteria_df.index, name="TOPSIS_Score")

        val_topsis = topsis_score(val_criteria, ahp_weights, crit_min, crit_max)

        def calibrate_thresholds(scores, y_true, recall_targets=(0.95, 0.75, 0.50)):
            precision, recall, thr = precision_recall_curve(y_true, scores)
            recall_ = recall[:-1]
            thr_ = thr
            order = np.argsort(thr_)
            thr_sorted, recall_sorted = thr_[order], recall_[order]

            chosen = []
            for target in recall_targets:
                idx_candidates = np.where(recall_sorted >= target)[0]
                if len(idx_candidates) == 0:
                    chosen.append(thr_sorted[0])
                else:
                    chosen.append(thr_sorted[idx_candidates[-1]])
            chosen = sorted(chosen)
            return chosen

        t_medium, t_high, t_critical = calibrate_thresholds(val_topsis.values, y_val.values)

        # Lưu files
        joblib.dump(type_encoder, dest_dir / "type_encoder.joblib")
        joblib.dump(scaler, dest_dir / "scaler.joblib")
        joblib.dump(final_model, dest_dir / "ml_model.joblib")

        ahp_weights.to_json(dest_dir / "ahp_weights.json")
        crit_min.to_json(dest_dir / "criteria_min.json")
        crit_max.to_json(dest_dir / "criteria_max.json")

        with open(dest_dir / "decision_thresholds.json", "w") as f:
            json.dump({
                "t_medium": float(t_medium),
                "t_high": float(t_high),
                "t_critical": float(t_critical),
                "final_model": "RandomForestClassifier (Local Pipeline)",
                "data_source": "synthetic_fallback"
            }, f, indent=2)

        print(f"[+] Đã tạo thành công 7 DSS artifacts trong: {dest_dir.resolve()}")
        return True
    except Exception as e:
        print(f"[-] Lỗi khi sinh artifacts cục bộ: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Tải Kaggle kernel output hoặc khởi tạo artifacts cho DSS")
    parser.add_argument("-p", "--dest", default="outputnotebook", help="Đường dẫn thư mục đích (mặc định: outputnotebook)")
    parser.add_argument("--force-kaggle", action="store_true", help="Chỉ tải từ Kaggle, không dùng fallback")
    parser.add_argument("--local-only", action="store_true", help="Chỉ sinh cục bộ từ notebook logic")
    args = parser.parse_args()

    target_dir = Path(args.dest)

    if args.local_only:
        generate_local_artifacts(target_dir)
        return

    print(f"[*] Bắt đầu chuẩn bị DSS artifacts vào thư mục '{target_dir}'...")
    success = download_from_kaggle(target_dir)
    
    if not success and not args.force_kaggle:
        print("\n[!] Không thể tải từ Kaggle (có thể thiếu kaggle CLI hoặc API key).")
        print("[!] Đang tự động chuyển sang chế độ tạo artifacts cục bộ...")
        success = generate_local_artifacts(target_dir)

    if success or check_artifacts_in_dir(target_dir):
        print("\n=======================================================")
        print(f"[✓] HOÀN TẤT! Tất cả artifacts đã sẵn sàng trong '{target_dir}'.")
        print(f"    Bạn có thể chạy web demo bằng lệnh: python web/app.py")
        print("=======================================================")
    else:
        print("\n[✗] Thất bại trong việc chuẩn bị artifacts.")
        sys.exit(1)

if __name__ == "__main__":
    main()
