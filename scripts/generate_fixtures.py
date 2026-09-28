"""Deterministic synthetic metadata, never connects to a warehouse."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "fixtures"
SPECS = {
    "commerce": [
        ("customers", "Customer profiles contact details and account registration", "customer_id,email,region"),
        ("orders", "Customer purchases order status checkout and gross merchandise value", "order_id,customer_id,total_amount"),
        ("order_items", "Individual purchased products quantity and unit price", "order_id,product_id,quantity"),
        ("products", "Product catalog names categories and list prices", "product_id,category_id,list_price"),
        ("categories", "Merchandise category hierarchy taxonomy", "category_id,parent_category_id,label"),
        ("carts", "Shopping cart abandonment before checkout", "cart_id,customer_id,abandoned_at"),
        ("shipments", "Order delivery tracking carriers shipping dispatch", "shipment_id,order_id,tracking_number"),
        ("returns", "Returned merchandise reasons reverse logistics", "return_id,order_id,reason"),
        ("inventory", "Warehouse stock availability replenishment quantities", "product_id,warehouse_id,stock_quantity"),
        ("suppliers", "Vendor procurement contacts and supplier contracts", "supplier_id,company_name,contact_email"),
        ("promotions", "Discount campaigns coupon codes promotional offers", "promotion_id,coupon_code,discount_amount"),
        ("reviews", "Product star ratings customer feedback reviews", "review_id,product_id,rating"),
        ("wishlists", "Saved favorite products shopping intent", "customer_id,product_id,saved_at"),
        ("loyalty", "Reward points membership tiers customer loyalty", "customer_id,points,tier"),
        ("daily_sales", "Daily aggregated sales revenue merchandise performance", "sale_date,product_id,revenue"),
    ],
    "finance": [
        ("payments", "Payment transactions settlement card transfer status", "payment_id,order_id,amount"),
        ("refunds", "Money refunded to buyers payment reversals", "refund_id,payment_id,amount"),
        ("invoices", "Customer billing invoices due dates receivables", "invoice_id,customer_id,due_date"),
        ("invoice_lines", "Invoice line charges billed units", "invoice_id,product_id,amount"),
        ("subscriptions", "Recurring plans monthly recurring revenue MRR", "subscription_id,customer_id,monthly_amount"),
        ("ledger_entries", "Double entry accounting general ledger postings", "entry_id,account_id,debit_amount"),
        ("accounts", "Chart of accounts accounting classification", "account_id,account_name,account_type"),
        ("exchange_rates", "Currency foreign exchange conversion daily FX rates", "currency,rate_date,exchange_rate"),
        ("tax_rates", "Regional taxation VAT sales tax percentages", "region,tax_code,percentage"),
        ("budgets", "Department spending budgets planned allocation", "department_id,fiscal_year,planned_amount"),
        ("expenses", "Employee expense reimbursement business spending", "expense_id,employee_id,amount"),
        ("payouts", "Merchant disbursement payout bank transfers", "payout_id,supplier_id,amount"),
        ("chargebacks", "Disputed card charges fraud chargeback cases", "chargeback_id,payment_id,reason"),
        ("revenue_daily", "Recognized net revenue daily financial reporting", "revenue_date,recognized_amount,currency"),
        ("audit_events", "Financial audit trail changes compliance history", "event_id,actor_id,action"),
    ],
    "product": [
        ("users", "Application user identities signup activation profiles", "user_id,customer_id,email"),
        ("sessions", "Application visits session duration device platform", "session_id,user_id,duration_seconds"),
        ("events", "Application clickstream behavioral event tracking", "event_id,session_id,event_name"),
        ("page_views", "Web page traffic views URLs referrers", "view_id,session_id,url"),
        ("features", "Feature registry product capabilities release catalog", "feature_id,feature_name,released_at"),
        ("feature_usage", "Feature adoption engagement usage counters", "user_id,feature_id,use_count"),
        ("experiments", "AB testing experiment hypotheses treatment variants", "experiment_id,hypothesis,start_date"),
        ("experiment_assignments", "Experiment cohort variant assignment participants", "experiment_id,user_id,variant"),
        ("conversions", "Funnel goal completions conversion attribution", "user_id,session_id,goal_name"),
        ("retention", "Weekly user retention cohort return activity", "cohort_week,user_id,retained"),
        ("notifications", "Push and email notification delivery messages", "notification_id,user_id,channel"),
        ("support_tickets", "Customer support issues resolution helpdesk", "ticket_id,user_id,resolution_time"),
        ("feedback", "In app survey satisfaction NPS responses", "response_id,user_id,nps_score"),
        ("errors", "Application crashes error telemetry stack traces", "error_id,session_id,error_message"),
        ("releases", "Application deployment version release history", "release_id,version,deployed_at"),
    ],
}
assets, edges, definitions = [], [], []
for domain, tables in SPECS.items():
    assets.append(dict(id=domain, kind="dataset", name=domain, data_type="schema",
                       description=f"{domain.title()} warehouse domain", domain=domain,
                       owners=[f"{domain}-platform"], tags=[domain]))
    for name, description, columns in tables:
        table_id = f"{domain}.{name}"
        assets.append(dict(id=table_id, kind="table", name=name, data_type="table",
                           description=description, domain=domain, parent_id=domain,
                           owners=[f"{domain}-analytics"], tags=[domain, "synthetic"]))
        for column in columns.split(",") + ["created_at", "updated_at"]:
            numeric = any(word in column for word in ["amount", "price", "quantity", "count", "score", "rate", "points", "seconds"])
            dtype = "numeric" if numeric else "timestamptz" if column.endswith("_at") else "text"
            assets.append(dict(id=f"{table_id}.{column}", kind="column", name=column,
                               data_type=dtype, description=f"{column.replace('_', ' ')} for {name.replace('_', ' ')}",
                               domain=domain, parent_id=table_id, owners=[f"{domain}-analytics"], tags=[domain]))


def edge(source, target, kind, sc=None, tc=None):
    edges.append(dict(source_id=source, target_id=target, kind=kind,
                      description=f"{source}.{sc} = {target}.{tc}" if kind == "join" else f"{source} → {target}",
                      source_column=sc, target_column=tc))


for source, target, column in [
    ("commerce.orders", "commerce.customers", "customer_id"),
    ("commerce.order_items", "commerce.orders", "order_id"),
    ("commerce.order_items", "commerce.products", "product_id"),
    ("commerce.products", "commerce.categories", "category_id"),
    ("commerce.shipments", "commerce.orders", "order_id"),
    ("commerce.returns", "commerce.orders", "order_id"),
    ("commerce.inventory", "commerce.products", "product_id"),
    ("commerce.reviews", "commerce.products", "product_id"),
    ("commerce.loyalty", "commerce.customers", "customer_id"),
    ("finance.payments", "commerce.orders", "order_id"),
    ("finance.refunds", "finance.payments", "payment_id"),
    ("finance.chargebacks", "finance.payments", "payment_id"),
    ("finance.invoices", "commerce.customers", "customer_id"),
    ("finance.subscriptions", "commerce.customers", "customer_id"),
    ("finance.invoice_lines", "finance.invoices", "invoice_id"),
    ("finance.ledger_entries", "finance.accounts", "account_id"),
    ("product.users", "commerce.customers", "customer_id"),
    ("product.sessions", "product.users", "user_id"),
    ("product.events", "product.sessions", "session_id"),
    ("product.page_views", "product.sessions", "session_id"),
    ("product.feature_usage", "product.features", "feature_id"),
    ("product.feature_usage", "product.users", "user_id"),
    ("product.experiment_assignments", "product.experiments", "experiment_id"),
    ("product.experiment_assignments", "product.users", "user_id"),
    ("product.support_tickets", "product.users", "user_id"),
]:
    edge(source, target, "join", column, column)
edge("commerce.orders", "commerce.daily_sales", "lineage")
edge("commerce.order_items", "commerce.daily_sales", "lineage")
edge("finance.payments", "finance.revenue_daily", "lineage")
edge("finance.refunds", "finance.revenue_daily", "lineage")
edge("product.events", "product.retention", "lineage")
edge("commerce.customers", "product.users", "same_concept")
for term, definition, ids in [
    ("GMV", "Gross merchandise value before refunds and fees", ["commerce.orders", "commerce.daily_sales"]),
    ("MRR", "Monthly recurring revenue from active subscriptions", ["finance.subscriptions"]),
    ("Net revenue", "Recognized revenue after refunds and adjustments", ["finance.revenue_daily", "finance.refunds"]),
    ("Active user", "A user with a recorded application session", ["product.users", "product.sessions"]),
    ("Retention", "Share of a signup cohort returning in a later week", ["product.retention"]),
    ("Conversion", "Completion of a tracked funnel goal", ["product.conversions"]),
    ("NPS", "Net promoter score from user satisfaction surveys", ["product.feedback"]),
    ("Stock", "Units currently available in a warehouse", ["commerce.inventory"]),
]:
    definitions.append(dict(term=term, definition=definition, asset_ids=ids))
ROOT.mkdir(exist_ok=True)
(ROOT / "warehouse.json").write_text(json.dumps(dict(assets=assets, edges=edges, definitions=definitions), indent=2) + "\n")
as_of = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
queries = []
for index, asset in enumerate(a for a in assets if a["kind"] == "table"):
    # Leave every seventh table unused; popularity is unrelated to golden labels.
    for n in range(0 if index % 7 == 0 else 3 + (index * 13) % 50):
        queries.append(dict(query_id=f"q-{index}-{n}", occurred_at=(as_of - timedelta(hours=n * 3 + index)).isoformat(),
                            asset_ids=[asset["id"]], team=f"team-{n % 3}"))
queries.append(dict(query_id="old-customer", occurred_at=(as_of - timedelta(days=30)).isoformat(),
                    asset_ids=["commerce.customers"], team="growth"))
(ROOT / "query_history.json").write_text(json.dumps(dict(as_of=as_of.isoformat(), queries=queries), indent=2) + "\n")
GOLDEN = [
    ("customer profiles", ["commerce.customers"]), ("gross merchandise value", ["commerce.orders", "commerce.daily_sales"]),
    ("purchased products quantity", ["commerce.order_items"]), ("product catalog", ["commerce.products"]),
    ("category hierarchy", ["commerce.categories"]), ("cart abandonment", ["commerce.carts"]),
    ("delivery tracking", ["commerce.shipments"]), ("returned merchandise", ["commerce.returns"]),
    ("stock availability", ["commerce.inventory"]), ("supplier contracts", ["commerce.suppliers"]),
    ("coupon codes", ["commerce.promotions"]), ("star ratings", ["commerce.reviews"]),
    ("reward points", ["commerce.loyalty"]), ("payment settlement", ["finance.payments"]),
    ("payment reversals", ["finance.refunds"]), ("billing due dates", ["finance.invoices"]),
    ("monthly recurring revenue", ["finance.subscriptions"]), ("ledger postings", ["finance.ledger_entries"]),
    ("foreign exchange", ["finance.exchange_rates"]), ("department budgets", ["finance.budgets"]),
    ("expense reimbursement", ["finance.expenses"]), ("disputed charges", ["finance.chargebacks"]),
    ("recognized revenue", ["finance.revenue_daily"]), ("session duration", ["product.sessions"]),
    ("clickstream", ["product.events"]), ("feature adoption", ["product.feature_usage"]),
    ("experiment hypotheses", ["product.experiments"]), ("cohort retention", ["product.retention"]),
    ("helpdesk resolution", ["product.support_tickets"]), ("satisfaction NPS", ["product.feedback"]),
    ("crashes telemetry", ["product.errors"]), ("deployment version", ["product.releases"]),
    ("total amount", ["commerce.orders.total_amount"]), ("tracking number", ["commerce.shipments.tracking_number"]),
    ("duration seconds", ["product.sessions.duration_seconds"]), ("nps score", ["product.feedback.nps_score"]),
]
(ROOT / "golden_queries.json").write_text(json.dumps([dict(query=q, expected=expected,
    kind="column" if expected[0].count(".") == 2 else "table") for q, expected in GOLDEN], indent=2) + "\n")
