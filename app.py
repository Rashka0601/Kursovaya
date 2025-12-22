from flask import Flask, render_template, request, redirect, url_for, session, send_file, Response, jsonify
import pandas as pd
import io
import json
import base64
from pathlib import Path
from urllib.parse import urlparse

from analysis_utils import (
    basic_stats,
    price_distribution_by_brand,
    price_vs_year,
    price_vs_horsepower,
)

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "cars_clean.csv"

df = pd.read_csv(DATA_PATH)

# Нормализуем числовые колонки (чтобы не было 500 из-за типов)
for col in ["year", "horsepower", "price_usd"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Добавляем id каждой строке (для избранного и рекомендаций)
if "id" not in df.columns:
    df = df.reset_index().rename(columns={"index": "id"})
df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)


def _to_int(x):
    try:
        if x is None:
            return None
        x = str(x).strip()
        if x == "":
            return None
        return int(x)
    except Exception:
        return None


def _safe_next(next_url: str):
    """Разрешаем редирект только на внутренний путь вида '/...'."""
    if not next_url:
        return url_for("index")
    p = urlparse(next_url)
    if p.scheme or p.netloc:
        return url_for("index")
    if not next_url.startswith("/"):
        return url_for("index")
    return next_url


def apply_filters(
    data,
    q=None,
    brand=None, model=None, body_type=None,
    year_min=None, year_max=None,
    hp_min=None, hp_max=None,
    price_min=None, price_max=None,
    fuel_type=None, drive_type=None, transmission=None
):
    """Фильтрация + поиск по тексту (q)."""
    filtered = data.copy()

    # ---- Поиск (q) ----
    if q and str(q).strip():
        terms = str(q).strip().lower().split()
        search_cols = ["brand", "model", "body_type", "fuel_type", "drive_type", "transmission"]

        haystack = (
            filtered[search_cols]
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
        )

        mask = pd.Series(True, index=filtered.index)
        for term in terms:
            mask &= haystack.str.contains(term, na=False)

        filtered = filtered[mask]

    # ---- Фильтры по полям ----
    if brand:
        filtered = filtered[filtered["brand"] == brand]
    if model:
        filtered = filtered[filtered["model"] == model]
    if body_type:
        filtered = filtered[filtered["body_type"] == body_type]
    if fuel_type:
        filtered = filtered[filtered["fuel_type"] == fuel_type]
    if drive_type:
        filtered = filtered[filtered["drive_type"] == drive_type]
    if transmission:
        filtered = filtered[filtered["transmission"] == transmission]

    y_min = _to_int(year_min)
    y_max = _to_int(year_max)
    hp_min_i = _to_int(hp_min)
    hp_max_i = _to_int(hp_max)
    p_min = _to_int(price_min)
    p_max = _to_int(price_max)

    if y_min is not None:
        filtered = filtered[filtered["year"] >= y_min]
    if y_max is not None:
        filtered = filtered[filtered["year"] <= y_max]

    if hp_min_i is not None:
        filtered = filtered[filtered["horsepower"] >= hp_min_i]
    if hp_max_i is not None:
        filtered = filtered[filtered["horsepower"] <= hp_max_i]

    if p_min is not None:
        filtered = filtered[filtered["price_usd"] >= p_min]
    if p_max is not None:
        filtered = filtered[filtered["price_usd"] <= p_max]

    return filtered


@app.route("/", methods=["GET"])
def index():
    brands = sorted(df["brand"].dropna().unique())
    all_models = sorted(df["model"].dropna().unique())

    # модели по маркам (для зависимого select)
    models_by_brand = (
        df.groupby("brand")["model"]
        .apply(lambda s: sorted(s.dropna().unique()))
        .to_dict()
    )

    body_types = sorted(df["body_type"].dropna().unique())
    fuel_types = sorted(df["fuel_type"].dropna().unique())
    drive_types = sorted(df["drive_type"].dropna().unique())
    transmissions = sorted(df["transmission"].dropna().unique())

    stats = basic_stats()

    keys = [
        "q",
        "brand", "model", "body_type", "fuel_type", "drive_type", "transmission",
        "year_min", "year_max", "hp_min", "hp_max", "price_min", "price_max"
    ]
    filters = {k: (request.args.get(k, "") or "") for k in keys}

    filtered_cars = apply_filters(
        df,
        q=filters["q"],
        brand=filters["brand"],
        model=filters["model"],
        body_type=filters["body_type"],
        year_min=filters["year_min"],
        year_max=filters["year_max"],
        hp_min=filters["hp_min"],
        hp_max=filters["hp_max"],
        price_min=filters["price_min"],
        price_max=filters["price_max"],
        fuel_type=filters["fuel_type"],
        drive_type=filters["drive_type"],
        transmission=filters["transmission"],
    )

    # JSON для фронта (через data-* чтобы не ломалось)
    models_by_brand_json = json.dumps(models_by_brand, ensure_ascii=False)
    models_json = json.dumps(all_models, ensure_ascii=False)
    saved_model_json = json.dumps(filters.get("model", ""), ensure_ascii=False)

    favorites = session.get("favorites", [])

    return render_template(
        "index.html",
        cars=filtered_cars.to_dict(orient="records"),
        stats=stats,
        brands=brands,
        body_types=body_types,
        fuel_types=fuel_types,
        drive_types=drive_types,
        transmissions=transmissions,
        filters=filters,
        models_by_brand_json=models_by_brand_json,
        models_json=models_json,
        saved_model_json=saved_model_json,
        favorites=favorites,
    )


@app.route("/favorites/toggle/<int:car_id>", methods=["GET"])
def toggle_favorite(car_id):
    favorites = session.get("favorites", [])

    if car_id in favorites:
        favorites.remove(car_id)
    else:
        favorites.append(car_id)

    session["favorites"] = favorites

    next_url = _safe_next(request.args.get("next") or request.referrer or url_for("index"))
    return redirect(next_url)


@app.route("/favorites", methods=["GET"])
def favorites():
    favorites_ids = session.get("favorites", [])
    fav_cars = df[df["id"].isin(favorites_ids)]
    return render_template("favorites.html", cars=fav_cars.to_dict(orient="records"))


@app.route("/recommend/<int:car_id>", methods=["GET"])
def recommend(car_id):
    car_row = df[df["id"] == car_id]
    if car_row.empty:
        return "Машина не найдена", 404

    car = car_row.iloc[0]
    year = car["year"]
    hp = car["horsepower"]
    price = car["price_usd"]

    # Похожие: та же марка и кузов, год ±1, мощность ±20%
    similar = df[
        (df["brand"] == car["brand"]) &
        (df["body_type"] == car["body_type"]) &
        (df["year"].between(year - 1, year + 1)) &
        (df["horsepower"].between(hp * 0.8, hp * 1.2)) &
        (df["id"] != car_id)
    ]

    # Цена ±10%
    price_range_cars = df[
        (df["price_usd"].between(price * 0.9, price * 1.1)) &
        (df["id"] != car_id)
    ]

    return render_template(
        "recommend.html",
        car=car.to_dict(),
        similar_cars=similar.to_dict(orient="records"),
        price_range_cars=price_range_cars.to_dict(orient="records"),
    )


@app.route("/export", methods=["GET"])
def export():
    """Экспорт по текущим фильтрам (из URL) в CSV через GET."""
    keys = [
        "q",
        "brand", "model", "body_type", "fuel_type", "drive_type", "transmission",
        "year_min", "year_max", "hp_min", "hp_max", "price_min", "price_max"
    ]
    filters = {k: (request.args.get(k, "") or "") for k in keys}

    filtered_cars = apply_filters(
        df,
        q=filters["q"],
        brand=filters["brand"],
        model=filters["model"],
        body_type=filters["body_type"],
        year_min=filters["year_min"],
        year_max=filters["year_max"],
        hp_min=filters["hp_min"],
        hp_max=filters["hp_max"],
        price_min=filters["price_min"],
        price_max=filters["price_max"],
        fuel_type=filters["fuel_type"],
        drive_type=filters["drive_type"],
        transmission=filters["transmission"],
    )

    buf = io.StringIO()
    filtered_cars.to_csv(buf, index=False)
    buf.seek(0)

    return send_file(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="filtered_cars.csv",
    )


@app.route("/plot/<name>", methods=["GET"])
def plot(name):
    """ВАЖНО: отдаём настоящий PNG, а не HTML — чтобы не было image errors."""
    if name == "brand_price":
        img_b64 = price_distribution_by_brand()
    elif name == "price_year":
        img_b64 = price_vs_year()
    elif name == "price_hp":
        img_b64 = price_vs_horsepower()
    else:
        return "Unknown plot", 404

    img_bytes = base64.b64decode(img_b64)
    return Response(img_bytes, mimetype="image/png")


if __name__ == "__main__":
    app.run(debug=True)

@app.route("/api/search", methods=["GET"])
def api_search():
    """
    API для живых подсказок поиска.
    Возвращает список авто: id, brand, model, year, price_usd, body_type
    """
    q = (request.args.get("q") or "").strip()
    brand = (request.args.get("brand") or "").strip()

    try:
        limit = int(request.args.get("limit", 8))
        limit = max(1, min(20, limit))
    except Exception:
        limit = 8

    # если ничего не ввели — не показываем подсказки
    if len(q) < 2 and not brand:
        return jsonify([])

    result = apply_filters(df, q=q, brand=brand)

    cols = ["id", "brand", "model", "year", "price_usd", "body_type"]
    for c in cols:
        if c not in result.columns:
            result[c] = ""

    result = result.sort_values(by="price_usd", ascending=True).head(limit)
    return jsonify(result[cols].to_dict(orient="records"))
