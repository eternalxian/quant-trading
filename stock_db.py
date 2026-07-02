"""
股票公司信息库

管理持仓股票的基础信息（主营业务、核心产品）
数据存储: data/stock_info.json
"""
import json
import os
import pandas as pd
import akshare as ak
from datetime import datetime
from data import DATA_DIR

DB_FILE = os.path.join(DATA_DIR, "stock_info.json")

# ── 美股/港股 手动基础信息 ──
# 格式: code: { name, sector, business, products, hq }
MANUAL_INFO = {
    "NVDA": {
        "name": "英伟达",
        "sector": "半导体/AI",
        "business": "AI芯片设计龙头，GPU/CUDA生态垄断者",
        "products": "H100/B200数据中心GPU, RTX消费显卡, CUDA软件栈, Drive自动驾驶平台",
        "hq": "美国加州圣克拉拉",
    },
    "TSM": {
        "name": "台积电",
        "sector": "半导体",
        "business": "全球最大晶圆代工厂，先进制程领先者",
        "products": "3nm/5nm/7nm制程代工, CoWoS先进封装, 车用MCU",
        "hq": "台湾新竹",
    },
    "LITE": {
        "name": "Lumentum",
        "sector": "光通信",
        "business": "光通信器件与激光器龙头",
        "products": "光模块核心光芯片, 3D传感VCSEL, 光纤激光器",
        "hq": "美国加州圣何塞",
    },
    "COHR": {
        "name": "Coherent",
        "sector": "光通信",
        "business": "光通信器件与工业激光器",
        "products": "光通信收发模块, 高功率激光器, 精密光学元件",
        "hq": "美国宾州萨克森堡",
    },
    "CIEN": {
        "name": "Ciena",
        "sector": "光通信",
        "business": "光网络设备商，重视AI时代DCI互联",
        "products": "WaveLogic光传输平台, 路由器和交换机, 网络自动化软件",
        "hq": "美国马里兰州汉诺威",
    },
    "VIAV": {
        "name": "Viavi",
        "sector": "光通信/测试",
        "business": "通信测试设备与光网络监控",
        "products": "光纤测试仪, 网络性能监控, 3D传感光学滤光片",
        "hq": "美国亚利桑那州钱德勒",
    },
    "ANET": {
        "name": "Arista",
        "sector": "通信设备",
        "business": "数据中心交换机领先者, AI集群网络关键供应商",
        "products": "数据中心交换机, 路由平台, EOS网络操作系统",
        "hq": "美国加州圣克拉拉",
    },
    "AAPL": {
        "name": "苹果",
        "sector": "消费电子",
        "business": "全球消费电子巨头",
        "products": "iPhone, Mac, iPad, Apple Watch, AirPods, Apple Silicon芯片",
        "hq": "美国加州库比蒂诺",
    },
    "GOOGL": {
        "name": "谷歌-A",
        "sector": "AI/互联网",
        "business": "全球搜索引擎巨头, AI大模型领导者",
        "products": "Google搜索, Gemini大模型, Android, YouTube, Google Cloud, TPU芯片",
        "hq": "美国加州山景城",
    },
    "GOOG": {
        "name": "谷歌-C",
        "sector": "AI/互联网",
        "business": "谷歌C类股（无投票权），业务同GOOGL",
        "products": "同GOOGL",
        "hq": "美国加州山景城",
    },
    "MSFT": {
        "name": "微软",
        "sector": "AI/云计算",
        "business": "全球最大软件公司, AI全面转型",
        "products": "Azure云, Office 365, Windows, Copilot AI, GitHub, OpenAI投资",
        "hq": "美国华盛顿州雷德蒙德",
    },
    "AMZN": {
        "name": "亚马逊",
        "sector": "云计算",
        "business": "全球最大电商+云计算平台",
        "products": "AWS云服务, Amazon电商, Alexa, Prime Video, Kuiper卫星",
        "hq": "美国华盛顿州西雅图",
    },
    "META": {
        "name": "Meta",
        "sector": "AI/互联网",
        "business": "全球社交网络巨头, AI+元宇宙双主线",
        "products": "Facebook, Instagram, WhatsApp, Llama大模型, Quest VR, Ray-Ban眼镜",
        "hq": "美国加州门洛帕克",
    },
    "AVGO": {
        "name": "博通",
        "sector": "半导体/通信",
        "business": "通信芯片+基础设施软件双巨头",
        "products": "网络交换芯片, WiFi/蓝牙芯片, VMware虚拟化, 光耦隔离器",
        "hq": "美国加州圣何塞",
    },
    "AMD": {
        "name": "AMD",
        "sector": "半导体",
        "business": "CPU/GPU芯片设计, 英伟达主要竞争对手",
        "products": "Ryzen CPU, Radeon GPU, EPYC服务器CPU, Instinct AI加速器",
        "hq": "美国加州圣克拉拉",
    },
    "MU": {
        "name": "美光",
        "sector": "半导体",
        "business": "全球三大存储芯片厂商之一",
        "products": "DRAM内存, NAND闪存, HBM高带宽内存(AI关键物料)",
        "hq": "美国爱达荷州博伊西",
    },
    "MRVL": {
        "name": "Marvell",
        "sector": "半导体",
        "business": "数据中心连接芯片设计公司",
        "products": "以太网交换芯片, 光通信DSP, 定制ASIC, 存储控制器",
        "hq": "美国加州圣克拉拉",
    },
    "SNPS": {
        "name": "Synopsys",
        "sector": "EDA/半导体",
        "business": "全球第一大EDA软件公司",
        "products": "EDA设计工具, IP核, 软件安全测试",
        "hq": "美国加州山景城",
    },
    "CDNS": {
        "name": "Cadence",
        "sector": "EDA/半导体",
        "business": "全球第二大EDA软件公司",
        "products": "EDA设计工具, IP核, 系统仿真验证",
        "hq": "美国加州圣何塞",
    },
    "ADI": {
        "name": "亚德诺",
        "sector": "模拟芯片",
        "business": "全球第二大模拟芯片公司",
        "products": "模数转换器(ADC), 放大器, 惯性传感器, 射频芯片",
        "hq": "美国马萨诸塞州威尔明顿",
    },
    "TXN": {
        "name": "德州仪器",
        "sector": "模拟芯片",
        "business": "全球最大模拟芯片公司",
        "products": "电源管理芯片, 信号链芯片, 嵌入式处理器",
        "hq": "美国得州达拉斯",
    },
    "QCOM": {
        "name": "高通",
        "sector": "通信芯片",
        "business": "移动通信芯片霸主",
        "products": "骁龙手机SoC, 5G基带芯片, 汽车座舱芯片, IoT模组",
        "hq": "美国加州圣地亚哥",
    },
    "NXPI": {
        "name": "恩智浦",
        "sector": "汽车芯片",
        "business": "汽车电子芯片领导者",
        "products": "车载MCU, 汽车雷达芯片, NFC控制器, 物联网处理器",
        "hq": "荷兰埃因霍温",
    },
    "KLAC": {
        "name": "科磊",
        "sector": "半导体设备",
        "business": "晶圆检测设备龙头",
        "products": "光罩检测, 晶圆缺陷检测, 量测设备",
        "hq": "美国加州米尔皮塔斯",
    },
    "AMAT": {
        "name": "应用材料",
        "sector": "半导体设备",
        "business": "全球最大半导体设备公司",
        "products": "薄膜沉积, 离子注入, 蚀刻, 计量检测设备",
        "hq": "美国加州圣克拉拉",
    },
    "LRCX": {
        "name": "泛林",
        "sector": "半导体设备",
        "business": "全球第三大半导体设备公司",
        "products": "蚀刻设备, 薄膜沉积设备, 晶圆清洗设备",
        "hq": "美国加州弗里蒙特",
    },
    "ASML": {
        "name": "ASML",
        "sector": "半导体设备",
        "business": "全球唯一EUV光刻机供应商",
        "products": "EUV极紫外光刻机, DUV深紫外光刻机, 计量检测系统",
        "hq": "荷兰费尔德霍芬",
    },
    "CRWD": {
        "name": "CrowdStrike",
        "sector": "网络安全",
        "business": "云端网络安全龙头",
        "products": "Falcon终端检测响应(EDR), 威胁情报, 零信任安全",
        "hq": "美国德州奥斯汀",
    },
    "PANW": {
        "name": "Palo Alto",
        "sector": "网络安全",
        "business": "网络安全综合方案供应商",
        "products": "下一代防火墙, Prisma云安全, Cortex XDR",
        "hq": "美国加州圣克拉拉",
    },
    "WDC": {
        "name": "西部数据",
        "sector": "存储",
        "business": "全球存储设备及方案厂商",
        "products": "HDD机械硬盘, NAND闪存, SSD固态硬盘",
        "hq": "美国加州圣何塞",
    },
    "STX": {
        "name": "希捷",
        "sector": "存储",
        "business": "全球机械硬盘领导者",
        "products": "HDD机械硬盘(含HAMR热辅助磁记录), NVMe SSD",
        "hq": "美国加州弗里蒙特",
    },
    "TSLA": {
        "name": "特斯拉",
        "sector": "汽车/新能源",
        "business": "全球电动汽车领导者, AI/机器人新方向",
        "products": "Model S/3/X/Y, Cybertruck, Optimus机器人, FSD自动驾驶, Dojo超算",
        "hq": "美国德州奥斯汀",
    },
    "GLW": {
        "name": "康宁",
        "sector": "材料/光学",
        "business": "特种材料与光通信光纤龙头",
        "products": "Gorilla玻璃, 光纤光缆, 显示玻璃基板, 排放控制陶瓷",
        "hq": "美国纽约州康宁市",
    },
    "BRK_B": {
        "name": "伯克希尔-B",
        "sector": "综合投资",
        "business": "巴菲特旗下多元化投资控股公司",
        "products": "保险(GEICO), 铁路(BNSF), 能源(BHE), 苹果持股, 大量现金储备",
        "hq": "美国内布拉斯加州奥马哈",
    },
    "AEIS": {
        "name": "先进能源",
        "sector": "半导体设备",
        "business": "半导体制造电源与控制方案",
        "products": "射频电源, 等离子体电源, 高压电源, 远程等离子体源",
        "hq": "美国科罗拉多州丹佛",
    },
    "TER": {
        "name": "泰瑞达",
        "sector": "半导体设备",
        "business": "半导体测试设备龙头",
        "products": "SoC测试机, 存储测试机, 工业自动化测试, 机器人",
        "hq": "美国马萨诸塞州威尔明顿",
    },
    "AXTI": {
        "name": "AXT Inc",
        "sector": "半导体材料",
        "business": "砷化镓/磷化铟衬底材料供应商",
        "products": "砷化镓(GaAs)衬底, 磷化铟(InP)衬底, 锗衬底",
        "hq": "美国加州弗里蒙特",
    },
    "TSEM": {
        "name": "高塔半导体",
        "sector": "半导体",
        "business": "以色列特色工艺晶圆代工厂",
        "products": "模拟/混合信号代工, 射频SOI, 图像传感器代工, 电源管理代工",
        "hq": "以色列拿撒勒",
    },
    "00981": {
        "name": "中芯国际",
        "sector": "半导体",
        "business": "中国大陆最大晶圆代工厂",
        "products": "28nm成熟制程代工, 逻辑IC代工, CIS图像传感器代工",
        "hq": "上海",
    },
    "01347": {
        "name": "华虹半导体",
        "sector": "半导体",
        "business": "中国大陆特色工艺代工厂",
        "products": "嵌入式存储代工, 功率器件代工, 模拟IC代工, 逻辑代工",
        "hq": "上海",
    },
    "SNDK": {
        "name": "晟碟(西部数据)",
        "sector": "存储",
        "business": "闪存存储方案商(已被西数整合)",
        "products": "NAND闪存, SSD, 存储卡, U盘",
        "hq": "美国加州米尔皮塔斯",
    },
}

# ── A股需要从AKShare拉取，不存储在MANUAL_INFO ──

def _fetch_a_stock_info(code: str) -> dict:
    """通过 AKShare 获取 A 股公司基础信息 (cninfo 源, 含主营业务/行业/地址)"""
    try:
        info = ak.stock_profile_cninfo(symbol=code)
        if info is None or info.empty:
            return {}
        row = info.iloc[0]
        result = {
            "name": str(row.get("A股简称", "")),
            "sector": str(row.get("所属行业", "")),
            "business": str(row.get("主营业务", "")),
            "products": "",
            "hq": str(row.get("注册地址", "")),
            "website": str(row.get("官方网站", "") or ""),
        }
        return result
    except Exception as e:
        return {}


_A_STOCK_CACHE = {}


def get_stock_info(code: str) -> dict:
    """获取单只股票的公司信息

    Args:
        code: 股票代码 (6位A股代码 或 美股代码)

    Returns:
        dict with keys: name, sector, business, products, hq, source
    """
    db = load_db()

    # 缓存命中
    if code in db:
        return db[code]

    # 美股/港股
    if code in MANUAL_INFO:
        info = dict(MANUAL_INFO[code])
        info["code"] = code
        info["source"] = "manual"
        db[code] = info
        save_db(db)
        return info

    # A股
    if code.isdigit() and len(code) == 6:
        if code in _A_STOCK_CACHE:
            return _A_STOCK_CACHE[code]
        fetched = _fetch_a_stock_info(code)
        if fetched and "name" in fetched:
            info = {
                "code": code,
                "name": fetched.get("name", ""),
                "sector": fetched.get("sector", ""),
                "business": fetched.get("business", "主营业务数据暂缺"),
                "products": fetched.get("products", ""),
                "hq": fetched.get("hq", ""),
                "website": fetched.get("website", ""),
                "source": "akshare",
            }
            db[code] = info
            save_db(db)
            _A_STOCK_CACHE[code] = info
            return info

    return {"code": code, "name": code, "sector": "未知", "business": "暂无数据"}


def load_db() -> dict:
    """加载全部股票信息库"""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_db(db: dict):
    """保存股票信息库"""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [错误] 保存股票信息库失败: {e}")


def seed_from_holdings(all_holdings: dict):
    """基于持仓数据批量填充股票信息库"""
    db = load_db()
    seen = set()

    for fund_code, data in all_holdings.items():
        for h in data["holdings"]:
            code = h.get("code", "")
            if not code or code in seen:
                continue
            seen.add(code)

            # 跳过 ETF 穿透的电力股
            if h.get("note", "").startswith("(159611"):
                continue

            if code in db:
                continue
            if code in MANUAL_INFO:
                info = dict(MANUAL_INFO[code])
                info["code"] = code
                info["source"] = "manual"
                db[code] = info
                print(f"  + {code} {info['name']} (手动数据)")
            elif code.isdigit() and len(code) == 6:
                fetched = _fetch_a_stock_info(code)
                if fetched and "name" in fetched:
                    info = {
                        "code": code,
                        "name": fetched.get("name", ""),
                        "sector": fetched.get("sector", ""),
                        "business": fetched.get("business", ""),
                        "products": fetched.get("products", ""),
                        "hq": fetched.get("hq", ""),
                        "website": fetched.get("website", ""),
                        "source": "akshare",
                    }
                    db[code] = info
                    print(f"  + {code} {info['name']} (AKShare)")
                else:
                    print(f"  x {code} 拉取失败")

    save_db(db)
    print(f"\n共收录 {len(db)} 只股票")


def query_stock(keyword: str) -> list:
    """搜索股票信息

    Args:
        keyword: 代码或名称关键词

    Returns:
        [{"code", "name", "sector", "business"}, ...]
    """
    db = load_db()
    results = []
    for code, info in db.items():
        if keyword.lower() in code.lower() or keyword.lower() in info.get("name", "").lower():
            results.append({
                "code": code,
                "name": info.get("name", ""),
                "sector": info.get("sector", ""),
                "business": info.get("business", ""),
            })
    return results


def print_stock_info(code: str):
    """CLI 打印单只股票信息"""
    info = get_stock_info(code)
    if not info or not info.get("name"):
        print(f"\n未找到 {code} 的信息\n")
        return
    print(f"\n{'='*50}")
    print(f"  {info.get('name', code)} ({code})")
    print(f"{'='*50}")
    print(f"  行业:    {info.get('sector', 'N/A')}")
    print(f"  主营:    {info.get('business', 'N/A')}")
    if info.get("products"):
        print(f"  产品:    {info['products']}")
    if info.get("hq"):
        print(f"  总部:    {info['hq']}")
    if info.get("website"):
        print(f"  官网:    {info['website']}")
    if info.get("source") == "manual":
        print(f"  数据源:  手动整理")
    print(f"{'='*50}\n")
