"""
Urbanista Monday Brief — Agent
Images fetched directly from source articles via web search.
No external image API needed.
"""

import os, sys, json, datetime, re, requests, anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed

MODEL = "claude-sonnet-4-6"

URBANISTA_CONTEXT = """
Urbanista is a Stockholm-based premium consumer audio brand founded in 2010.
Company size: ~15 people split between Stockholm (product, brand, commercial) and Shenzhen (PM, supplier, production).

Product portfolio and pipeline:
- Shibuya: on-ear headphones, $49 Essential tier, launching Aug 2026
- Miami 2: over-ear headphones, €149 Signature tier, launching Oct 2026
- Palo Alto 2: TWS earphones, $99 Premium tier, launching Jan 2027

Three brand pillars: Design-led, Effortless, Accessible.
Three price tiers: Essential (~$49), Core (~$99), Signature (~$149+).
Distribution: 90+ countries, ~30,000 retail locations globally.
Key markets: North America, Europe (Nordics, DE, FR, UK), Australia, New Zealand.

Strategic priorities:
- Premiumisation: moving mix toward Signature tier, reducing Action retail exposure
- Brand building: Scandinavian design heritage, urban lifestyle positioning
- Market expansion: strengthening DE, FR, UK, AU/NZ
- Compliance: active in EU, US, CA, AU/NZ

Key competitive threats: Sony, Bose (premium), Nothing, Sudio (brand/design),
Soundcore/JLab (price), Marshall (lifestyle/heritage).

Key opportunities: travel retail, DTC editorial content, Nordic premium brand story,
Harman EU shelf opening, premium gifting occasions.
"""

def get_date_context():
    now = datetime.datetime.now()
    week_start = now - datetime.timedelta(days=7)
    return {
        "today": now.strftime("%B %d, %Y"),
        "week_start": week_start.strftime("%B %d, %Y"),
        "month": now.strftime("%B %Y"),
        "year": str(now.year)
    }

ITEM_TEMPLATE = '{"tag":"region","headline":"news headline","body":"2 sentences.","date":"May 5, 2026","url":"https://article-url.com","source":"Publisher","image_url":"https://image-from-article.com/image.jpg"}'

def make_sections(d):
    items_template = ",".join([ITEM_TEMPLATE] * 5)
    base = f'{{"items":[{items_template}]}}'

    return [
        {
            "key": "market",
            "label": "Market Update",
            "emoji": "🌍",
            "prompt": f'Today is {d["today"]}. Search for news published in the past 7 days (after {d["week_start"]}) about the consumer audio market — headphones, earphones, Bluetooth speakers — in North America, Europe, UK, Australia and New Zealand. Search for: "headphone market {d["month"]}", "audio sales {d["month"]}", "consumer electronics news {d["month"]}". Find 5 actual recent news stories. For each story, also fetch the article page and extract the main Open Graph image URL (og:image meta tag) from the article. Include the publication date. Return ONLY this JSON with no other text:\n{base}'
        },
        {
            "key": "product",
            "label": "Product News",
            "emoji": "🎯",
            "prompt": f'Today is {d["today"]}. Search for news published in the past 7 days (after {d["week_start"]}) about these audio brands: Nothing, JLab, JBL, Soundcore, Marshall, Sudio. Search for: "Nothing audio {d["month"]}", "JBL {d["month"]}", "Soundcore {d["month"]}", "Marshall {d["month"]}", "Sudio {d["month"]}". Find 5 actual recent news stories. For each story, fetch the article page and extract the main Open Graph image URL (og:image meta tag). Include the publication date. Return ONLY this JSON with no other text:\n{base}'
        },
        {
            "key": "retail",
            "label": "Retail",
            "emoji": "🏪",
            "prompt": f'Today is {d["today"]}. Search for news published in the past 7 days (after {d["week_start"]}) about consumer electronics retail — Best Buy, MediaMarkt, Currys, Amazon audio, DTC ecommerce, airport retail. Search for: "Best Buy {d["month"]}", "Amazon electronics {d["month"]}", "retail consumer electronics {d["month"]}". Find 5 actual recent news stories. For each, fetch the article and extract the og:image URL. Include publication date. Return ONLY this JSON with no other text:\n{base}'
        },
        {
            "key": "compliance",
            "label": "Compliance",
            "emoji": "⚖️",
            "prompt": f'Today is {d["today"]}. Search for regulatory and compliance news published in the past 7 days (after {d["week_start"]}) affecting consumer electronics in EU, US, UK, Canada, Australia. Search for: "FCC {d["month"]}", "EU electronics regulation {d["month"]}", "consumer electronics compliance {d["month"]}", "battery regulation {d["month"]}". Find 5 actual recent regulatory updates. For each, fetch the page and extract the og:image URL. Include publication date. Return ONLY this JSON with no other text:\n{base}'
        },
        {
            "key": "ai",
            "label": "AI Tips & Tricks",
            "emoji": "✦",
            "prompt": f'Today is {d["today"]}. Search for AI news and tips published in the past 7 days (after {d["week_start"]}) relevant to small businesses and product companies. Search for: "AI small business {d["month"]}", "Claude {d["month"]}", "ChatGPT productivity {d["month"]}", "AI tools {d["month"]}". Find 5 actionable recent AI tips. For each, fetch the article and extract the og:image URL. Include publication date. Return ONLY this JSON with no other text:\n{base}'
        }
    ]


def research_section(section):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    print(f"  → {section['emoji']} {section['label']}...")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": section["prompt"]}]
        )
        text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text.strip()]
        for text in reversed(text_blocks):
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                try:
                    result = json.loads(text[start:end])
                    if result.get("items"):
                        result["items"] = result["items"][:5]
                        print(f"    ✓ {section['label']}: {len(result['items'])} items")
                        return section["key"], result
                except json.JSONDecodeError:
                    pass
        print(f"    ⚠️  No valid JSON found")
        return section["key"], {"items": []}
    except Exception as e:
        print(f"    ⚠️  Exception: {e}")
        return section["key"], {"items": []}


def generate_intro(client, results, sections):
    print("  → ✍️  Writing intro...")
    headlines = []
    for section in sections[:3]:
        items = results.get(section["key"], {}).get("items", [])
        if items:
            headlines.append(items[0].get("headline", ""))
    prompt = f"Write a 2-sentence editorial intro for Urbanista's Monday Brief — a weekly intelligence report for a premium audio brand. Tone: sharp, informed, like a smart colleague summarising the week. Based on these top stories: {' | '.join(headlines)}. Respond with ONLY the 2 sentences, nothing else."
    try:
        response = client.messages.create(
            model=MODEL, max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"    ⚠️  Intro error: {e}")
        return "Another week of signals worth reading. Here's what moved in audio, retail, compliance, and AI."


def generate_signals(client, results, sections):
    print("  → 🧠 Generating strategic signals...")
    all_news = []
    for section in sections:
        items = results.get(section["key"], {}).get("items", [])
        for item in items:
            all_news.append(f"[{section['label']}] {item.get('headline', '')}: {item.get('body', '')}")

    news_summary = "\n".join(all_news[:20])

    prompt = f"""You are a senior strategy advisor to Urbanista, a premium audio brand.

Here is everything you need to know about Urbanista:
{URBANISTA_CONTEXT}

Here is this week's market intelligence:
{news_summary}

Identify exactly 3 strategic signals that Urbanista's leadership team should act on or monitor this week.
Each signal must be specific to Urbanista, tied to this week's news, and actionable.

Return ONLY this JSON with no other text:
{{"signals":[{{"headline":"signal headline","body":"Context and what Urbanista should do. 2 sentences.","urgency":"High|Medium|Watch"}},{{"headline":"signal headline","body":"2 sentences.","urgency":"High|Medium|Watch"}},{{"headline":"signal headline","body":"2 sentences.","urgency":"High|Medium|Watch"}}]}}"""

    try:
        response = client.messages.create(
            model=MODEL, max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text.strip()]
        for text in reversed(text_blocks):
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                try:
                    result = json.loads(text[start:end])
                    if result.get("signals"):
                        print(f"    ✓ {len(result['signals'])} signals generated")
                        return result["signals"]
                except json.JSONDecodeError:
                    pass
        return []
    except Exception as e:
        print(f"    ⚠️  Signals error: {e}")
        return []


def build_card(results, intro, signals, date_str, edition, sections):
    def image_block(url):
        if url and url.startswith("http"):
            return [{"type": "Image", "url": url, "size": "Stretch",
                     "altText": "Article image", "spacing": "Small"}]
        return []

    body = [
        {"type": "TextBlock", "text": f"URBANISTA MONDAY BRIEF · {edition}",
         "weight": "Bolder", "size": "Medium", "wrap": True},
        {"type": "TextBlock", "text": date_str,
         "isSubtle": True, "size": "Small", "spacing": "None"},
        {"type": "TextBlock", "text": intro,
         "wrap": True, "size": "Medium", "spacing": "Medium", "isSubtle": True}
    ]

    for section in sections:
        items = results.get(section["key"], {}).get("items", [])
        body.append({
            "type": "TextBlock",
            "text": f"{section['emoji']} {section['label'].upper()}",
            "weight": "Bolder", "size": "Small",
            "color": "Accent", "spacing": "Large", "separator": True
        })
        if not items:
            body.append({"type": "TextBlock", "text": "_No updates this week_",
                         "isSubtle": True, "size": "Small"})
            continue

        # Lead item with image
        lead = items[0]
        body += image_block(lead.get("image_url", ""))
        body.append({"type": "TextBlock",
                     "text": f"**{lead.get('headline', '')}**",
                     "wrap": True, "spacing": "Small"})
        body.append({"type": "TextBlock",
                     "text": lead.get("body", ""),
                     "wrap": True, "isSubtle": True, "size": "Small", "spacing": "Small"})
        date_item = lead.get("date", "")
        footer = f"_{lead.get('tag', '')}_"
        if date_item:
            footer += f" · {date_item}"
        footer += f" · [{lead.get('source', 'Source')}]({lead.get('url', '#')})"
        body.append({"type": "TextBlock", "text": footer,
                     "wrap": True, "size": "ExtraSmall",
                     "color": "Accent", "spacing": "Small"})

        # Remaining items — smaller, thumbnail image in column
        for item in items[1:]:
            img_url = item.get("image_url", "")
            if img_url and img_url.startswith("http"):
                col_set = {
                    "type": "ColumnSet",
                    "spacing": "Medium",
                    "columns": [
                        {
                            "type": "Column", "width": "80px",
                            "items": [{"type": "Image", "url": img_url,
                                       "size": "Stretch", "altText": "thumbnail"}]
                        },
                        {
                            "type": "Column", "width": "stretch",
                            "items": [
                                {"type": "TextBlock",
                                 "text": f"**{item.get('headline', '')}**",
                                 "wrap": True, "size": "Small"},
                                {"type": "TextBlock",
                                 "text": item.get("body", ""),
                                 "wrap": True, "isSubtle": True,
                                 "size": "ExtraSmall", "spacing": "Small"},
                                {"type": "TextBlock",
                                 "text": f"_{item.get('tag', '')}_ · {item.get('date', '')} · [{item.get('source', 'Source')}]({item.get('url', '#')})",
                                 "wrap": True, "size": "ExtraSmall",
                                 "color": "Accent", "spacing": "Small"}
                            ]
                        }
                    ]
                }
                body.append(col_set)
            else:
                body.append({"type": "TextBlock",
                             "text": f"**{item.get('headline', '')}**",
                             "wrap": True, "spacing": "Medium"})
                body.append({"type": "TextBlock",
                             "text": item.get("body", ""),
                             "wrap": True, "isSubtle": True,
                             "size": "Small", "spacing": "Small"})
                footer = f"_{item.get('tag', '')}_"
                if item.get("date"):
                    footer += f" · {item['date']}"
                footer += f" · [{item.get('source', 'Source')}]({item.get('url', '#')})"
                body.append({"type": "TextBlock", "text": footer,
                             "wrap": True, "size": "ExtraSmall",
                             "color": "Accent", "spacing": "Small"})

    # Signals section
    if signals:
        urgency_color = {"High": "Attention", "Medium": "Warning", "Watch": "Accent"}
        urgency_emoji = {"High": "🔴", "Medium": "🟡", "Watch": "🔵"}
        body.append({
            "type": "TextBlock",
            "text": "🧠 THIS WEEK'S SIGNALS — FOR URBANISTA",
            "weight": "Bolder", "size": "Small",
            "color": "Warning", "spacing": "Large", "separator": True
        })
        body.append({
            "type": "TextBlock",
            "text": "Strategic implications of this week's news, specific to Urbanista.",
            "wrap": True, "isSubtle": True, "size": "Small", "spacing": "Small"
        })
        for signal in signals:
            urgency = signal.get("urgency", "Watch")
            body.append({
                "type": "TextBlock",
                "text": f"{urgency_emoji.get(urgency, '⚪')} **{signal.get('headline', '')}**",
                "wrap": True, "spacing": "Medium",
                "color": urgency_color.get(urgency, "Default")
            })
            body.append({
                "type": "TextBlock",
                "text": signal.get("body", ""),
                "wrap": True, "isSubtle": True, "size": "Small", "spacing": "Small"
            })
            body.append({
                "type": "TextBlock",
                "text": f"_{urgency} priority_",
                "wrap": True, "size": "ExtraSmall",
                "color": urgency_color.get(urgency, "Default"), "spacing": "Small"
            })

    body.append({"type": "TextBlock",
                 "text": "Urbanista Monday Brief · Every Monday 08:00 CET · 100% AI researched · Past 7 days",
                 "size": "ExtraSmall", "isSubtle": True,
                 "spacing": "Large", "separator": True})

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.4", "body": body
            }
        }]
    }


def main():
    dry_run = "--dry-run" in sys.argv

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set."); sys.exit(1)
    if not os.environ.get("TEAMS_WEBHOOK_URL") and not dry_run:
        print("Error: TEAMS_WEBHOOK_URL not set."); sys.exit(1)

    now = datetime.datetime.now()
    date_str = now.strftime("%A, %-d %B %Y")
    edition = f"W{now.isocalendar()[1]} · {now.year}"
    d = get_date_context()
    sections = make_sections(d)

    print(f"\n📰 Urbanista Monday Brief — {date_str}")
    print(f"   News window: {d['week_start']} → {d['today']}")
    print("=" * 52)
    print("\n[1/3] Running all sections in parallel...")

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(research_section, s): s for s in sections}
        for future in as_completed(futures):
            key, data = future.result()
            results[key] = data

    print("\n[2/3] Writing intro and generating signals...")
    intro = generate_intro(client, results, sections)
    signals = generate_signals(client, results, sections)

    print("\n[3/3] Building card and posting...")
    card = build_card(results, intro, signals, date_str, edition, sections)

    if dry_run:
        print("\n── DRY RUN ──")
        print(f"\nIntro: {intro}\n")
        for section in sections:
            items = results[section["key"]].get("items", [])
            print(f"\n{section['emoji']} {section['label']} ({len(items)} items)")
            for item in items:
                has_image = "🖼️" if item.get("image_url", "").startswith("http") else "❌"
                print(f"  {has_image} [{item.get('date','')}] {item.get('headline','')}")
        print("\n🧠 Signals:")
        for s in signals:
            print(f"  {'🔴' if s.get('urgency')=='High' else '🟡' if s.get('urgency')=='Medium' else '🔵'} {s.get('headline','')}")
    else:
        r = requests.post(os.environ["TEAMS_WEBHOOK_URL"], json=card,
                          headers={"Content-Type": "application/json"}, timeout=30)
        r.raise_for_status()
        print(f"  ✓ Posted (HTTP {r.status_code})")

    print(f"\n✓ Done — {edition}\n")


if __name__ == "__main__":
    main()
