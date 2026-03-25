import requests
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urlparse
import re
from datetime import datetime

# 使用之前找到的BASE_URL
BASE_URL = "https://finance.ifeng.com/shanklist/1-62-305749-"

def create_directory_structure():
    """创建所需的目录结构"""
    directory = "/Users/yichen/Documents/LLM_NewsWeaver/newsData/Phonix/ssgsyjy/"
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"已创建目录: {directory}")
    return directory

def get_even_indexed_links(links):
    """
    获取索引为偶数的链接（过滤掉索引为奇数的链接）
    
    Args:
        links (list): 原始链接列表
        
    Returns:
        list: 索引为偶数的链接列表
    """
    # 只保留索引为偶数的链接（0, 2, 4, ...）
    even_indexed_links = [link for i, link in enumerate(links) if i % 2 == 0]
    return even_indexed_links

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
                href = a_tag.get('href')
                if href:
                    # 处理相对链接
                    if href.startswith('//'):
                        href = 'https:' + href
                    elif href.startswith('/'):
                        parsed_url = urlparse(url)
                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        href = base_url + href
                    
                    links.append(href)
        
        return links
    
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
    """
    爬取文章页面内容，提取包含class包含"index_text_"的div块中的所有p标签内容 
    
    Args: 
        url (str): 文章页面URL 
        
    Returns: 
        str: 提取的文章内容 
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找包含class包含"index_text_"的div块 
        # 使用属性选择器来匹配包含特定文本的class 
        divs = soup.find_all('div', class_=lambda x: x and 'index_text_' in x)
        
        content = ""
        for div in divs:
            # 获取div中的所有p标签内容 
            p_tags = div.find_all('p')
            for p in p_tags:
                content += p.get_text().strip() + "\n"
        
        return content
    
    except requests.RequestException as e:
        print(f"请求文章页面错误: {e}")
        return ""
    except Exception as e:
        print(f"解析文章内容错误: {e}")
        return ""

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
    seen_links = set()  # 记录已经处理过的链接
    
    print(f"开始监测新闻，刷新间隔: {refresh_interval} 秒")
    print(f"基础URL: {base_url}")
    print(f"保存目录: {directory}")
    print("按 Ctrl+C 停止监测")
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在检查新新闻...")
            
            # 获取当前所有链接
            current_links = scrape_news_links(base_url)
            print(f"找到 {len(current_links)} 个链接")
            
            # 过滤掉索引为奇数的链接，只保留索引为偶数的链接
            filtered_links = get_even_indexed_links(current_links)
            print(f"过滤后剩余 {len(filtered_links)} 个链接（仅索引为偶数的链接）")
            
            # 检查是否有新链接
            new_links = [link for link in filtered_links if link not in seen_links]
            
            if new_links:
                print(f"发现 {len(new_links)} 个新链接")
                for link in new_links:
                    print(f"处理新链接: {link}")
                    
                    # 使用修改后的函数获取文章内容
                    content = scrape_article_content(link)
                    if content:
                        # 提取文件名
                        filename = extract_filename_from_url(link)
                        # 保存内容
                        save_article_content(content, filename, directory)
                        # 添加到已处理集合
                        seen_links.add(link)
                        print(f"成功解析并保存文章内容: {filename}")
                    else:
                        print(f"无法获取链接内容或内容为空: {link}")
                    # 短暂延迟以避免过于频繁的请求
                    time.sleep(1)
            else:
                print("没有发现新链接")
            
            # 更新已知链接集合（使用过滤后的链接）
            seen_links.update(filtered_links)
            
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