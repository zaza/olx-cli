from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from olx_cli.offer import compute_stats
from olx_cli.query import build_url, describe
from olx_cli.radius import KNOWN_RADII
from olx_cli.scrapper import OlxScrapper, fetch_my_offers, fetch_user_offers_html


def _print_table(offers, description, total, url, json_output, stats=None):
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
        if stats:
            data['stats'] = stats
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    click.echo(f"Found {total} offers for {description}")
    if stats:
        click.echo(
            f"  Pages: {stats['pages_visited']}  "
            f"Avg price: {stats['average'] or 'N/A'} zł  "
            f"Median: {stats['median'] or 'N/A'} zł  "
            f"(skipped {stats['skipped']} non-monetary)"
        )
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
@click.pass_context
def cli(ctx):
    pass


@cli.command()
def login():
    from olx_cli.auth import (login as auth_login, get_tokens,
        _tokens_path)
    from olx_cli.client import get_profile

    creds_path = Path.cwd() / "credentials.txt"
    if not creds_path.exists():
        click.echo(
            f"Error: {creds_path} not found.\n\n"
            "Create a credentials.txt file with:\n"
            "username=your@email.com\n"
            "password=your_password",
            err=True,
        )
        raise click.Abort

    creds = {}
    for line in creds_path.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()

    email = creds.get("username") or creds.get("email")
    password = creds.get("password")

    if not email or not password:
        click.echo(
            "Error: credentials.txt must contain 'username' and 'password' fields.",
            err=True,
        )
        raise click.Abort

    try:
        auth_login(email, password)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort from e

    profile = get_profile()
    user_id = None
    if profile:
        import re
        m = re.search(r'/user/([^/]+)/', profile.get('user_ads_url', ''))
        if m:
            user_id = m.group(1)
            tokens = get_tokens()
            if tokens:
                tokens['user_id'] = user_id
                _tokens_path().write_text(json.dumps(tokens, ensure_ascii=False))

    if user_id:
        click.echo(user_id)
    else:
        click.echo("Logged in successfully.")


@cli.command()
def logout():
    from olx_cli.auth import logout as auth_logout

    auth_logout()
    click.echo("Logged out.")


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def me(json_output):
    from olx_cli.client import get_profile

    profile = get_profile()
    if profile is None:
        click.echo("Not logged in. Run 'olx-cli login' first.", err=True)
        raise click.Abort

    if json_output:
        import json as _json

        _json.dump(profile, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    click.echo(f"Name:     {profile.get('name', 'N/A')}")
    click.echo(f"Email:    {profile.get('email', 'N/A')}")
    click.echo(f"Phone:    {profile.get('phone', 'N/A')}")
    click.echo(f"City:     {profile.get('location', {}).get('city', {}).get('name', 'N/A')}")
    click.echo(f"Since:    {profile.get('created', 'N/A')}")
    click.echo(f"Account:  {'Business' if profile.get('is_business') else 'Personal'}")
    click.echo(f"Profile:  {profile.get('user_ads_url', 'N/A')}")


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
@click.argument("query", required=False)
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
@click.option("-u", "--user", "user_id", help="User ID to show their offers (e.g. '2MwLv1')")
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
def search(query, photo_only, location, radius, min_price, max_price, category, user_id, max_pages, no_max_pages, json_output):
    category = _validate_category(category)

    if no_max_pages:
        max_pages = None

    if user_id:
        if query:
            click.echo("Error: QUERY cannot be used with --user.", err=True)
            raise click.Abort

        if user_id == 'me':
            from olx_cli.auth import get_tokens

            tokens = get_tokens()
            if not tokens:
                click.echo("Not logged in. Run 'olx-cli login' first.", err=True)
                raise click.Abort

            uid = tokens.get('user_id', '?')
            offers, pages = fetch_my_offers(tokens['AccessToken'], max_pages=max_pages)
            url = f"https://www.olx.pl/mojolx/"
            desc = f"my offers ({uid})"
            stats = compute_stats(offers, pages)
        else:
            url = f"https://www.olx.pl/oferty/uzytkownik/{user_id}/"
            offers, pages = fetch_user_offers_html(user_id, max_pages=max_pages)
            desc = f"offers by user ({user_id})"
            stats = compute_stats(offers, pages)
    else:
        if not query:
            click.echo("Error: QUERY is required.", err=True)
            raise click.Abort

        url = build_url(
            query=query,
            photo_only=photo_only,
            location=location,
            radius=radius,
            min_price=min_price,
            max_price=max_price,
            category=category,
        )

        scrapper = OlxScrapper(url, max_pages=max_pages)
        offers = scrapper.get_offers()
        offers = [o for o in offers if o.matches_keywords(query)]

        desc = describe(query, photo_only=photo_only, category=category)
        stats = compute_stats(offers, scrapper.pages_visited)

    total = len(offers)

    _print_table(offers, desc, total, url, json_output, stats=stats)


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
