from flask import Flask, request, render_template
import redis
import os


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

try:
    redis_client.ping()
    print("Redis 连接成功！")
except Exception as e:
    print(f"Redis 连接失败：{e}（请检查 Redis 服务是否启动）")

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


if __name__ == '__main__':
    app.run(debug=True)
