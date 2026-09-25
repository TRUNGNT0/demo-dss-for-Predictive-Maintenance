import sys
import json
from pathlib import Path

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from web.app import app

def run_tests():
    client = app.test_client()

    print("[*] 1. Kiểm thử trang chủ GET /")
    res = client.get('/')
    assert res.status_code == 200, f"Index failed: {res.status_code}"
    print("    [✓] Trang chủ trả về HTTP 200 OK")

    print("[*] 2. Kiểm thử trang lịch sử GET /history")
    res = client.get('/history')
    assert res.status_code == 200, f"History page failed: {res.status_code}"
    print("    [✓] Trang lịch sử trả về HTTP 200 OK")

    print("[*] 3. Kiểm thử API sinh ngẫu nhiên GET /api/random-machines?n=10")
    res = client.get('/api/random-machines?n=10')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['success'] is True and len(data['machines']) == 10
    print(f"    [✓] Sinh thành công {len(data['machines'])} máy ngẫu nhiên")

    print("[*] 4. Kiểm thử API thực thi DSS POST /api/run")
    run_payload = {'machines': data['machines']}
    res = client.post('/api/run', json=run_payload)
    assert res.status_code == 200
    run_data = json.loads(res.data)
    assert run_data['success'] is True
    run_id = run_data['run_id']
    ranking = run_data['data']['ranking']
    assert len(ranking) == 10
    top_m = ranking[0]
    print(f"    [✓] Phân tích hoàn tất: Run ID = {run_id}")
    print(f"        -> Máy ưu tiên số 1: {top_m['machine_id']} (TOPSIS={top_m['topsis_score']}, Mức={top_m['risk_level']})")

    print("[*] 5. Kiểm thử API danh sách lịch sử GET /api/history")
    res = client.get('/api/history')
    assert res.status_code == 200
    hist_data = json.loads(res.data)
    assert len(hist_data['runs']) >= 1
    print(f"    [✓] Lấy danh sách lịch sử thành công: {len(hist_data['runs'])} lượt chạy")

    print(f"[*] 6. Kiểm thử API chi tiết lượt chạy GET /api/history/{run_id}")
    res = client.get(f'/api/history/{run_id}')
    assert res.status_code == 200
    detail_data = json.loads(res.data)
    assert detail_data['success'] is True
    print(f"    [✓] Chi tiết lượt chạy hợp lệ")

    print("[*] 7. Kiểm thử API thông tin mô hình GET /api/model-info")
    res = client.get('/api/model-info')
    assert res.status_code == 200
    model_data = json.loads(res.data)
    print(f"    [✓] Thông tin DSS Model: {model_data.get('model_type')}")

    print("\n==================================================")
    print("   [✓] TOÀN BỘ KIỂM THỬ WEB DEMO ĐÃ THÀNH CÔNG!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
