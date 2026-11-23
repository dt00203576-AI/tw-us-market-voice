import os
import subprocess
import requests
import pandas as pd
import yfinance as yf

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

def get_index_info(symbol, name, calc_ma=False):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2mo" if calc_ma else "5d")
        if len(hist) >= 2:
            curr = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            diff = curr - prev
            pct = (diff / prev) * 100
            date_str = hist.index[-1].strftime("%m/%d")
            
            res = {
                "name": name,
                "date": date_str,
                "close": curr,
                "diff": diff,
                "pct": pct,
                "ok": True
            }
            if calc_ma and len(hist) >= 20:
                res["ma5"] = float(hist["Close"].tail(5).mean())
                res["ma20"] = float(hist["Close"].tail(20).mean())
            return res
    except Exception:
        pass
    return {"name": name, "ok": False}

def analyze_tw_trend(twii, twoii, tsmc):
    if not twii["ok"]:
        return "🟡 暫無最新台股大盤數據", "台北股市暫無最新數據。"

    curr = twii["close"]
    ma5 = twii.get("ma5", curr)
    ma20 = twii.get("ma20", curr)

    if curr > ma5 and curr > ma20:
        status_badge = "🟢 強勢多頭（站穩5日線與月線）"
        status_speech = f"台北股市目前處於強勢多頭格局，加權指數站穩五日均線 {int(round(ma5))} 點，以及二十日月線 {int(round(ma20))} 點之上。"
    elif curr < ma5 and curr >= ma20:
        status_badge = "🟡 高檔震盪（守穩20日月線支撐）"
        status_speech = f"台北股市目前呈現高檔震盪整理，指數雖略低於五日線，但仍守穩在二十日月線 {int(round(ma20))} 點支撐之上。"
    elif curr >= ma5 and curr < ma20:
        status_badge = "🟠 跌深反彈（站回5日線挑戰月線）"
        status_speech = f"台北股市展開短線反彈，已重新站回五日均線 {int(round(ma5))} 點，上方正準備挑戰二十日月線壓力。"
    else:
        status_badge = "🔴 短線偏空（跌破5日線與月線）"
        status_speech = f"台北股市短線走勢偏空修正，目前指數位於五日線與二十日月線 {int(round(ma20))} 點之下，操作宜保守應對。"

    structure_note = ""
    if twoii["ok"] and tsmc["ok"]:
        if twii["pct"] > 0 and twoii["pct"] > 0:
            structure_note = "前一交易日大型權值股與中小型櫃買指數同步收紅，市場資金動能健康。"
        elif twii["pct"] > 0 and twoii["pct"] < 0:
            structure_note = "前一交易日呈現拉積盤結構，主要由權值股撐盤，中小型股相對弱勢。"
        elif twii["pct"] < 0 and twoii["pct"] > 0:
            structure_note = "前一交易日權值股休息，但中小型櫃買指數逆勢走強，內資人氣仍在。"

    return status_badge, f"{status_speech} {structure_note}".strip()

def build_macro_report():
    twii = get_index_info("^TWII", "台灣加權指數", calc_ma=True)
    twoii = get_index_info("^TWOII", "櫃買指數(OTC)", calc_ma=False)
    tsmc = get_index_info("2330.TW", "台積電", calc_ma=False)
    
    sox = get_index_info("^SOX", "費城半導體")
    ixic = get_index_info("^IXIC", "那斯達克")
    gspc = get_index_info("^GSPC", "標普500")
    dji = get_index_info("^DJI", "道瓊工業")
    
    vix = get_index_info("^VIX", "VIX恐慌指數")
    twd = get_index_info("TWD=X", "美元兌台幣")

    tw_badge, tw_speech = analyze_tw_trend(twii, twoii, tsmc)

    us_bull = 0
    if sox["ok"] and sox["pct"] > 0: us_bull += 1
    if ixic["ok"] and ixic["pct"] > 0: us_bull += 1
    if gspc["ok"] and gspc["pct"] > 0: us_bull += 1

    if us_bull == 3:
        us_badge = "🟢 偏多助攻（美股科技同步收紅）"
        us_speech = "搭配昨夜美股科技與大盤同步走強，有利今日台股開盤延續氣勢。"
    elif us_bull == 0:
        us_badge = "🔴 偏空承壓（美股四大指數拉回）"
        us_speech = "不過昨夜美股四大指數同步拉回，今日台股開盤可能面臨補跌或測試支撐壓力。"
    else:
        us_badge = "🟡 震盪觀察（美股漲跌互見）"
        us_speech = "加上昨夜美股漲跌互見，預期今日台股開盤以個股表現與區間震盪為主。"

    def fmt_line(item, unit="點", decimals=0):
        if not item["ok"]:
            return f"• {item['name']}：暫無最新報價"
        sign = "+" if item["diff"] > 0 else ""
        icon = "🔺" if item["diff"] > 0 else ("🔻" if item["diff"] < 0 else "➖")
        val_str = f"{item['close']:,.{decimals}f}"
        diff_str = f"{sign}{item['diff']:,.{decimals}f}"
        extra = ""
        if "ma5" in item and "ma20" in item:
            extra = f"\n   └ 均線參考：5日線 `{item['ma5']:,.0f}` ｜ 月線 `{item['ma20']:,.0f}`"
        return f"{icon} **{item['name']}** ({item['date']})：`{val_str}` {unit}（{diff_str} / `{sign}{item['pct']:.2f}%`）{extra}"

    def fmt_speech(item, unit="點", decimals=0):
        if not item["ok"]:
            return ""
        direction = "上漲" if item["pct"] > 0 else ("下跌" if item["pct"] < 0 else "平盤")
        abs_pct = abs(item["pct"])
        if decimals == 0:
            val_say = f"{int(round(item['close']))}"
            diff_say = f"{int(round(abs(item['diff'])))} {unit}，"
        else:
            val_say = f"{item['close']:.2f}"
            diff_say = ""
        return f"{item['name']}收在 {val_say} {unit}，{direction} {diff_say}幅度百分之 {abs_pct:.1f}。"

    text_lines = [
        "🌅 **08:30 台美股市大方向 AI 盤前早報**",
        f"🇹🇼 **台股大方向**：{tw_badge}",
        f"🇺🇸 **美股開盤風向**：{us_badge}",
        "",
        "**【一、台北股市大方向與結構】**",
        fmt_line(twii, "點", 0),
        fmt_line(twoii, "點", 2),
        fmt_line(tsmc, "元", 0),
        "",
        "**【二、昨夜美股四大指數】**",
        fmt_line(sox, "點", 0),
        fmt_line(ixic, "點", 0),
        fmt_line(gspc, "點", 0),
        fmt_line(dji, "點", 0),
        "",
        "**【三、資金與避險指標】**",
        fmt_line(vix, "", 2),
        fmt_line(twd, "元", 2)
    ]

    speech_parts = [
        "早安，現在是早上八點半，為你播報台北股市與美股大方向盤前早報。",
        "首先掌握台北股市大方向，",
        tw_speech,
        us_speech,
        "接著為你報告詳細指數數據。在台北股市方面，",
        fmt_speech(twii, "點", 0),
        fmt_speech(twoii, "點", 2),
        fmt_speech(tsmc, "元", 0),
        "在昨夜美股四大指數方面，",
        fmt_speech(sox, "點", 0),
        fmt_speech(ixic, "點", 0),
        fmt_speech(gspc, "點", 0),
        fmt_speech(dji, "點", 0),
        "最後在資金與避險風向標方面，",
        fmt_speech(vix, "", 2),
        fmt_speech(twd, "元", 2),
        "以上是今日台美股市大方向重點，祝你今天操作順利。"
    ]

    return "\n".join(text_lines), " ".join([s for s in speech_parts if s])

def generate_voice(speech_text, output_mp3="morning_market.mp3"):
    cmd = [
        "edge-tts",
        "--voice", "zh-TW-HsiaoChenNeural",
        "--rate=+5%",
        "--text", speech_text,
        "--write-media", output_mp3
    ]
    subprocess.run(cmd, check=True)
    return output_mp3

def send_to_discord(webhook_url, message_text, mp3_path=None):
    webhook_url = webhook_url.strip()
    if not webhook_url.startswith("http"):
        print("❌ 錯誤：尚未在 GitHub Secrets 設定 DISCORD_WEBHOOK_URL！")
        return

    data = {
        "username": "台美股大方向 AI 助理",
        "content": message_text[:1950]
    }

    if mp3_path and os.path.exists(mp3_path):
        with open(mp3_path, "rb") as f:
            files = {"file": (os.path.basename(mp3_path), f, "audio/mpeg")}
            resp = requests.post(webhook_url, data=data, files=files, timeout=20)
    else:
        resp = requests.post(webhook_url, json=data, timeout=20)

    if resp.status_code in (200, 204):
        print("✅ 推播成功！")
    else:
        print(f"❌ 推播失敗，狀態碼：{resp.status_code}，原因：{resp.text}")

if __name__ == "__main__":
    try:
        discord_msg, voice_script = build_macro_report()
        mp3_file = generate_voice(voice_script)
        send_to_discord(DISCORD_WEBHOOK_URL, discord_msg, mp3_file)
    except Exception as e:
        err = f"🚨 盤前早報執行發生異常：{str(e)}"
        print(err)
        send_to_discord(DISCORD_WEBHOOK_URL, err)
