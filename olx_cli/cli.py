from __future__ import annotations

import json
from pathlib import Path

import click
import sys
from tabulate import tabulate

from olx_cli.auth import (
    _tokens_path,
    get_tokens,
    login as auth_login,
    logout as auth_logout,
    read_credentials,
)
from olx_cli.category import ensure_cached, validate as validate_category
from olx_cli.client import get_profile, get_user_id_from_profile
from olx_cli.offer import compute_stats
from olx_cli.offer_submit import find_offer_files, read_offer, submit_offer, validate_offer
from olx_cli.query import build_url, describe
from olx_cli.radius import KNOWN_RADII
from olx_cli.scraper import OlxScraper, fetch_my_offers, fetch_user_offers_html


def render_json(data):
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")

def _print_table(offers, description, total, url, json_output, stats=None, max_pages=None):
    if json_output:
        data = {
            "query": description,
            "url": url,
            "total": total,
            "offers": [
                {
                    "title": o.title,
                    "price": o.clean_price,
                    "is_negotiable": o.is_negotiable,
                    "url": o.url,
                    "city": o.city,
                    "photo": o.photo,
                }
                for o in offers
            ],
        }
        if stats:
            data['stats'] = stats
        render_json(data)
        return

    pw = 8
    click.echo(f"{'Search:':<{pw}}{description}")
    click.echo(f"{'URL:':<{pw}}{url}")
    if stats:
        pages = stats['pages_visited']
        pages_label = f"{pages} page{'s' * (pages != 1)}"
        if max_pages is not None and pages == max_pages:
            pages_label += ' (max)'
        skipped = stats['skipped']
        avg = stats['average']
        med = stats['median']
        click.echo(f"{'Found:':<{pw}}{total} offers"
                   f"{' (skipped ' + str(skipped) + ' non-monetary)' if skipped else ''}"
                   f" across {pages_label}")
        if avg is not None and med is not None:
            click.echo(f"{'Price:':<{pw}}avg {avg} zł, median {med} zł")
    else:
        click.echo(f"Found:  {total} offers")

    click.echo()

    if not offers:
        return

    rows = []
    for o in offers:
        price = f"*{o.clean_price}" if o.is_negotiable else o.clean_price
        rows.append((o.title, price, o.city))

    click.echo(tabulate(rows, headers=('Title', 'Price', 'Location'), tablefmt='simple'))


@click.group()
def cli():
    pass


def _login_with_browser(creds, json_output=False):
    from olx_cli.browser_auth import login_with_browser as browser_login, read_credentials as browser_creds
    from olx_cli.client import get_profile, get_user_id_from_profile

    if creds is None:
        creds = browser_creds()

    email = password = None
    if creds:
        email, password = creds

    try:
        tokens = browser_login(headless=False, email=email, password=password)
    except RuntimeError as e:
        click.echo(f"Error: {e}\n\nTry again in a few minutes.", err=True)
        raise click.Abort from e

    if not tokens.get('user_id'):
        profile = get_profile()
        if profile and (user_id := get_user_id_from_profile(profile)):
            tokens['user_id'] = user_id
            from olx_cli.auth import _tokens_path
            import json
            _tokens_path().write_text(json.dumps(tokens, ensure_ascii=False))

    if json_output:
        render_json(tokens)
        return

    click.echo("Logged in successfully.")


@cli.command()
@click.option("--browser", is_flag=True, help="Force browser-based login (bypasses WAF)")
@click.option("--json", "json_output", is_flag=True, help="Output tokens as JSON")
def login(browser, json_output):
    creds_path = Path.cwd() / "credentials.txt"
    creds = read_credentials(creds_path)

    if browser or creds is None:
        if not browser and creds is None and not creds_path.exists():
            click.echo(
                f"Error: {creds_path} not found or malformed.\n\n"
                "Create a credentials.txt file with:\n"
                "username=your@email.com\n"
                "password=your_password",
                err=True,
            )
            raise click.Abort
        _login_with_browser(creds, json_output=json_output)
    else:
        email, password = creds

        try:
            auth_login(email, password)
        except RuntimeError:
            click.echo("Cognito login blocked (likely WAF). Falling back to browser login...", err=True)
            _login_with_browser(creds, json_output=json_output)
        else:
            profile = get_profile()
            user_id = get_user_id_from_profile(profile) if profile else None
            if user_id:
                tokens = get_tokens()
                if tokens:
                    tokens['user_id'] = user_id
                    _tokens_path().write_text(json.dumps(tokens, ensure_ascii=False))

            if json_output:
                tokens = get_tokens()
                render_json(tokens)
            else:
                click.echo("Logged in successfully.")


@cli.command()
def logout():
    auth_logout()
    click.echo("Logged out.")


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def me(json_output):
    profile = get_profile()
    if profile is None:
        click.echo("Not logged in. Run 'olx-cli login' first.", err=True)
        raise click.Abort

    if json_output:
        render_json(profile)
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
@click.option("-u", "--user", "user_id", help="User ID to show their offers; 'me' for your own")
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

        scrapper = OlxScraper(url, max_pages=max_pages)
        offers = scrapper.get_offers()
        offers = [o for o in offers if o.matches_keywords(query)]

        desc = describe(query, photo_only=photo_only, category=category)
        stats = compute_stats(offers, scrapper.pages_visited)

    total = len(offers)

    _print_table(offers, desc, total, url, json_output, stats=stats, max_pages=max_pages)


@cli.command()
def categories():
    cats = ensure_cached()
    if not cats:
        click.echo("Failed to fetch categories. Check your internet connection.", err=True)
        raise click.Abort
    for c in cats:
        click.echo(c)


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--dry-run', is_flag=True, help='Parse and validate only, do not submit')
@click.option('--json', 'json_output', is_flag=True, help='Output result as JSON')
def add(path, dry_run, json_output):
    """Add offer(s) from a file or folder.

    PATH can be a single offer.txt file or a folder containing subfolders
    each with their own offer.txt.

    File format:

        title=Tytuł ogłoszenia

        price=1299

        category=rowery

        city=Kraków

        ---

        Opis ogłoszenia (może być wieloliniowy).
    """
    files = find_offer_files(path)

    if not files:
        click.echo('Error: no offer.txt files found.', err=True)
        raise click.Abort

    results = []
    has_errors = False

    for f in files:
        data = read_offer(f)
        errors = validate_offer(data)

        if errors:
            click.echo(f'Error in {f}:', err=True)
            for e in errors:
                click.echo(f'  - {e}', err=True)
            has_errors = True
            if not dry_run:
                results.append({'file': f, 'status': 'validation_error', 'errors': errors})
            continue

        if dry_run:
            click.echo(f'{f}: valid')
            results.append({'file': f, 'status': 'valid', 'data': data})
            continue

        try:
            resp = submit_offer(data)
            results.append({'file': f, 'status': 'submitted', 'response': resp})
        except (RuntimeError, ValueError) as e:
            click.echo(f'Error submitting {f}: {e}', err=True)
            has_errors = True
            results.append({'file': f, 'status': 'error', 'error': str(e)})

    if json_output:
        render_json(results)

    if has_errors:
        raise click.Abort


def main():
    cli()


if __name__ == "__main__":
    main()
