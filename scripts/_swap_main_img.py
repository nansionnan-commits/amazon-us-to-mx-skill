# -*- coding: utf-8 -*-
"""主图被判定含文字/水印（18027 / 18320）时，把 US 的备选图顶到主图位重传。
用法: python _swap_main_img.py --store zhangaodi --idx 1 SKU1,SKU2,...
      --idx 1 表示用 US 的 other_product_image_locator_1，2 用 _2，依次类推
"""
import argparse
import time
import urllib.parse

import auth
import build_mx as bm
import stores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True, choices=list(stores.STORES))
    ap.add_argument("--idx", default="1")
    ap.add_argument("skus")
    a = ap.parse_args()
    auth.set_store(a.store)
    alt = f"other_product_image_locator_{a.idx}"

    for us_sku in [x.strip() for x in a.skus.split(",") if x.strip()]:
        r = None
        qs = urllib.parse.urlencode({"marketplaceIds": auth.US,
                                     "includedData": "attributes,summaries,productTypes"})
        st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{us_sku}?{qs}")
        if st != 200:
            print(f"⚠️ {us_sku} GET HTTP {st}")
            continue
        attrs = r.get("attributes") or {}
        pt = None
        for p in (r.get("productTypes") or []):
            if p.get("marketplaceId") == auth.US:
                pt = p.get("productType")
        pt = pt or ((r.get("summaries") or [{}])[0]).get("productType")
        src = (attrs.get(alt) or [])
        if not src:
            print(f"⚠️ {us_sku} 无 US {alt}，跳过")
            continue
        sku_mx = stores.to_mx_sku(us_sku, a.store)
        sch = bm.load_mx_schema(pt)
        props, req = sch.get("properties") or {}, sch.get("required") or []
        try:
            us_price = attrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
        except Exception as e:
            print(f"⚠️ {us_sku} 读源价失败 {e}")
            continue
        t, o, l = bm.calc_mx_price(us_price)
        pd, _, _ = bm.build(attrs, (t, o, l), sku_mx, False, pt, props, req, None, standalone=True)
        pd["main_product_image_locator"] = bm.retag(src)
        pd.pop(alt, None)   # 已顶上主图，避免重复
        st2, rr = bm.put_listing(sku_mx, {"productType": pt, "requirements": "LISTING",
                                          "attributes": pd})
        errs = [(i.get("code"), i.get("attributeNames")) for i in (rr.get("issues") or [])
                if i.get("severity") == "ERROR"]
        print(f"[{us_sku} → {sku_mx}] 主图换 {alt} | PUT HTTP {st2} {rr.get('status')} errs={errs}")
        time.sleep(1.2)


if __name__ == "__main__":
    main()
