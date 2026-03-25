import requests
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urlparse
import re
from datetime import datetime

from news_storage import (
    TIME_FORMAT,
    collect_seen_links,
    ensure_news_data_directory,
    get_cached_json_path,
    load_text_metadata,
    update_text_metadata
)

# 使用之前找到的BASE_URL
BASE_URL = "https://finance.ifeng.com/shanklist/1-62-305749-"
ARTICLE_URL_PATTERN = re.compile(r"^https?://finance\.ifeng\.com/c/[^/?#]+$")
PUBLISH_TIME_PATTERN = re.compile(r"(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}(?:日)?\s+\d{1,2}:\d{2}:\d{2})")

def create_directory_structure(base_dir=None):
    """创建所需的目录结构"""
    if base_dir is None:
        base_dir = os.path.dirname(__file__)

    directory = ensure_news_data_directory(base_dir)
    return directory

def normalize_link(url, base_url):
    """将链接统一转换为完整URL"""
    if not url:
        return None

    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        parsed_url = urlparse(base_url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}{url}"
    return url


def is_article_link(url):
    """只保留凤凰财经正文页链接，过滤评论页等噪声链接"""
    return bool(url and ARTICLE_URL_PATTERN.match(url))


def deduplicate_links(links):
    """按出现顺序去重"""
    unique_links = []
    seen = set()

    for link in links:
        if link in seen:
            continue
        seen.add(link)
        unique_links.append(link)

    return unique_links


def normalize_publish_datetime(value):
    """将页面里的时间文本统一转成标准格式"""
    if not value:
        return None

    text = re.sub(r"\s+", " ", value).strip()
    match = PUBLISH_TIME_PATTERN.search(text)
    if match:
        text = match.group(1)

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y年%m月%d日 %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime(TIME_FORMAT)
        except ValueError:
            continue

    return None


def extract_article_metadata(soup, html):
    """提取文章页中的来源和作者下方发布时间"""
    metadata = {
        "published_at": None,
        "source_name": None,
        "source_location": None
    }

    source_tag = soup.select_one('div[class*="index_sourceTitleText_"] a, div[class*="index_sourceTitleText_"]')
    if source_tag:
        metadata["source_name"] = source_tag.get_text(" ", strip=True) or None

    time_tag = soup.select_one('div[class*="index_timeBref_"] a, div[class*="index_timeBref_"], time')
    if time_tag:
        time_text = time_tag.get_text(" ", strip=True)
        metadata["published_at"] = normalize_publish_datetime(time_text)
        location_match = re.search(r"(来自\S+)", time_text)
        if location_match:
            metadata["source_location"] = location_match.group(1)

    if not metadata["published_at"]:
        for meta in soup.find_all("meta"):
            meta_name = (meta.get("name") or meta.get("property") or "").strip().lower()
            if meta_name in {"og:time", "article:published_time", "publishdate", "pubdate"}:
                metadata["published_at"] = normalize_publish_datetime(meta.get("content"))
                if metadata["published_at"]:
                    break

    if not metadata["published_at"]:
        news_time_match = re.search(r'"newsTime":"([^"]+)"', html)
        if news_time_match:
            metadata["published_at"] = normalize_publish_datetime(news_time_match.group(1))

    return metadata

def scrape_news_links(url):
    """
    爬取指定URL页面中class=news-stream-newsStream-news-item-infor的div块中的链接
    
    Args:
        url (str): 要爬取的目标网页URL
        
    Returns:
        list: 包含所有找到的链接的列表
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 使用CSS选择器查找目标元素
        news_items = soup.select('div.news-stream-newsStream-news-item-infor')
        
        links = []
        for item in news_items:
            # 查找div中的a标签
            a_tags = item.find_all('a')
            for a_tag in a_tags:
                href = normalize_link(a_tag.get('href'), url)
                if is_article_link(href):
                    links.append(href)

        if not links:
            # 兼容页面结构调整时的兜底策略
            for a_tag in soup.find_all('a', href=True):
                href = normalize_link(a_tag.get('href'), url)
                if is_article_link(href):
                    links.append(href)
        
        return deduplicate_links(links)
    
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        return []
    except Exception as e:
        print(f"解析错误: {e}")
        return []

def extract_filename_from_url(url):
    """
    从URL中提取文件名，基于/c/后的内容
    
    Args:
        url (str): 完整的URL
        
    Returns:
        str: 提取的文件名，如果没有找到/c/则返回时间戳命名
    """
    # 查找/c/后的内容
    match = re.search(r'/c/([^/?#]+)', url)
    if match:
        return match.group(1) + ".txt"
    else:
        # 如果没有找到/c/，使用时间戳作为文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"article_{timestamp}.txt"

def scrape_article_content(url):
    article_data = scrape_article_data(url)
    return article_data.get("content", "")


def scrape_article_data(url, include_content=True):
    """
    爬取文章页面内容，并提取作者名下方的发布时间和正文
    
    Args: 
        url (str): 文章页面URL 
        include_content (bool): 是否提取正文
        
    Returns: 
        dict: 提取后的文章信息
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, 'html.parser')
        metadata = extract_article_metadata(soup, response.text)
        
        content = ""
        if include_content:
            # 查找包含class包含"index_text_"的div块 
            # 使用属性选择器来匹配包含特定文本的class 
            divs = soup.find_all('div', class_=lambda x: x and 'index_text_' in x)
            for div in divs:
                # 获取div中的所有p标签内容 
                p_tags = div.find_all('p')
                for p in p_tags:
                    content += p.get_text().strip() + "\n"

        metadata["content"] = content
        return metadata
    
    except requests.RequestException as e:
        print(f"请求文章页面错误: {e}")
        return {
            "content": "",
            "published_at": None,
            "source_name": None,
            "source_location": None
        }
    except Exception as e:
        print(f"解析文章内容错误: {e}")
        return {
            "content": "",
            "published_at": None,
            "source_name": None,
            "source_location": None
        }


def build_article_url_from_filename(filename):
    """根据新闻文件名重建原始文章链接"""
    article_id = os.path.splitext(os.path.basename(filename))[0]
    if re.fullmatch(r"[A-Za-z0-9]{8,32}", article_id):
        return f"https://finance.ifeng.com/c/{article_id}"
    return None


def ensure_article_metadata(file_path, source_url=None):
    """为已存在新闻补齐来源和发布时间元数据"""
    metadata = load_text_metadata(file_path)
    if metadata.get("published_at"):
        return metadata

    article_url = source_url or metadata.get("source_url") or build_article_url_from_filename(file_path)
    if not article_url:
        return metadata

    article_data = scrape_article_data(article_url, include_content=False)
    if not any(article_data.get(key) for key in ("published_at", "source_name", "source_location")):
        return metadata

    return update_text_metadata(
        file_path,
        source_url=article_url,
        published_at=article_data.get("published_at"),
        source_name=article_data.get("source_name"),
        source_location=article_data.get("source_location")
    )

def save_article_content(content, filename, directory):
    """
    保存文章内容到指定目录下的文件
    
    Args:
        content (str): 文章内容
        filename (str): 文件名
        directory (str): 目录路径
    """
    filepath = os.path.join(directory, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"已保存文章到: {filepath}")
        return True
    except Exception as e:
        print(f"保存文件失败: {e}")
        return False

def monitor_news(base_url, refresh_interval, directory):
    """
    动态监测新闻链接
    
    Args:
        base_url (str): 基础URL
        refresh_interval (int): 刷新间隔（秒）
        directory (str): 保存文件的目录
    """
    seen_links = collect_seen_links(directory)  # 记录已经处理过的链接
    json_directory = os.path.join(os.path.dirname(__file__), "newsJson")
    
    print(f"开始监测新闻，刷新间隔: {refresh_interval} 秒")
    print(f"基础URL: {base_url}")
    print(f"保存目录: {directory}")
    print("按 Ctrl+C 停止监测")
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在检查新新闻...")
            
            # 获取当前所有正文链接
            current_links = scrape_news_links(base_url)
            print(f"找到 {len(current_links)} 个链接")

            # 检查是否有新链接
            new_links = [link for link in current_links if link not in seen_links]
            
            if new_links:
                print(f"发现 {len(new_links)} 个新链接")
                for link in new_links:
                    print(f"处理新链接: {link}")
                    
                    filename = extract_filename_from_url(link)
                    file_path = os.path.join(directory, filename)
                    cached_json_path = get_cached_json_path(json_directory, filename)
                    metadata = load_text_metadata(file_path) if os.path.exists(file_path) else {}

                    if os.path.exists(file_path):
                        update_text_metadata(
                            file_path,
                            source_url=link,
                            source_file=filename,
                            last_seen_at=datetime.now().strftime(TIME_FORMAT),
                            parse_status=metadata.get("parse_status", "pending"),
                            is_parsed=metadata.get("is_parsed", os.path.exists(cached_json_path)),
                            parsed_json_path=metadata.get("parsed_json_path") or (
                                cached_json_path if os.path.exists(cached_json_path) else None
                            )
                        )
                        seen_links.add(link)
                        if metadata.get("is_parsed") or os.path.exists(cached_json_path):
                            print(f"新闻已解析过，直接复用本地结果: {filename}")
                        else:
                            print(f"新闻原文已存在，等待本地解析流程处理: {filename}")
                        continue

                    # 获取正文和发布时间
                    article_data = scrape_article_data(link)
                    content = article_data.get("content", "")
                    if content:
                        # 保存内容
                        if save_article_content(content, filename, directory):
                            update_text_metadata(
                                file_path,
                                source_url=link,
                                source_file=filename,
                                scrape_status="downloaded",
                                parse_status="pending",
                                is_parsed=False,
                                parsed_json_path=None,
                                scraped_at=datetime.now().strftime(TIME_FORMAT),
                                last_seen_at=datetime.now().strftime(TIME_FORMAT),
                                published_at=article_data.get("published_at"),
                                source_name=article_data.get("source_name"),
                                source_location=article_data.get("source_location")
                            )
                            # 添加到已处理集合
                            seen_links.add(link)
                            print(f"成功保存新闻原文，等待解析: {filename}")
                        else:
                            print(f"保存新闻原文失败: {filename}")
                    else:
                        print(f"无法获取链接内容或内容为空: {link}")
                    # 短暂延迟以避免过于频繁的请求
                    time.sleep(1)
            else:
                print("没有发现新链接")
            
            # 更新已知链接集合
            seen_links.update(current_links)
            
            print(f"等待 {refresh_interval} 秒后再次检查...")
            time.sleep(refresh_interval)
            
        except KeyboardInterrupt:
            print("\n用户停止监测")
            break
        except Exception as e:
            print(f"监测过程中发生错误: {e}")
            print(f"将在 {refresh_interval} 秒后重试...")
            time.sleep(refresh_interval)

def main():
    # 创建目录结构
    directory = create_directory_structure()
    
    # 获取用户输入的刷新间隔
    try:
        refresh_interval = int(input("请输入刷新间隔（秒）: "))
        if refresh_interval <= 0:
            refresh_interval = 30  # 默认30秒
            print("无效输入，使用默认刷新间隔: 30秒")
    except ValueError:
        refresh_interval = 30  # 默认30秒
        print("无效输入，使用默认刷新间隔: 30秒")
    
    # 开始监测
    monitor_news(BASE_URL, refresh_interval, directory)

if __name__ == "__main__":
    main()
