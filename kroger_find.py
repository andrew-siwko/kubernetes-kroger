import re
import sys

import requests


def load_variable(variable_name):
    import os
    result = os.getenv(variable_name)
    if result is None:
        try:
            import winreg
            result = winreg.QueryValue(winreg.CreateKey(winreg.HKEY_CURRENT_USER, None), variable_name)
        except FileNotFoundError:
            print('variable definition missing:', variable_name)
            print('add to environment or registry under HKEY_CURRENT_USER')
            sys.exit(1)
        except ModuleNotFoundError:
            print('Registry module not available')
            sys.exit(1)
    return result


def get_access_token(client_id, client_secret):
    token_url = "https://api.kroger.com/v1/connect/oauth2/token"
    payload = {
        "grant_type": "client_credentials",
        "scope": "product.compact",
    }
    # The requests library 'auth' tuple automatically handles Base64 encoding
    # of client_id:client_secret and sets the 'Authorization: Basic ...' header.
    response = requests.post(
        token_url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=(client_id, client_secret),
    )
    response.raise_for_status()
    return response.json()["access_token"]


def search_products(access_token, location_id, term):
    url = "https://api.kroger.com/v1/products"
    params = {
        "filter.locationId": location_id,
        "filter.limit": 50,
    }
    # A numeric term is a product number (productId/UPC) rather than a
    # keyword -- filter.productId looks it up directly instead of doing a
    # text search over it.
    if term.isdigit():
        params["filter.productId"] = term
    else:
        params["filter.term"] = term
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()["data"]


def format_price(product):
    # Price lives under the first item, not on the product itself -- a
    # product can be out of stock/unpriced at this store, so items or price
    # can be missing entirely.
    items = product.get("items") or [{}]
    price = items[0].get("price") or {}
    regular = price.get("regular")
    promo = price.get("promo")
    if regular is None:
        return "-"
    if promo and promo != regular:
        return f"${promo:.2f} (reg ${regular:.2f})"
    return f"${regular:.2f}"


_WEIGHT_PATTERN = re.compile(r"\s*([\d.]+)\s*\[([^\]]+)\]")


def _parse_weight_lb(text):
    # itemInformation weight fields look like "3.97 [lb_av]" -- confirmed
    # live that "lb_av" (pounds avoirdupois) is the only unit code seen on
    # weight fields; a zero or missing value (both occur in real data --
    # some products have no netWeight at all, one had "0.0 [lb_av]") isn't
    # usable as a divisor.
    if not text:
        return None
    match = _WEIGHT_PATTERN.match(text)
    if not match:
        return None
    value = float(match.group(1))
    if match.group(2) != "lb_av" or value <= 0:
        return None
    return value


def format_price_per_lb(product):
    items = product.get("items") or [{}]
    item = items[0]
    price = item.get("price") or {}
    regular = price.get("regular")
    promo = price.get("promo")
    if item.get("soldBy") == "WEIGHT":
        # Butcher-counter items sold by weight: price.regular/promo is
        # already $/lb (confirmed live via regularPerUnitEstimate/
        # promoPerUnitEstimate matching regular/promo exactly), no
        # netWeight to divide by.
        per_lb = promo if (promo and promo != regular) else regular
        return f"${per_lb:.2f}/lb" if per_lb is not None else "-"

    info = product.get("itemInformation") or {}
    weight_lb = _parse_weight_lb(info.get("netWeight")) or _parse_weight_lb(info.get("grossWeight"))
    if not weight_lb:
        return "-"
    effective_price = promo if (promo and promo != regular) else regular
    if effective_price is None:
        return "-"
    return f"${effective_price / weight_lb:.2f}/lb"


def format_location(product):
    aisles = product.get("aisleLocations") or []
    if not aisles:
        return "-"
    aisle = aisles[0]
    return f"{aisle.get('description', '')} - Aisle {aisle.get('number', '')} ({aisle.get('side', '')})"


def print_table(rows, headers):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    row_format = "  ".join(f"{{:<{w}}}" for w in widths)
    print(row_format.format(*headers))
    print(row_format.format(*("-" * w for w in widths)))
    for row in rows:
        print(row_format.format(*row))


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <search term>")
        sys.exit(1)
    term = sys.argv[1]

    client_id = load_variable("KROGER_CLIENT_ID")
    client_secret = load_variable("KROGER_CLIENT_SECRET")

    access_token = get_access_token(client_id, client_secret)

    location_id = "02900525"
    products = search_products(access_token, location_id, term)

    if not products:
        print(f"No products found for '{term}'")
        return

    rows = [
        [
            product.get("productId", ""),
            product.get("description", ""),
            format_price(product),
            format_price_per_lb(product),
            format_location(product),
        ]
        for product in products
    ]
    print_table(rows, ["Product #", "Product", "Price", "$/lb", "Location"])


if __name__ == "__main__":
    main()
