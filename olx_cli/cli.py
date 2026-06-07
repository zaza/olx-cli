from __future__ import annotations

import json
import sys

import click

from olx_cli.query import build_url, describe
from olx_cli.radius import KNOWN_RADII
from olx_cli.scrapper import OlxScrapper


def _print_table(offers, description, total, url, json_output):
    if json_output:
        data = {
            "query": description,
            "url": url,
            "total": total,
            "offers": [
                {
                    "title": o.title,
                    "price": o.price,
                    "url": o.url,
                    "city": o.city,
                    "photo": o.photo,
                }
                for o in offers
            ],
        }
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    click.echo(f"Found {total} offers for {description}")
    click.echo()

    if not offers:
        return

    title_w = max(len(o.title) for o in offers)
    title_w = max(title_w, len("Title"))
    price_w = max(len(o.price) for o in offers)
    price_w = max(price_w, len("Price"))
    city_w = max(len(o.city) for o in offers)
    city_w = max(city_w, len("Location"))

    header = f"{'Title':<{title_w}}  {'Price':>{price_w}}  {'Location':<{city_w}}"
    sep = "-" * len(header)
    click.echo(header)
    click.echo(sep)
    for o in offers:
        click.echo(
            f"{o.title:<{title_w}}  {o.price:>{price_w}}  {o.city:<{city_w}}"
        )
    click.echo()
    click.echo(f"URL: {url}")


@click.group()
def cli():
    pass


def _validate_category(category: str | None) -> str | None:
    if category is None:
        return None
    from olx_cli.category import validate as validate_category

    try:
        validate_category(category)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort from e
    return category.strip("/")


@cli.command()
@click.argument("query")
@click.option("-p", "--photo-only", is_flag=True, help="Only offers with photos")
@click.option("-l", "--location", help="Location name (e.g. 'Kraków')")
@click.option(
    "-r",
    "--radius",
    type=click.IntRange(0, 100),
    help=f"Radius in km {sorted(KNOWN_RADII)}",
)
@click.option("-m", "--min-price", type=int, help="Minimum price")
@click.option("-M", "--max-price", type=int, help="Maximum price")
@click.option("-c", "--category", help="Category slug (e.g. 'motoryzacja/samochody')")
@click.option(
    "--max-pages",
    type=int,
    default=5,
    show_default=True,
    help="Max result pages to scrape",
)
@click.option(
    "--no-max-pages",
    is_flag=True,
    help="Disable page limit (scrapes all pages)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def search(query, photo_only, location, radius, min_price, max_price, category, max_pages, no_max_pages, json_output):
    category = _validate_category(category)

    url = build_url(
        query=query,
        photo_only=photo_only,
        location=location,
        radius=radius,
        min_price=min_price,
        max_price=max_price,
        category=category,
    )

    if no_max_pages:
        max_pages = None

    scrapper = OlxScrapper(url, max_pages=max_pages)
    offers = scrapper.get_offers()

    desc = describe(query, photo_only=photo_only, category=category)
    total = len(offers)

    _print_table(offers, desc, total, url, json_output)


@cli.command()
def categories():
    from olx_cli.category import get_cached, ensure_cached

    cats = ensure_cached()
    if not cats:
        click.echo("Failed to fetch categories. Check your internet connection.", err=True)
        raise click.Abort
    for c in cats:
        click.echo(c)


def main():
    cli()


if __name__ == "__main__":
    main()
