import os
import time
import json
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
from flask import Flask, render_template

# 导入我们现有的模块
from news_monitor import monitor_news, BASE_URL, create_directory_structure
from news_event_extractor import NewsEventExtractor

# 创建Flask应用
app = Flask(__name__)
app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')

# 全局变量
processed_files = set()  # 记录已经处理过的文件
watcher_thread = None  # 文件监视线程
observer = None  # 文件观察者

IMPACT_LABELS = {
    "positive": "利好",
    "neutral": "中性",
    "negative": "利空",
    "unknown": "未知"
}

EVENT_TYPE_LABELS = {
    "regulation": "监管",
    "delisting": "退市风险",
    "fraud": "欺诈",
    "share_issuance": "股权/融资",
    "executive_change": "高管变动",
    "policy_change": "政策变化",
    "merger": "合并重组",
    "large_holder_trade": "大股东交易",
    "organization_change": "组织变化",
    "investigation": "立案调查",
    "security_breach": "安全事件",
    "acquisition": "收购",
    "public_relations": "舆情公关",
    "other": "其他",
    "others": "其他"
}


def parse_date_value(date_str, fmt):
    """将日期字符串解析为datetime，失败则返回None"""
    if not isinstance(date_str, str) or not date_str:
        return None

    try:
        return datetime.strptime(date_str, fmt)
    except ValueError:
        return None


def get_collection_date(file_path, json_directory):
    """从JSON相对路径中提取采集日期"""
    relative_path = os.path.relpath(file_path, json_directory)
    path_parts = relative_path.split(os.sep)
    if not path_parts:
        return None

    return parse_date_value(path_parts[0], "%Y%m%d")


def get_event_sort_date(event_date):
    """解析事件日期，用于排序回退"""
    return parse_date_value(event_date, "%Y-%m-%d") or datetime.min


def get_news_sort_key(news_item):
    """新闻排序键：优先按采集日期，再按文件修改时间，再按事件日期"""
    return (
        news_item.get("_collection_sort", datetime.min),
        news_item.get("_updated_sort", 0.0),
        news_item.get("_event_sort", datetime.min)
    )


def build_news_item(data, file_path, json_directory, base_dir):
    """构建前端展示需要的新闻数据"""
    source_file = os.path.basename(file_path)
    txt_filename = os.path.splitext(source_file)[0] + ".txt"
    collection_date = get_collection_date(file_path, json_directory)
    updated_timestamp = os.path.getmtime(file_path)
    updated_datetime = datetime.fromtimestamp(updated_timestamp)
    event_types = data.get("event_type")

    if isinstance(event_types, list):
        localized_event_types = [EVENT_TYPE_LABELS.get(event_type, event_type) for event_type in event_types]
    elif event_types:
        localized_event_types = [EVENT_TYPE_LABELS.get(event_types, event_types)]
    else:
        localized_event_types = []

    news_item = dict(data)
    news_item["source_file"] = source_file
    news_item["news_txt_file"] = os.path.join(base_dir, "newsData", "Phonix", "ssgsyjy", txt_filename)
    news_item["json_file_path"] = file_path
    news_item["collection_date"] = collection_date.strftime("%Y-%m-%d") if collection_date else "未知"
    news_item["updated_at"] = updated_datetime.strftime("%Y-%m-%d %H:%M:%S")
    news_item["impact_label"] = IMPACT_LABELS.get(news_item.get("impact_direction"), "未知")
    news_item["event_type_labels"] = localized_event_types
    news_item["_collection_sort"] = collection_date or datetime.min
    news_item["_updated_sort"] = updated_timestamp
    news_item["_event_sort"] = get_event_sort_date(news_item.get("event_date"))
    return news_item

class NewsFileHandler(FileSystemEventHandler):
    """处理新闻文件变化的处理器"""
    
    def __init__(self, json_directory):
        self.json_directory = json_directory
        self.extractor = NewsEventExtractor()
        
    def on_created(self, event):
        """当有新文件创建时触发"""
        if not event.is_directory and event.src_path.endswith('.txt'):
            print(f"检测到新文件: {event.src_path}")
            # 使用线程处理文件，避免阻塞文件系统监听
            thread = threading.Thread(target=self.process_news_file, args=(event.src_path,))
            thread.daemon = True
            thread.start()
    
    def process_news_file(self, file_path):
        """处理新闻文件并提取事件信息"""
        try:
            # 检查是否已经处理过该文件
            if file_path in processed_files:
                print(f"文件已处理过，跳过: {file_path}")
                return
                
            print(f"正在处理文件: {file_path}")
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                print(f"文件内容为空: {file_path}")
                processed_files.add(file_path)
                return
            
            # 使用news_event_extractor解析内容
            result = self.extractor.extract_events(content)
            
            # 生成JSON文件名
            base_name = os.path.basename(file_path)
            name_without_ext = os.path.splitext(base_name)[0]
            json_filename = f"{name_without_ext}.json"
            
            # 创建日期目录结构
            today = datetime.now().strftime("%Y%m%d")
            json_path = os.path.join(self.json_directory, today, "Phonix", "ssgsyjy")
            
            # 确保目录存在
            os.makedirs(json_path, exist_ok=True)
            
            # 保存JSON文件
            json_file_path = os.path.join(json_path, json_filename)
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"已保存JSON文件: {json_file_path}")
            processed_files.add(file_path)
            
        except Exception as e:
            print(f"处理文件时出错 {file_path}: {e}")

def process_existing_files(watch_directory, json_directory):
    """处理已存在的文件"""
    print(f"正在处理已存在的文件: {watch_directory}")
    
    # 创建提取器实例
    extractor = NewsEventExtractor()
    
    # 遍历目录中的所有txt文件
    for root, dirs, files in os.walk(watch_directory):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                
                # 检查是否已经处理过该文件
                if file_path in processed_files:
                    print(f"文件已处理过，跳过: {file_path}")
                    continue
                    
                try:
                    print(f"正在处理已存在的文件: {file_path}")
                    
                    # 读取文件内容
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if not content.strip():
                        print(f"文件内容为空: {file_path}")
                        processed_files.add(file_path)
                        continue
                    
                    # 使用news_event_extractor解析内容
                    result = extractor.extract_events(content)
                    
                    # 生成JSON文件名
                    base_name = os.path.basename(file_path)
                    name_without_ext = os.path.splitext(base_name)[0]
                    json_filename = f"{name_without_ext}.json"
                    
                    # 创建日期目录结构
                    today = datetime.now().strftime("%Y%m%d")
                    json_path = os.path.join(json_directory, today, "Phonix", "ssgsyjy")
                    
                    # 确保目录存在
                    os.makedirs(json_path, exist_ok=True)
                    
                    # 保存JSON文件
                    json_file_path = os.path.join(json_path, json_filename)
                    with open(json_file_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    
                    print(f"已保存JSON文件: {json_file_path}")
                    processed_files.add(file_path)
                    
                except Exception as e:
                    print(f"处理文件时出错 {file_path}: {e}")

def start_file_watcher(watch_directory, json_directory):
    """启动文件监视器"""
    global observer
    
    # 创建JSON保存目录
    os.makedirs(json_directory, exist_ok=True)
    
    # 首先处理已存在的文件
    process_existing_files(watch_directory, json_directory)
    
    # 设置事件处理器
    event_handler = NewsFileHandler(json_directory)
    
    # 创建观察者
    observer = Observer()
    observer.schedule(event_handler, watch_directory, recursive=True)
    
    # 启动观察者
    observer.start()
    print(f"开始监视目录: {watch_directory}")
    print(f"JSON文件将保存到: {json_directory}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("文件监视已停止")
    
    observer.join()

def start_news_monitor(refresh_interval=30):
    """启动新闻监视器"""
    print("启动新闻链接监视器...")
    
    # 创建保存新闻文件的目录
    directory = create_directory_structure()
    
    # 启动监视器
    monitor_news(BASE_URL, refresh_interval, directory)

def get_filtered_news_data(json_directory):
    """读取和过滤所有JSON文件，返回company_confidence >= 0.6的新闻数据"""
    base_dir = os.path.dirname(__file__)
    latest_news_by_source = {}

    # 遍历json_directory下的所有日期目录，按同一source_file只保留最新版本
    for root, dirs, files in os.walk(json_directory):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict) and 'company_confidence' in data:
                            news_item = build_news_item(data, file_path, json_directory, base_dir)
                            existing_item = latest_news_by_source.get(file)

                            if existing_item is None or get_news_sort_key(news_item) > get_news_sort_key(existing_item):
                                latest_news_by_source[file] = news_item
                except json.JSONDecodeError:
                    print(f"解析JSON文件出错: {file_path}")
                except Exception as e:
                    print(f"读取JSON文件出错 {file_path}: {e}")

    news_data = [
        news_item for news_item in latest_news_by_source.values()
        if news_item.get('company_confidence', 0) >= 0.6
    ]
    news_data.sort(key=get_news_sort_key, reverse=True)

    return news_data

@app.route('/')
def index():
    """Flask主页路由"""
    # 设置JSON目录路径
    json_directory = os.path.join(os.path.dirname(__file__), 'newsJson')
    # 获取过滤后的新闻数据
    news_data = get_filtered_news_data(json_directory)
    latest_collection_date = news_data[0]['collection_date'] if news_data else "暂无"
    latest_update_time = news_data[0]['updated_at'] if news_data else "暂无"
    impact_stats = {
        'positive': sum(1 for item in news_data if item.get('impact_direction') == 'positive'),
        'neutral': sum(1 for item in news_data if item.get('impact_direction') == 'neutral'),
        'negative': sum(1 for item in news_data if item.get('impact_direction') == 'negative')
    }
    # 获取当前时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 渲染模板
    return render_template(
        'index.html',
        news_data=news_data,
        current_time=current_time,
        latest_collection_date=latest_collection_date,
        latest_update_time=latest_update_time,
        impact_stats=impact_stats
    )

@app.route('/news/<filename>')
def get_news_content(filename):
    """获取新闻原文内容"""
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, 'newsData', 'Phonix', 'ssgsyjy', filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 获取当前时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return render_template('news_content.html', content=content, title="新闻原文", filename=filename, current_time=current_time)
    except FileNotFoundError:
        return f"文件未找到: {filename}", 404
    except Exception as e:
        return f"读取文件出错: {str(e)}", 500

@app.route('/llm/<filename>')
def get_llm_content(filename):
    """获取LLM判断原文内容"""
    base_dir = os.path.dirname(__file__)
    # 查找对应的JSON文件
    json_file = None
    for root, dirs, files in os.walk(os.path.join(base_dir, 'newsJson')):
        for file in files:
            if file == filename:
                json_file = os.path.join(root, file)
                break
        if json_file:
            break
    
    if json_file:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # 获取当前时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return render_template('news_content.html', content=content, title="LLM判断原文", filename=filename, current_time=current_time)
        except Exception as e:
            return f"读取文件出错: {str(e)}", 500
    else:
        return f"文件未找到: {filename}", 404

def main():
    """主函数"""
    print("新闻LLM系统启动")
    
    # 设置目录路径
    current_dir = os.path.dirname(__file__)
    watch_directory = os.path.join(current_dir, "newsData")
    json_directory = os.path.join(current_dir, "newsJson")
    
    # 创建JSON保存目录
    os.makedirs(json_directory, exist_ok=True)
    
    # 刷新间隔设置为30秒
    refresh_interval = 30
    print(f"新闻刷新间隔设置为: {refresh_interval}秒")
    
    # 启动新闻监视器线程
    news_thread = threading.Thread(target=start_news_monitor, args=(refresh_interval,))
    news_thread.daemon = True
    news_thread.start()
    
    # 启动文件监视器线程
    file_watcher_thread = threading.Thread(target=start_file_watcher, args=(watch_directory, json_directory))
    file_watcher_thread.daemon = True
    file_watcher_thread.start()
    
    # 启动Flask应用
    print("启动Flask Web服务器...")
    print("请访问 http://127.0.0.1:5001 查看新闻解析结果")
    app.run(debug=False, host='0.0.0.0', port=5001)

if __name__ == "__main__":
    main()
