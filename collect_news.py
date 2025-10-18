import feedparser
import json
import requests
from datetime import datetime
import os

def load_config():
    """加载配置文件"""
    with open('news_sources.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_rss_news(feed_url):
    """获取RSS新闻"""
    try:
        feed = feedparser.parse(feed_url)
        news = []
        for entry in feed.entries[:5]:
            news.append({
                'title': entry.title,
                'link': entry.get('link', ''),
                'summary': entry.get('summary', '')[:200],
                'published': entry.get('published', '')
            })
        return news
    except Exception as e:
        print(f"❌ RSS获取失败: {e}")
        return []

def filter_news(news_list, config):
    """根据关键词过滤新闻"""
    filters = config.get('filters', {})
    keywords = filters.get('关注行业', []) + filters.get('关注关键词', [])
    blocked = filters.get('屏蔽词', [])
    
    if not keywords:
        filtered = news_list
    else:
        filtered = []
        for news in news_list:
            text = news['title'] + news.get('summary', '')
            if any(kw in text for kw in keywords):
                if not any(bw in text for bw in blocked):
                    filtered.append(news)
    
    seen = set()
    unique_news = []
    for news in filtered:
        if news['title'] not in seen:
            seen.add(news['title'])
            unique_news.append(news)
    
    return unique_news

def format_simple_news(news_list):
    """简单格式化（不使用AI）"""
    result = f"📊 投资快讯 ({datetime.now().strftime('%m-%d %H:%M')})\n\n"
    
    for i, news in enumerate(news_list[:10], 1):
        result += f"{i}. {news['title']}\n"
        if news.get('link'):
            result += f"   🔗 {news['link']}\n"
        result += "\n"
    
    return result

def push_to_bark(bark_url, title, content):
    """推送到Bark（iOS）"""
    try:
        print(f"推送内容: {content}")  # 调试输出，查看推送内容是否为空
        url = f"{bark_url}{requests.utils.quote(title)}"
        params = {
            "body": content[:500],  # 推送的消息内容，最多500个字符
            "sound": "bell",  # 可选，推送铃声
            "group": "投资",  # 可选，推送分组
            "isArchive": "1"  # 使消息能够被存档
        }
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            print("✅ Bark推送成功")
        else:
            print(f"❌ Bark推送失败: {response.text}")
    except Exception as e:
        print(f"❌ Bark异常: {e}")

def main():
    print(f"🚀 投资助手启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    config = load_config()
    
    print("📰 采集财经新闻...")
    all_news = []
    
    for source in config['rss_feeds']:
        if source.get('enabled', True):
            print(f"  📡 {source['name']}")
            news = fetch_rss_news(source['url'])
            all_news.extend(news)
            print(f"     ↳ 获取 {len(news)} 条")
    
    if not all_news:
        print("⚠️  没有获取到新闻")
        return
    
    print(f"\n📝 共收集 {len(all_news)} 条新闻")
    
    filtered_news = filter_news(all_news, config)
    print(f"🔍 过滤后剩余 {len(filtered_news)} 条相关新闻")
    
    report = format_simple_news(filtered_news)
    print(f"📜 推送内容: {report}")
    
    print("✅ 分析完成\n")
    
    print("📤 推送消息...")
    
    bark_url = os.getenv('BARK_URL')
    
    if bark_url:
        push_to_bark(bark_url, "📊 投资快讯", report)
    else:
        print("⚠️  未配置Bark")
    
    print("\n✅ 任务完成！")

if __name__ == "__main__":
    main()
