"""
DSS Maintenance Prioritization Web Application
Flask Web Server cung cấp giao diện Dashboard, REST API và quản lý lịch sử demo.
"""

import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS

# Add root directory to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web.dss_engine import get_dss_engine
from web.history_manager import get_history_manager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dss-maintenance-prioritization-secret-key-2026'
CORS(app)

# Initialize singletons
dss_engine = get_dss_engine()
history_manager = get_history_manager()


@app.route('/')
def index():
    """Trang chủ Dashboard phân tích & xếp hạng ưu tiên bảo trì."""
    model_info = dss_engine.get_model_info()
    initial_machines = dss_engine.generate_demo_machines(n=10, seed=7)
    recent_history = history_manager.get_all_runs(limit=5)
    return render_template(
        'index.html',
        model_info=model_info,
        initial_machines=initial_machines,
        recent_history=recent_history
    )


@app.route('/history')
def history_page():
    """Trang xem toàn bộ lịch sử demo."""
    all_runs = history_manager.get_all_runs(limit=100)
    return render_template('history.html', runs=all_runs)


# ==========================================
# REST API Endpoints
# ==========================================

@app.route('/api/random-machines', methods=['GET'])
def api_random_machines():
    """API sinh n máy ngẫu nhiên với phân phối AI4I 2020."""
    try:
        n = int(request.args.get('n', 10))
        n = max(1, min(n, 100)) # Giới hạn 1 - 100 máy
        machines = dss_engine.generate_demo_machines(n=n)
        return jsonify({"success": True, "count": len(machines), "machines": machines})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/run', methods=['POST'])
def api_run():
    """API tiếp nhận danh sách máy và thực thi pipeline DSS."""
    try:
        payload = request.get_json(force=True)
        machines = payload.get('machines', [])
        if not machines:
            return jsonify({"success": False, "error": "Danh sách máy không được để trống"}), 400

        results = dss_engine.evaluate_batch(machines)
        run_id = history_manager.save_run(results, machines)
        
        return jsonify({
            "success": True,
            "run_id": run_id,
            "data": results
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/model-info', methods=['GET'])
def api_model_info():
    """API lấy thông tin model, trọng số AHP và ngưỡng quyết định."""
    return jsonify(dss_engine.get_model_info())


@app.route('/api/history', methods=['GET'])
def api_get_history():
    """API lấy danh sách tóm tắt lịch sử."""
    limit = int(request.args.get('limit', 50))
    runs = history_manager.get_all_runs(limit=limit)
    return jsonify({"success": True, "runs": runs})


@app.route('/api/history/<run_id>', methods=['GET'])
def api_get_history_detail(run_id):
    """API lấy dữ liệu chi tiết của một lần chạy."""
    run = history_manager.get_run(run_id)
    if not run:
        return jsonify({"success": False, "error": "Không tìm thấy lượt chạy chỉ định"}), 404
    return jsonify({"success": True, "run": run})


@app.route('/api/history/delete/<run_id>', methods=['POST', 'DELETE'])
def api_delete_history(run_id):
    """API xoá một lần chạy trong lịch sử."""
    success = history_manager.delete_run(run_id)
    return jsonify({"success": success})


@app.route('/api/history/clear', methods=['POST'])
def api_clear_history():
    """API xoá toàn bộ lịch sử demo."""
    history_manager.clear_all()
    return jsonify({"success": True, "message": "Đã xóa toàn bộ lịch sử"})


if __name__ == '__main__':
    print("===============================================================")
    print("  DSS MAINTENANCE PRIORITIZATION - FLASK WEB DEMO SERVER")
    print("  Giao diện demo đang chạy tại: http://127.0.0.1:5000")
    print("===============================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
