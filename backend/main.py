from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ── Azure / Dataverse config (set these in .env) ──────────────────────────────
TENANT_ID       = os.getenv("TENANT_ID")
CLIENT_ID       = os.getenv("CLIENT_ID")
CLIENT_SECRET   = os.getenv("CLIENT_SECRET")
DATAVERSE_URL   = os.getenv("DATAVERSE_URL")          # e.g. https://yourorg.crm.dynamics.com
TABLE_NAME      = os.getenv("TABLE_NAME", "cr399_tables")  # logical plural name


def get_access_token():
    """Obtain a Bearer token via client-credentials flow."""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         f"{DATAVERSE_URL}/.default",
    }
    resp = requests.post(url, data=data, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def query_dataverse(filter_expr: str, select_cols: str):
    """Run an OData query against Dataverse and return the value list."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version":    "4.0",
        "Prefer": "odata.include-annotations=OData.Community.Display.V1.FormattedValue",
    }
    endpoint = (
        f"{DATAVERSE_URL}/api/data/v9.2/{TABLE_NAME}"
        f"?$select={select_cols}&$filter={filter_expr}&$top=50"
    )
    resp = requests.get(endpoint, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json().get("value", [])


# ── Columns to retrieve ───────────────────────────────────────────────────────
SELECT_COLS = ",".join([
    "cr399_cr1e1_0003ausalesordersid",   # Primary key
    "cr399_cr1e1_no",                    # Sales Order Number
    "cr399_cr1e1_itemno",                # Item No
    "cr399_cr1e1_customername",          # Customer Name
    "cr399_cr1e1_customerno",            # Customer No
    "cr399_cr1e1_bincode",               # Bin Code
    "cr399_cr1e1_externaldocumentno",    # External Document No
    "cr399_cr1e1_locationcode",          # Location Code
    "cr399_cr1e1_orderdate",             # Order Date
    "cr399_cr1e1_quantity",              # Quantity
    "cr399_cr1e1_saleinvoiceno",         # Sale Invoice No
    "cr399_cr1e1_salespersoncode",       # Salesperson Code
    "cr399_cr1e1_shiptoaddress",         # Ship-to Address
    "cr399_cr1e1_shiptoaddress2",        # Ship-to Address 2
    "cr399_cr1e1_shiptocity",            # Ship-to City
    "cr399_cr1e1_shiptocountry",         # Ship-to Country
    "cr399_cr1e1_shiptocountryregion",   # Ship-to Country/Region
    "cr399_cr1e1_shiptoname",            # Ship-to Name
    "cr399_cr1e1_shiptophoneno",         # Ship-to Phone No
    "cr399_cr1e1_shiptopostcode",        # Ship-to Post Code
    "cr399_cr1e1_status",                # Status
    "cr399_cr1e1_totalinclvataud",       # Total Incl. VAT (AUD)
    "cr399_cr1e1_totalvataud",           # Total VAT (AUD)
    "cr399_cr1e1_trackingnumber",        # Tracking Number
    "cr399_cr1e1_type",                  # Type
    "cr399_cr1e1_unitpriceincvat",       # Unit Price Incl. VAT
    "cr399_cr1e1_yourreference",         # Your Reference
    "cr399_cr1e1_starshipitshipmentdate",# Shipment Date
    "cr399_cr1e1_carriername",           # Carrier Name
    "cr399_cr1e1_carrierservice",        # Carrier Service
])


@app.route("/api/search", methods=["GET"])
def search():
    query      = request.args.get("q", "").strip()
    search_by  = request.args.get("by", "name")   # name | external | reference

    if not query:
        return jsonify({"error": "Query parameter 'q' is required."}), 400

    safe_query = query.replace("'", "''")   # basic OData injection guard

    filter_map = {
        "name":      f"contains(cr399_cr1e1_no,'{safe_query}')",
        "external":  f"contains(cr399_cr1e1_externaldocumentno,'{safe_query}')",
        "reference": f"contains(cr399_cr1e1_yourreference,'{safe_query}')",
    }
    filter_expr = filter_map.get(search_by, filter_map["name"])

    try:
        records = query_dataverse(filter_expr, SELECT_COLS)
        return jsonify({"data": records, "count": len(records)})
    except requests.HTTPError as e:
        return jsonify({"error": str(e), "detail": e.response.text}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/order/<order_id>", methods=["GET"])
def get_order(order_id):
    """Fetch a single order by its GUID."""
    try:
        token = get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version":    "4.0",
            "Prefer": "odata.include-annotations=OData.Community.Display.V1.FormattedValue",
        }
        url = f"{DATAVERSE_URL}/api/data/v9.2/{TABLE_NAME}({order_id})?$select={SELECT_COLS}"
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.HTTPError as e:
        return jsonify({"error": str(e), "detail": e.response.text}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)