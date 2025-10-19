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
        for entry in feed.entries[:3]:  # 每个源只取3条，避免太多
            news.append({
                'title': entry.title,
                'link': entry.get('link', ''),
                'summary': entry.get('summary', '')[:100],
                'published': entry.get('published', '')
            })
        return news
    except Exception as e:
        print(f"❌ RSS获取失败 {feed_url}: {e}")
        return []

def filter_news(news_list, config):
    """根据关键词过滤新闻"""
    filters = config.get('filters', {})
    keywords = filters.get('关注行业', []) + filters.get('关注关键词', [])
    blocked = filters.get('屏蔽词', [])
    
    # 如果没有设置关键词，返回所有新闻（限制数量）
    if not keywords:
        print("⚠️  未设置过滤关键词，返回所有新闻")
        return news_list[:20]  # 最多20条
    
    filtered = []
    for news in news_list:
        text = news['title'] + news.get('summary', '')
        
        # 检查是否包含关注关键词
        if any(kw in text for kw in keywords):
            # 排除屏蔽词
            if not any(bw in text for bw in blocked):
                filtered.append(news)
    
    # 去重
    seen = set()
    unique_news = []
    for news in filtered:
        if news['title'] not in seen:
            seen.add(news['title'])
            unique_news.append(news)
    
    return unique_news[:15]  # 最多返回15条

def format_news(news_list):
    """格式化新闻为推送内容"""
    if not news_list:
        return "暂无符合条件的新闻"
    
    result = f"📊 投资快讯 ({datetime.now().strftime('%m-%d %H:%M')})\n\n"
    
    for i, news in enumerate(news_list[:10], 1):
        # 标题
        result += f"{i}. {news['title']}\n"
        
        # 链接（可选）
        # if news.get('link'):
        #     result += f"🔗 {news['link']}\n"
        
        result += "\n"
    
    result += f"\n共 {len(news_list)} 条相关新闻"
    
    return result

def push_to_bark(bark_url, title, content):
    """推送到Bark（iOS）"""
    try:
        # 确保URL格式正确
        if not bark_url.endswith('/'):
            bark_url += '/'
        
        # 调试输出
        print(f"\n📡 准备推送到Bark")
        print(f"📝 标题: {title}")
        print(f"📝 内容长度: {len(content)} 字符")
        print(f"📝 内容预览: {content[:100]}...")
        
        # Bark API 格式：GET请求
        encoded_title = requests.utils.quote(title)
        encoded_body = requests.utils.quote(content[:1000])  # 限制1000字符
        
        # 方式1：URL参数（推荐）
        full_url = f"{bark_url}{encoded_title}/{encoded_body}"
        params = {
            "sound": "bell",
            "group": "投资",
            "isArchive": "1"
        }
        
        print(f"🌐 请求URL: {bark_url}{encoded_title}/...")
        
        response = requests.get(full_url, params=params, timeout=15)
        
        print(f"📊 响应状态: {response.status_code}")
        print(f"📊 响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                print("✅ Bark推送成功")
                return True
            else:
                print(f"❌ Bark返回错误: {result}")
                return False
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Bark推送异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print(f"🚀 投资助手启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 加载配置
    try:
        config = load_config()
        print("✅ 配置文件加载成功")
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        return
    
    # 2. 采集新闻
    print("\n📰 开始采集新闻...")
    all_news = []
    success_count = 0
    
    for source in config['rss_feeds']:
        if not source.get('enabled', True):
            continue
            
        print(f"  📡 {source['name']}", end=" ")
        news = fetch_rss_news(source['url'])
        
        if news:
            all_news.extend(news)
            success_count += 1
            print(f"✅ {len(news)}条")
        else:
            print(f"⚠️  0条")
    
    print(f"\n📊 成功采集 {success_count} 个源，共 {len(all_news)} 条新闻")
    
    if not all_news:
        print("❌ 没有获取到任何新闻，退出")
        return
    
    # 3. 过滤新闻
    print("\n🔍 过滤新闻...")
    filtered_news = filter_news(all_news, config)
    print(f"✅ 过滤后剩余 {len(filtered_news)} 条")
    
    if not filtered_news:
        print("⚠️  没有符合条件的新闻")
        # 如果没有符合条件的，发送前10条
        filtered_news = all_news[:10]
        print(f"📋 改为发送最新的 {len(filtered_news)} 条")
    
    # 4. 格式化内容
    report = format_news(filtered_news)
    print(f"\n📄 生成报告完成，长度: {len(report)} 字符")
    
    # 5. 推送
    print("\n📤 开始推送...")
    bark_url = os.getenv('BARK_URL')
    
    if not bark_url:
        print("❌ 未配置 BARK_URL")
        print("📄 报告内容:")
        print(report)
        return
    
    print(f"📱 Bark URL: {bark_url[:40]}...")
    
    success = push_to_bark(bark_url, "📊 投资快讯", report)
    
    if success:
        print("\n✅ 任务完成！推送成功")
    else:
        print("\n⚠️  任务完成，但推送可能失败")
        print("\n报告内容:")
        print(report[:500])

if __name__ == "__main__":
    main()
```

---

## 📝 修改要点

### 1. **改进了过滤逻辑**
- 如果没有符合关键词的新闻，自动发送最新10条
- 避免推送空内容

### 2. **优化了推送格式**
- 使用 `{bark_url}{title}/{body}` 格式
- 内容限制1000字符，避免太长

### 3. **增强了调试信息**
- 详细输出每一步的状态
- 显示推送内容预览

---

## 🚀 测试步骤

### 1. 更新代码
在 GitHub 仓库：
1. 点击 `collect_news.py`
2. 点击编辑（✏️）
3. 全选删除旧代码
4. 粘贴上面的新代码
5. Commit changes

### 2. 手动运行
1. 进入 Actions 页面
2. 点击 `投资助手`
3. Run workflow
4. 等待运行完成

### 3. 查看日志
展开 "运行助手" 步骤，应该看到：
```
🚀 投资助手启动
📰 开始采集新闻...
  📡 新华社-财经 ✅ 3条
  📡 新浪财经 ✅ 3条
  ...
📊 成功采集 10 个源，共 30 条新闻
🔍 过滤新闻...
✅ 过滤后剩余 15 条
📄 生成报告完成，长度: 856 字符
📤 开始推送...
📝 内容预览: 📊 投资快讯 (10-18 21:50)...
✅ Bark推送成功
