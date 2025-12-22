from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64


# --- Загрузка данных (абсолютный путь, чтобы работало всегда) ---
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "cars_clean.csv"

df = pd.read_csv(DATA_PATH)

# Нормализуем числа
for col in ["year", "horsepower", "price_usd"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")


def _fig_to_base64(fig) -> str:
    """Сохраняет matplotlib-figure в PNG(base64) и освобождает память."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# --- 1) Базовая статистика ---
def basic_stats() -> dict:
    """
    Возвращает базовую статистику по данным:
    - total_cars: количество авто
    - mean_price: средняя цена (округление до целого)
    - median_price: медианная цена (округление до целого)
    - popular_brands: топ-5 марок по количеству
    """
    data = df.dropna(subset=["price_usd"]).copy()

    total_cars = int(len(df))
    mean_price = int(round(data["price_usd"].mean())) if len(data) else 0
    median_price = int(round(data["price_usd"].median())) if len(data) else 0

    popular_brands = (
        df["brand"]
        .fillna("Unknown")
        .value_counts()
        .head(5)
        .to_dict()
    )

    return {
        "total_cars": total_cars,
        "mean_price": mean_price,
        "median_price": median_price,
        "popular_brands": popular_brands,
    }


# --- 2) Графики ---
def price_distribution_by_brand() -> str:
    """
    Распределение цен по маркам (boxplot).
    Возвращает PNG (base64).
    """
    data = df.dropna(subset=["brand", "price_usd"]).copy()
    if data.empty:
        fig = plt.figure(figsize=(8, 3))
        plt.text(0.5, 0.5, "Нет данных для графика", ha="center", va="center")
        plt.axis("off")
        return _fig_to_base64(fig)

    brands = sorted(data["brand"].unique())
    prices = [data.loc[data["brand"] == b, "price_usd"].values for b in brands]

    fig = plt.figure(figsize=(10, 4))
    plt.boxplot(prices, labels=brands, showfliers=True)
    plt.title("Распределение цен по маркам")
    plt.xlabel("Марка")
    plt.ylabel("Цена (USD)")
    plt.xticks(rotation=30, ha="right")
    plt.grid(True, axis="y", alpha=0.3)

    return _fig_to_base64(fig)


def price_vs_year() -> str:
    """
    Зависимость цены от года выпуска (scatter).
    Возвращает PNG (base64).
    """
    data = df.dropna(subset=["year", "price_usd"]).copy()
    if data.empty:
        fig = plt.figure(figsize=(8, 3))
        plt.text(0.5, 0.5, "Нет данных для графика", ha="center", va="center")
        plt.axis("off")
        return _fig_to_base64(fig)

    fig = plt.figure(figsize=(9, 4))
    plt.scatter(data["year"], data["price_usd"], alpha=0.8)
    plt.title("Зависимость цены от года выпуска")
    plt.xlabel("Год выпуска")
    plt.ylabel("Цена (USD)")
    plt.grid(True, alpha=0.3)

    return _fig_to_base64(fig)


def price_vs_horsepower() -> str:
    """
    Зависимость цены от мощности (scatter).
    Возвращает PNG (base64).
    """
    data = df.dropna(subset=["horsepower", "price_usd"]).copy()
    if data.empty:
        fig = plt.figure(figsize=(8, 3))
        plt.text(0.5, 0.5, "Нет данных для графика", ha="center", va="center")
        plt.axis("off")
        return _fig_to_base64(fig)

    fig = plt.figure(figsize=(9, 4))
    plt.scatter(data["horsepower"], data["price_usd"], alpha=0.8)
    plt.title("Зависимость цены от мощности")
    plt.xlabel("Мощность (л.с.)")
    plt.ylabel("Цена (USD)")
    plt.grid(True, alpha=0.3)

    return _fig_to_base64(fig)
