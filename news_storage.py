import json
import os
import shutil
from datetime import datetime


NEWS_PATH_PARTS = ("Phonix", "ssgsyjy")
CACHE_ROOT_DIR = "cache"
METADATA_SUFFIX = ".meta.json"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_news_data_directory(base_dir):
    """返回新闻原文目录"""
    return os.path.join(base_dir, "newsData", *NEWS_PATH_PARTS)


def ensure_news_data_directory(base_dir):
    """确保新闻原文目录存在"""
    directory = get_news_data_directory(base_dir)
    os.makedirs(directory, exist_ok=True)
    return directory


def normalize_source_json_name(filename):
    """统一转换为JSON文件名"""
    base_name = os.path.basename(filename)
    stem, ext = os.path.splitext(base_name)
    if ext.lower() == ".json":
        return base_name
    return f"{stem}.json"


def get_source_txt_filename(filename):
    """统一转换为新闻原文文件名"""
    source_json_name = normalize_source_json_name(filename)
    return os.path.splitext(source_json_name)[0] + ".txt"


def get_text_metadata_path(txt_file_path):
    """返回新闻原文对应的sidecar元数据文件路径"""
    return f"{txt_file_path}{METADATA_SUFFIX}"


def load_text_metadata(txt_file_path):
    """读取新闻原文sidecar元数据"""
    metadata_path = get_text_metadata_path(txt_file_path)
    if not os.path.exists(metadata_path):
        return {}

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_text_metadata(txt_file_path, metadata):
    """保存新闻原文sidecar元数据"""
    metadata_path = get_text_metadata_path(txt_file_path)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def update_text_metadata(txt_file_path, **updates):
    """更新新闻原文sidecar元数据"""
    metadata = load_text_metadata(txt_file_path)
    metadata.update({key: value for key, value in updates.items() if value is not None})
    save_text_metadata(txt_file_path, metadata)
    return metadata


def get_cached_json_directory(json_directory):
    """返回本地解析缓存目录"""
    return os.path.join(json_directory, CACHE_ROOT_DIR, *NEWS_PATH_PARTS)


def get_cached_json_path(json_directory, filename):
    """返回新闻对应的本地解析缓存JSON路径"""
    source_json_name = normalize_source_json_name(filename)
    return os.path.join(get_cached_json_directory(json_directory), source_json_name)


def get_collection_datetime(file_path, json_directory):
    """从路径或文件修改时间中获取排序所需的采集时间"""
    relative_path = os.path.relpath(file_path, json_directory)
    path_parts = relative_path.split(os.sep)
    if path_parts:
        try:
            return datetime.strptime(path_parts[0], "%Y%m%d")
        except ValueError:
            pass

    return datetime.fromtimestamp(os.path.getmtime(file_path))


def get_json_sort_key(file_path, json_directory):
    """JSON结果文件的排序键"""
    return (
        get_collection_datetime(file_path, json_directory),
        os.path.getmtime(file_path)
    )


def is_path_in_cache_dir(file_path, json_directory):
    """判断路径是否位于本地缓存目录下"""
    cache_directory = os.path.abspath(get_cached_json_directory(json_directory))
    absolute_file_path = os.path.abspath(file_path)
    try:
        return os.path.commonpath([absolute_file_path, cache_directory]) == cache_directory
    except ValueError:
        return False


def find_latest_json_file(json_directory, source_filename, include_cache=True):
    """查找同名新闻对应的最新JSON结果文件"""
    target_filename = normalize_source_json_name(source_filename)
    latest_file = None
    latest_key = None

    for root, _, files in os.walk(json_directory):
        for file in files:
            if file != target_filename:
                continue

            file_path = os.path.join(root, file)
            if not include_cache and is_path_in_cache_dir(file_path, json_directory):
                continue

            sort_key = get_json_sort_key(file_path, json_directory)
            if latest_file is None or sort_key > latest_key:
                latest_file = file_path
                latest_key = sort_key

    return latest_file


def ensure_cached_parse_result(txt_file_path, json_directory):
    """若历史解析结果存在，则同步到本地缓存并返回缓存路径"""
    cached_json_path = get_cached_json_path(json_directory, txt_file_path)
    if os.path.exists(cached_json_path):
        return cached_json_path

    latest_json_path = find_latest_json_file(
        json_directory,
        txt_file_path,
        include_cache=False
    )
    if not latest_json_path:
        return None

    os.makedirs(os.path.dirname(cached_json_path), exist_ok=True)
    shutil.copy2(latest_json_path, cached_json_path)
    return cached_json_path


def write_cached_parse_result(txt_file_path, json_directory, result):
    """将最新解析结果写入本地缓存"""
    cached_json_path = get_cached_json_path(json_directory, txt_file_path)
    os.makedirs(os.path.dirname(cached_json_path), exist_ok=True)
    with open(cached_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return cached_json_path


def collect_seen_links(directory):
    """从sidecar元数据中恢复已经见过的新闻链接"""
    seen_links = set()

    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith(METADATA_SUFFIX):
                continue

            metadata_path = os.path.join(root, file)
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                source_url = metadata.get("source_url")
                if source_url:
                    seen_links.add(source_url)
            except (json.JSONDecodeError, OSError):
                continue

    return seen_links
