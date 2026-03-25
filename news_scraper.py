import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime
import re
from urllib.parse import urlparse


ARTICLE_URL_PATTERN = re.compile(r"^https?://finance\.ifeng\.com/c/[^/?#]+$")


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
    """过滤出凤凰财经正文页链接"""
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

def scrape_news_links(url):
    """
    爬取指定URL页面中class=news-stream-newsStream-news-item-infor的div块中的链接
    
    Args:
        url (str): 要爬取的目标网页URL
        
    Returns:
        list: 包含所有找到的链接的列表
    """
    # 设置请求头，模拟浏览器访问
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # 发送HTTP请求
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 如果响应状态码不是200会抛出异常
        response.encoding = response.apparent_encoding  # 自动检测编码
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 使用CSS选择器查找目标元素
        # 查找class=news-stream-newsStream-news-item-infor的div块
        news_items = soup.select('div.news-stream-newsStream-news-item-infor')
        
        links = []
        # 遍历每个找到的div块，提取其中的a标签href属性
        for item in news_items:
            # 查找div中的a标签
            a_tags = item.find_all('a')
            for a_tag in a_tags:
                href = normalize_link(a_tag.get('href'), url)
                if is_article_link(href):
                    links.append(href)

        if not links:
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
        response = requests.get(url, headers=headers)
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

def save_content_to_file(content, timestamp):
    """
    将内容保存到以时间戳命名的文本文件中
    
    Args:
        content (str): 要保存的内容
        timestamp (str): 时间戳字符串，用作文件名
    """
    filename = f"article_content_{timestamp}.txt"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"内容已保存到文件: {filename}")
    except Exception as e:
        print(f"保存文件时出错: {e}")

def main():
    # 使用您已有的BASE_URL作为示例
    base_url = "https://finance.ifeng.com/shanklist/1-62-305749-"
    
    print("开始爬取新闻链接...")
    links = scrape_news_links(base_url)
    
    if links:
        print(f"找到 {len(links)} 个链接")
        
        # 对每个链接进行进一步解析
        all_content = ""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, link in enumerate(links):
            print(f"正在处理链接 {i+1}/{len(links)}: {link}")
            content = scrape_article_content(link)
            if content:
                all_content += f"\n=== 文章 {i+1} ===\n{content}\n"
            else:
                print(f"未能从链接 {link} 提取内容")
            # 添加延迟以避免过于频繁的请求
            time.sleep(1)
        
        # 将所有内容保存到文件
        if all_content:
            save_content_to_file(all_content, timestamp)
        else:
            print("未能从任何链接提取到内容")
    else:
        print("未找到任何链接")

if __name__ == "__main__":
    main()
