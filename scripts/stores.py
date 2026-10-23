# -*- coding: utf-8 -*-
"""店铺配置表（US→MX 跨站复制用）。

每家店的：凭证文件、NA seller_id、token 下标、US 品牌、SKU 后缀规则。
新增店铺只需在此加一条。

⚠️ token 铁律：凭证文件里**第 0 个 refresh_token = AU 站，第 1 个 = NA(US/CA/MX)**；
MX 走 NA 端点 + 第 1 个 token。
"""

STORES = {
    "zhangaodi": {
        "cred_file": r"D:\广告上传表格\sp-api-workbuddy奥迪.txt",
        "na_seller": "A1ON6BNVRPOF3T",
        "token_na_index": 1,
        "us_brand": "EAOEIHD",
        "sku_us_suffix": None,            # 张奥迪 US SKU 无站点后缀（如 5X-Q1H6-6BP1）
        "sku_mx_suffix": "-mx",           # 张奥迪 MX＝追加 -mx（现网如 ZH-348-mx-#C）
    },
    "liudongdong": {
        "cred_file": r"D:\广告上传表格\sp-api-workbuddy刘冬冬.txt",
        "na_seller": "A37KA1V9F4DYXQ",
        "token_na_index": 1,
        "us_brand": "Generic",            # 刘冬冬 US 品牌是 Generic
        "sku_us_suffix": "-US",           # 刘冬冬 US SKU 带 -US/-us（如 483-1-US-3mx2m）
        "sku_mx_suffix": "-MX",           # 对应 MX 是 -MX/-mx（现网如 483-1-MX-2.4mx2.4m）
    },
}

DEFAULT_STORE = "zhangaodi"

# 需要从 US 标题里剥掉的品牌前缀
BRAND_PREFIXES = ["EAOEIHD", "Generic", "Genérico"]


def to_mx_sku(sku, store=DEFAULT_STORE):
    """US SKU → MX SKU。带 -US/-us 后缀的做替换，否则追加 -mx。"""
    cfg = STORES[store]
    us_suf = cfg.get("sku_us_suffix")
    mx_suf = cfg["sku_mx_suffix"]
    if us_suf:
        for variant in (us_suf.upper(), us_suf.lower()):
            if variant in sku:
                rep = mx_suf if variant.isupper() else mx_suf.lower()
                return sku.replace(variant, rep)
    return sku + mx_suf


def strip_brand(title):
    t = (title or "").strip()
    for b in sorted(BRAND_PREFIXES, key=len, reverse=True):
        if t.lower().startswith(b.lower()):
            t = t[len(b):].strip()
            break
    return t
