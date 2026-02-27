"""
アフィリエイトリンク クリック計測用リダイレクトサーバー

起動方法:
    python3 redirect_server.py

短縮URL形式:
    http://localhost:8080/go/{short_code}

short_code は商品登録時に自動生成されます。
商品一覧で確認: python3 main.py product list
"""
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.database import repository

app = FastAPI(title="アフィリエイトリンクトラッカー", docs_url=None, redoc_url=None)

repository.init_db()


@app.get("/go/{short_code}")
async def redirect_affiliate(short_code: str, request: Request):
    product = repository.get_product_by_short_code(short_code)
    if not product:
        return HTMLResponse("<h2>リンクが見つかりません</h2>", status_code=404)

    referrer = request.headers.get("referer")
    repository.record_click(
        product_id=product.id,
        short_code=short_code,
        referrer=referrer,
    )
    return RedirectResponse(url=product.affiliate_url, status_code=302)


@app.get("/")
async def index():
    products = repository.list_products()
    rows = "".join(
        f"<tr><td>{p.id}</td><td>{p.name}</td>"
        f"<td><a href='/go/{p.short_code}'>http://localhost:8080/go/{p.short_code}</a></td></tr>"
        for p in products
        if p.short_code
    )
    html = f"""
    <html><head><meta charset="utf-8"><title>リンク一覧</title>
    <style>body{{font-family:sans-serif;padding:20px}}
    table{{border-collapse:collapse;width:100%}}
    th,td{{border:1px solid #ccc;padding:8px;text-align:left}}</style>
    </head><body>
    <h2>トラッキングリンク一覧</h2>
    <table><tr><th>ID</th><th>商品名</th><th>短縮URL</th></tr>{rows}</table>
    </body></html>
    """
    return HTMLResponse(html)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
