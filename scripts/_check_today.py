# -*- coding: utf-8 -*-
"""交叉验证：某店 US 站最近 N 天新上架（按 createdDate DESC 取前若干条），确认 --today 的 0 是否真实。
用法：python _check_today.py <store> [days]
"""
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

import auth
import stores


def main():
    store = sys.argv[1] if len(sys.argv) > 1 else stores.DEFAULT_STORE
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    auth.set_store(store)
    now = datetime.now(timezone.utc)
    after = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    print(f"店={store} seller={auth.SELLER_ID} UTC now={now:%Y-%m-%d %H:%M} 查 createdAfter={after}")

    rows, token = [], None
    while True:
        params = {"marketplaceIds": auth.US, "pageSize": 20, "includedData": "summaries",
                  "sortBy": "createdDate", "sortOrder": "DESC", "createdAfter": after}
        if token:
            params["pageToken"] = token
        st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}?"
                                    + urllib.parse.urlencode(params))
        if st != 200:
            print(f"HTTP {st} {str(r)[:200]}")
            break
        for it in r.get("items", []):
            s = (it.get("summaries") or [{}])[0]
            rows.append((it.get("createdDate"), it.get("lastUpdatedDate"), it.get("sku"),
                         s.get("asin"), s.get("productType"), s.get("status")))
        token = (r.get("pagination") or {}).get("nextToken")
        if not token:
            break

    print(f"近 {days} 天共 {len(rows)} 条")
    for c, u, sku, asin, pt, stt in rows[:40]:
        print(f"  {c}  upd={u}  {sku}  {asin}  {pt}  {stt}")


if __name__ == "__main__":
    main()
