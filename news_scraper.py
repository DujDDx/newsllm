import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime

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
                href = a_tag.get('href')
                if href:  # 确保href不为空
                    # 处理相对链接
                    if href.startswith('//'):
                        href = 'https:' + href
                    elif href.startswith('/'):
                        # 如果是相对路径，需要根据基础URL进行处理
                        base_url = url.split('/')[0] + '//' + url.split('/')[2]
                        href = base_url + href
                    
                    links.append(href)
        
        return links
    
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        return []
    except Exception as e:
        print(f"解析错误: {e}")
        return []

def get_even_indexed_links(links):
    """
    从链接列表中选择索引为偶数的链接（基于0索引）
    
    Args:
        links (list): 原始链接列表
        
    Returns:
        list: 包含索引为偶数的链接的新列表
    """
    even_indexed_links = []
    for i in range(len(links)):
        if i % 2 == 0:  # 索引为偶数（0, 2, 4, ...）
            even_indexed_links.append(links[i])
    return even_indexed_links

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
        
        # 使用索引为偶数的链接覆盖原始链接列表
        links = get_even_indexed_links(links)
        print(f"筛选后剩余 {len(links)} 个链接")
        
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