# -*- coding: utf-8 -*-
"""探测 US ASIN 的真实 PT（catalog 2022-04-01 productTypes）与 US listing summaries 的差异。
用法: python _probe_pt.py --store zhangaodi ASIN1,ASIN2,...
"""
import argparse
import json
import urllib.parse

import auth
import stores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=stores.DEFAULT_STORE, choices=list(stores.STORES))
    ap.add_argument("asins")
    a = ap.parse_args()
    auth.set_store(a.store)
    for asin in [x.strip() for x in a.asins.split(",") if x.strip()]:
        qs = urllib.parse.urlencode({"marketplaceIds": auth.US,
                                     "includedData": "productTypes,summaries,classifications"})
        st, r = auth.request("GET", f"/catalog/2022-04-01/items/{asin}?{qs}")
        pts = r.get("productTypes") if isinstance(r, dict) else None
        cls = None
        if isinstance(r, dict):
            cls = [c.get("classifications") for c in (r.get("classifications") or [])]
        summ = (r.get("summaries") or [{}])[0] if isinstance(r, dict) else {}
        print(f"{asin} HTTP{st} pt={pts} name={(summ.get('itemName') or '')[:60]}")
        if cls and cls[0]:
            for c in cls[0][:6]:
                print("    cls:", c.get("marketplaceId"), c.get("classificationId"), c.get("displayName"))


if __name__ == "__main__":
    main()
