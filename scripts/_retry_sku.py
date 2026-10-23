# -*- coding: utf-8 -*-
"""按 US SKU 列表重传 MX（不翻全店，秒级）。修完 build_mx 用它重跑失败项。

用法：
  python _retry_sku.py --store zhangaodi SKU1,SKU2,...
  python _retry_sku.py --store zhangaodi SKU1 --dry-run

自动判定：PT 取 listings productTypes（规避 PRODUCT 占位）；parentage_level=child 且带 parent_sku → 子体；
parent → 父体；无 parentage → 独立 listing。
"""
import argparse
import time
import urllib.parse

import auth
import build_mx as bm
import stores


def get_item(sku):
    qs = urllib.parse.urlencode({"marketplaceIds": auth.US,
                                 "includedData": "attributes,summaries,productTypes"})
    st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{sku}?{qs}")
    if st != 200:
        raise RuntimeError(f"GET US {sku} HTTP {st}")
    return r


def real_pt(r):
    for p in (r.get("productTypes") or []):
        if p.get("marketplaceId") == auth.US and p.get("productType"):
            return p["productType"]
    return ((r.get("summaries") or [{}])[0]).get("productType")


def handle(store, us_sku, dry_run=False, force_pt=None):
    r = get_item(us_sku)
    attrs = r.get("attributes") or {}
    pt = force_pt or real_pt(r)
    sku_mx = stores.to_mx_sku(us_sku, store)
    sch = bm.load_mx_schema(pt)
    props, req = sch.get("properties") or {}, sch.get("required") or []

    pl = (attrs.get("parentage_level") or [{}])
    pl = pl[0].get("value") if pl and isinstance(pl[0], dict) else None
    rel = attrs.get("child_parent_sku_relationship") or []
    psku = rel[0].get("parent_sku") if rel and isinstance(rel[0], dict) else None

    if pl == "parent":
        pd, drop, miss = bm.build(attrs, None, sku_mx, True, pt, props, req)
        tag = "父"
    elif pl == "child" and psku:
        try:
            us_price = attrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
        except Exception as e:
            print(f"[子] {sku_mx} 读源价失败 {e}")
            return
        t, o, l = bm.calc_mx_price(us_price)
        pd, drop, miss = bm.build(attrs, (t, o, l), sku_mx, False, pt, props, req,
                                   stores.to_mx_sku(psku, store))
        tag = f"子(父={psku}) US${us_price}→MX${o}/划线MX${l}"
    else:
        try:
            us_price = attrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
        except Exception as e:
            print(f"[独立] {sku_mx} 读源价失败 {e}")
            return
        t, o, l = bm.calc_mx_price(us_price)
        pd, drop, miss = bm.build(attrs, (t, o, l), sku_mx, False, pt, props, req, None,
                                   standalone=True)
        tag = f"独立 US${us_price}→MX${o}/划线MX${l}"

    print(f"[{tag}] {us_sku} → {sku_mx} PT={pt} 剔除={drop} 缺必填={miss}")
    if miss:
        print("  ⚠️ 必填缺失，跳过")
        return
    if dry_run:
        return
    st, rr = bm.put_listing(sku_mx, {"productType": pt, "requirements": "LISTING", "attributes": pd})
    errs = [(i.get("code"), i.get("attributeNames")) for i in (rr.get("issues") or [])
            if i.get("severity") == "ERROR"]
    print(f"  PUT → HTTP {st} {rr.get('status')} errs={errs}")
    for i in (rr.get("issues") or []):
        if i.get("severity") != "ERROR":
            print(f"   · [{i.get('severity')}] {i.get('code')} {i.get('attributeNames')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True, choices=list(stores.STORES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-pt", default=None, help="强制指定 PT（如父体要跟子体对齐时）")
    ap.add_argument("skus")
    a = ap.parse_args()
    auth.set_store(a.store)
    for s in [x.strip() for x in a.skus.split(",") if x.strip()]:
        try:
            handle(a.store, s, a.dry_run, a.force_pt)
        except Exception as e:
            print(f"  ⚠️ {s} 异常：{e}")
        time.sleep(1.2)


if __name__ == "__main__":
    main()
