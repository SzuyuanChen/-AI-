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
        for entry in feed.entries[:5]:  # 每个源取最新5条
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
        # 如果没有设置关键词，返回所有新闻
        filtered = news_list
    else:
        # 过滤包含关键词的新闻
        filtered = []
        for news in news_list:
            text = news['title'] + news.get('summary', '')
            
            # 检查是否包含关注关键词
            if any(kw in text for kw in keywords):
                # 排除屏蔽词
                if not any(bw in text for bw in blocked):
                    filtered.append(news)
    
    # 去重（基于标题）
    seen = set()
    unique_news = []
    for news in filtered:
        if news['title'] not in seen:
            seen.add(news['title'])
            unique_news.append(news)
    
    return unique_news

def analyze_with_claude(news_list):
    """使用Claude分析新闻"""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        print("⚠️  未配置Claude API，使用简单格式化")
        return format_simple_news(news_list)
    
    # 组装新闻文本
    news_text = "\n\n".join([
        f"标题: {n['title']}\n链接: {n['link']}"
        for n in news_list[:15]  # 最多分析15条
    ])
    
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [{
                    "role": "user",
                    "content": f"""分析以下财经新闻，提取最重要的5-8条信息：

对每条新闻用一句话总结核心要点，并标注：
🔴 高度重要 🟡 中等重要 🟢 一般信息

新闻内容：
{news_text}

要求：
1. 简洁专业，适合手机推送
2. 突出市场影响
3. 总字数控制在500字内"""
                }]
            },
            timeout=30
        )
        
        result = response.json()
        if 'content' in result:
            return result['content'][0]['text']
        else:
            print(f"⚠️  Claude返回异常: {result}")
            return format_simple_news(news_list)
            
    except Exception as e:
        print(f"❌ Claude分析失败: {e}")
        return format_simple_news(news_list)

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
        url = f"{bark_url}/{requests.utils.quote(title)}"
        params = {
            "body": content[:500],
            "sound": "bell",
            "group": "投资",
            "isArchive": "1"
        }
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            print("✅ Bark推送成功")
        else:
            print(f"❌ Bark推送失败: {response.text}")
    except Exception as e:
        print(f"❌ Bark异常: {e}")

def push_to_telegram(bot_token, chat_id, content):
    """推送到Telegram"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = requests.post(url, json={
            "chat_id": chat_id,
            "text": content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram推送成功")
        else:
            print(f"❌ Telegram推送失败")
    except Exception as e:
        print(f"❌ Telegram异常: {e}")

def main():
    print(f"🚀 投资助手启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 加载配置
    config = load_config()
    
    # 2. 采集新闻
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
    
    # 3. 过滤新闻
    filtered_news = filter_news(all_news, config)
    print(f"🔍 过滤后剩余 {len(filtered_news)} 条相关新闻")
    
    # 4. AI分析
    print("\n🤖 AI分析中...")
    report = analyze_with_claude(filtered_news)
    print("✅ 分析完成\n")
    
    # 5. 推送消息
    print("📤 推送消息...")
    
    bark_url = os.getenv('BARK_URL')
    tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
    tg_chat = os.getenv('TELEGRAM_CHAT_ID')
    
    if bark_url:
        push_to_bark(bark_url, "📊 投资快讯", report)
    else:
        print("⚠️  未配置Bark")
    
    if tg_token and tg_chat:
        push_to_telegram(tg_token, tg_chat, report)
    else:
        print("⚠️  未配置Telegram")
    
    print("\n✅ 任务完成！")

if __name__ == "__main__":
    main()
