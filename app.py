from flask import Flask, request, render_template, jsonify, Response
import redis
import os
import json
from datetime import datetime, timedelta


app = Flask(__name__)

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),  # 开发时用 localhost，部署时改 Linux 服务器 IP
    port=int(os.getenv('REDIS_PORT', 6379)),    # 默认端口 6379
    password=os.getenv('REDIS_PASSWORD', ''),   # 本地开发无密码，部署时可设置 Redis 密码
    db=0,                                       # 用第 0 个数据库（可自定义）
    decode_responses=True,                      # 自动把 Redis 的 bytes 转成字符串（避免 b'xxx' 格式）
    socket_timeout=5,                           # 连接超时 5 秒（避免卡顿时长）
)
CLIPBOARD_KEY = 'cloud_clipboard'
JOURNAL_LOCAL_DIR = os.path.join(os.path.dirname(__file__), 'data', 'journals')
JOURNAL_REDIS_EXPIRE_DAYS = 30  # Redis 只保留最近 30 天

# 确保本地存储目录存在
os.makedirs(JOURNAL_LOCAL_DIR, exist_ok=True)

try:
    redis_client.ping()
    print("Redis 连接成功！")
except Exception as e:
    print(f"Redis 连接失败：{e}（请检查 Redis 服务是否启动）")


def save_journal_to_local(date_str, journal_data):
    """保存日记到本地文件"""
    # 按年月组织文件夹
    year_month = date_str[:7]  # YYYY-MM
    month_dir = os.path.join(JOURNAL_LOCAL_DIR, year_month)
    os.makedirs(month_dir, exist_ok=True)
    
    file_path = os.path.join(month_dir, f'{date_str}.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(journal_data, f, ensure_ascii=False, indent=2)


def load_journal_from_local(date_str):
    """从本地文件加载日记"""
    year_month = date_str[:7]
    file_path = os.path.join(JOURNAL_LOCAL_DIR, year_month, f'{date_str}.json')
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/bug-fix')
def tool1():
    return render_template('tool1.html')


@app.route('/feature')
def tool2():
    return render_template('tool2.html')


@app.route('/clipboard', methods=['GET', 'POST'])
def tool3():
    if request.method == 'POST':
        new_content = request.form.get('clipboardText', '').strip()
        redis_client.set(CLIPBOARD_KEY, new_content)
        return render_template('tool3.html', clipboard=new_content)
    
    latest_content = redis_client.get(CLIPBOARD_KEY) or ''
    return render_template('tool3.html', clipboard=latest_content)


@app.route('/base64')
def tool4():
    return render_template('tool4.html')


@app.route('/color')
def tool5():
    return render_template('tool5.html')


@app.route('/morning-journal', methods=['GET', 'POST'])
def tool6():
    if request.method == 'POST':
        data = request.get_json()
        date_str = datetime.now().strftime('%Y-%m-%d')
        journal_key = f'morning_journal:{date_str}'
        
        journal_data = {
            'date': date_str,
            'timestamp': datetime.now().isoformat(),
            'success': data.get('success', ''),
            'regret': data.get('regret', ''),
            'highlight': data.get('highlight', ''),
            'frog': data.get('frog', '')
        }
        
        try:
            # 保存到 Redis（设置 30 天过期）
            redis_client.set(journal_key, json.dumps(journal_data, ensure_ascii=False), 
                           ex=JOURNAL_REDIS_EXPIRE_DAYS * 24 * 3600)
            
            # 同时保存到本地文件（永久保存）
            save_journal_to_local(date_str, journal_data)
            
            return jsonify({'status': 'success', 'message': '日记保存成功'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'保存失败: {str(e)}'}), 500
    
    return render_template('tool6.html')


@app.route('/morning-journal/get', methods=['GET'])
def get_journal():
    date_str = request.args.get('date')
    if not date_str:
        # 默认查询昨天的日记
        yesterday = datetime.now().date() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
    
    journal_key = f'morning_journal:{date_str}'
    
    try:
        # 先从 Redis 查询
        journal_data = redis_client.get(journal_key)
        
        if journal_data:
            return jsonify({'status': 'success', 'data': json.loads(journal_data)})
        
        # Redis 没有，尝试从本地文件加载
        local_data = load_journal_from_local(date_str)
        if local_data:
            return jsonify({'status': 'success', 'data': local_data})
        
        # 都没有，返回空记录
        return jsonify({
            'status': 'success',
            'data': {
                'date': date_str,
                'success': 'None',
                'regret': 'None',
                'highlight': 'None',
                'frog': 'None'
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'获取失败: {str(e)}'}), 500


@app.route('/morning-journal/export', methods=['GET'])
def export_journal():
    """导出晨间日记为 HTML（日历网格形式）"""
    period = request.args.get('period', '7')
    
    try:
        days = int(period)
        days = max(1, min(days, 365))  # 限制 1-365 天
    except:
        days = 7
    
    # 星期映射
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday_full = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    
    # 收集日记数据
    journals = []
    today = datetime.now().date()
    
    for i in range(days):
        date = today - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        journal_key = f'morning_journal:{date_str}'
        
        # 先从 Redis 查询，没有则从本地加载
        journal_data = redis_client.get(journal_key)
        if journal_data:
            data = json.loads(journal_data)
        else:
            local_data = load_journal_from_local(date_str)
            if local_data:
                data = local_data
            else:
                data = {
                    'date': date_str,
                    'success': 'None',
                    'regret': 'None',
                    'highlight': 'None',
                    'frog': 'None'
                }
        
        # 添加额外信息
        data['day'] = date.day
        data['weekday'] = weekday_names[date.weekday()]
        data['weekday_full'] = weekday_full[date.weekday()]
        data['weekday_num'] = date.weekday()
        
        journals.append(data)
    
    # 按日期正序排列（用于日历网格）
    journals_sorted = sorted(journals, key=lambda x: x['date'])
    
    # 计算第一天是周几（用于填充空白格子）
    if journals_sorted:
        first_date = datetime.strptime(journals_sorted[0]['date'], '%Y-%m-%d').date()
        first_weekday = first_date.weekday()  # 0=周一, 6=周日
    else:
        first_weekday = 0
    
    # 日期范围
    start_date = journals_sorted[0]['date'] if journals_sorted else today.strftime('%Y-%m-%d')
    end_date = journals_sorted[-1]['date'] if journals_sorted else today.strftime('%Y-%m-%d')
    
    # 生成 HTML
    html = render_template('journal_export.html', 
                          journals=journals,  # 倒序（最新在前）
                          journals_sorted=journals_sorted,  # 正序（用于日历）
                          period=days,
                          first_weekday=first_weekday,
                          start_date=start_date,
                          end_date=end_date,
                          export_date=today.strftime('%Y-%m-%d'))
    
    # 返回 HTML 文件
    filename = f'morning_journal_{days}days_{today.strftime("%Y%m%d")}.html'
    return Response(
        html,
        mimetype='text/html',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


if __name__ == '__main__':
    app.run(debug=True)
