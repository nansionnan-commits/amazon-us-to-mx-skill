# -*- coding: utf-8 -*-
"""对给定 US SKU 列表：查 listings summaries 的 PT + catalog 的真实 PT，定位 PT=PRODUCT 的可创建类型。
用法: python _diag_pt_of.py --store zhangaodi SKU1,SKU2,...
"""
import argparse
import urllib.parse

import auth
import stores


def listing_summary(sku):
    qs = urllib.parse.urlencode({"marketplaceIds": auth.US, "includedData": "summaries"})
    st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{sku}?{qs}")
    s = (r.get("summaries") or [{}])[0] if isinstance(r, dict) else {}
    return st, s.get("asin"), s.get("productType"), s.get("itemName") or ""


def catalog_pts(asin):
    if not asin:
        return None, None
    qs = urllib.parse.urlencode({"marketplaceIds": auth.US,
                                 "includedData": "productTypes,classifications"})
    st, r = auth.request("GET", f"/catalog/2022-04-01/items/{asin}?{qs}")
    if st != 200 or not isinstance(r, dict):
        return st, None
    pts = [p.get("productType") for p in (r.get("productTypes") or [])]
    cls = []
    for c in (r.get("classifications") or []):
        for x in (c.get("classifications") or []):
            cls.append(x.get("classificationId"))
    return st, (pts, cls[:4])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=stores.DEFAULT_STORE, choices=list(stores.STORES))
    ap.add_argument("skus")
    a = ap.parse_args()
    auth.set_store(a.store)
    for sku in [x.strip() for x in a.skus.split(",") if x.strip()]:
        st, asin, pt, name = listing_summary(sku)
        cst, cpts = catalog_pts(asin)
        print(f"{sku:<24} ASIN={asin} listingPT={pt} catalog={cpts} | {name[:50]}")


if __name__ == "__main__":
    main()
