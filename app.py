from flask import Flask, request, render_template, jsonify, Response
import redis
import os
import json
import re
from datetime import datetime, timedelta


app = Flask(__name__)

# 输入验证配置
MAX_FIELD_LENGTH = 500  # 每个字段最大长度（字符数）
MAX_CLIPBOARD_LENGTH = 10000  # 剪切板内容最大长度
MIN_FIELD_LENGTH = 1  # 最小长度（至少1个字符）
DATE_FORMAT_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}$')  # 日期格式验证：YYYY-MM-DD

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD', ''),
    db=0,
    decode_responses=True,
    socket_timeout=5,
)
CLIPBOARD_KEY = 'cloud_clipboard'
JOURNAL_LOCAL_DIR = os.path.join(os.path.dirname(__file__), 'data', 'journals')
JOURNAL_REDIS_EXPIRE_DAYS = 30

os.makedirs(JOURNAL_LOCAL_DIR, exist_ok=True)

try:
    redis_client.ping()
    print("Redis 连接成功！")
except Exception as e:
    print(f"Redis 连接失败：{e}（请检查 Redis 服务是否启动）")


# ========== 输入验证函数 ==========

def validate_journal_field(field_value, field_name='字段'):
    """
    验证日记字段内容
    返回: (is_valid, cleaned_value, error_message)
    """
    if not isinstance(field_value, str):
        return False, None, f'{field_name}必须是字符串类型'
    
    # 去除首尾空格
    cleaned = field_value.strip()
    
    # 检查长度
    if len(cleaned) < MIN_FIELD_LENGTH:
        return False, None, f'{field_name}不能为空'
    
    if len(cleaned) > MAX_FIELD_LENGTH:
        return False, None, f'{field_name}长度不能超过{MAX_FIELD_LENGTH}个字符'
    
    # 检查是否包含潜在的恶意字符（可根据需要调整）
    # 禁止控制字符（除了换行符和制表符）
    if re.search(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', cleaned):
        return False, None, f'{field_name}包含非法字符'
    
    return True, cleaned, None


def validate_date_string(date_str):
    """
    验证日期字符串格式
    返回: (is_valid, error_message)
    """
    if not isinstance(date_str, str):
        return False, '日期参数必须是字符串'
    
    # 检查格式
    if not DATE_FORMAT_REGEX.match(date_str):
        return False, '日期格式不正确，应为 YYYY-MM-DD'
    
    # 验证日期是否有效
    try:
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        # 检查日期范围（不能是未来日期，最早可以是2020年）
        today = datetime.now().date()
        if parsed_date > today:
            return False, '日期不能是未来日期'
        if parsed_date < datetime(2020, 1, 1).date():
            return False, '日期不能早于2020年'
        return True, None
    except ValueError:
        return False, '日期无效'


def sanitize_string(text, max_length=None):
    """
    清理字符串，移除潜在危险字符
    """
    if not isinstance(text, str):
        return ''
    
    # 去除首尾空格
    cleaned = text.strip()
    
    # 限制长度
    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    
    return cleaned


def validate_period(period_str):
    """
    验证导出天数参数
    返回: (is_valid, days, error_message)
    """
    try:
        days = int(period_str)
        if days < 1:
            return False, None, '天数必须大于0'
        if days > 365:
            return False, None, '天数不能超过365'
        return True, days, None
    except (ValueError, TypeError):
        return False, None, '天数必须是有效的数字'


# ========== 原有函数保持不变 ==========

def save_journal_to_local(date_str, journal_data):
    """保存日记到本地文件"""
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
        
        # 添加验证
        if len(new_content) > MAX_CLIPBOARD_LENGTH:
            return render_template('tool3.html', 
                                 clipboard='', 
                                 error=f'内容过长，最大支持{MAX_CLIPBOARD_LENGTH}个字符')
        
        # 检查控制字符
        if re.search(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', new_content):
            return render_template('tool3.html', 
                                 clipboard='', 
                                 error='内容包含非法字符')
        
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
        # 验证请求数据
        if not request.is_json:
            return jsonify({'status': 'error', 'message': '请求必须是JSON格式'}), 400
        
        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': '请求数据格式错误'}), 400
        
        # 验证每个字段
        fields_to_validate = {
            'success': '成功事项',
            'regret': '遗憾事项',
            'highlight': '本日精华',
            'frog': '今日青蛙'
        }
        
        validated_data = {}
        for field_key, field_name in fields_to_validate.items():
            field_value = data.get(field_key, '')
            
            is_valid, cleaned_value, error_msg = validate_journal_field(field_value, field_name)
            if not is_valid:
                return jsonify({'status': 'error', 'message': error_msg}), 400
            
            validated_data[field_key] = cleaned_value
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        journal_key = f'morning_journal:{date_str}'
        
        journal_data = {
            'date': date_str,
            'timestamp': datetime.now().isoformat(),
            'success': validated_data['success'],
            'regret': validated_data['regret'],
            'highlight': validated_data['highlight'],
            'frog': validated_data['frog']
        }
        
        try:
            # 保存到 Redis（设置 30 天过期）
            redis_client.set(journal_key, json.dumps(journal_data, ensure_ascii=False), 
                           ex=JOURNAL_REDIS_EXPIRE_DAYS * 24 * 3600)
            
            # 同时保存到本地文件（永久保存）
            save_journal_to_local(date_str, journal_data)
            
            return jsonify({'status': 'success', 'message': '日记保存成功'})
        except Exception as e:
            # 不返回详细错误信息，避免泄露内部信息
            return jsonify({'status': 'error', 'message': '保存失败，请稍后重试'}), 500
    
    return render_template('tool6.html')


@app.route('/morning-journal/get', methods=['GET'])
def get_journal():
    date_str = request.args.get('date')
    if not date_str:
        # 默认查询昨天的日记
        yesterday = datetime.now().date() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
    else:
        # 验证日期格式
        is_valid, error_msg = validate_date_string(date_str)
        if not is_valid:
            return jsonify({'status': 'error', 'message': error_msg}), 400
    
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
        # 不返回详细错误信息
        return jsonify({'status': 'error', 'message': '获取失败，请稍后重试'}), 500


@app.route('/morning-journal/export', methods=['GET'])
def export_journal():
    """导出晨间日记为 HTML（日历网格形式）"""
    period = request.args.get('period', '7')
    
    # 验证天数参数
    is_valid, days, error_msg = validate_period(period)
    if not is_valid:
        return jsonify({'status': 'error', 'message': error_msg}), 400
    
    # 星期映射
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday_full = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    
    # 收集日记数据
    journals = []
    today = datetime.now().date()
    
    try:
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
    except Exception as e:
        # 不返回详细错误信息
        return jsonify({'status': 'error', 'message': '导出失败，请稍后重试'}), 500


if __name__ == '__main__':
    app.run(debug=True)